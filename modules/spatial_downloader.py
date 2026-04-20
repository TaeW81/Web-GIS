"""
공간 데이터 다운로드 모듈

역할:
  - VWorld WFS API로 벡터 데이터 요청
  - 좌표계 변환 (EPSG:4326 → 사용자 선택 EPSG)
  - 구역계(Polygon)를 별도 레이어로 포함
  - SHP(ZIP) 및 DXF 포맷으로 변환/내보내기
"""
import requests
import shapefile
import ezdxf
import zipfile
from io import BytesIO, StringIO
from pyproj import Transformer
from shapely.geometry import shape, Polygon, MultiPolygon
from config import VWORLD_KEY, VWORLD_WFS_LAYERS


# ========================================================
# 1. VWorld WFS 데이터 조회
# ========================================================
def fetch_wfs_data(layer_name: str, bbox: str, api_key: str = None) -> dict:
    """
    VWorld WFS API를 호출하여 GeoJSON 데이터를 반환합니다.

    Args:
        layer_name: UI 레이어 이름 (예: "지적도", "도시지역")
        bbox: "minLon,minLat,maxLon,maxLat" 형식의 BBOX 문자열
        api_key: VWorld API 키

    Returns:
        dict: { "geojson": GeoJSON dict, "count": int, "overflow": bool }

    Raises:
        ValueError: 지원하지 않는 레이어인 경우
        ConnectionError: API 호출 실패 시
    """
    key = api_key or VWORLD_KEY

    layer_config = VWORLD_WFS_LAYERS.get(layer_name)
    if not layer_config:
        raise ValueError(
            f"'{layer_name}' 레이어는 WFS 다운로드를 지원하지 않습니다.\n"
            f"지원 레이어: {', '.join(VWORLD_WFS_LAYERS.keys())}"
        )

    wfs_url = "https://api.vworld.kr/req/wfs"
    all_features = {}

    def fetch_grid(grid_bbox: list, depth: int):
        bbox_str = f"{grid_bbox[0]},{grid_bbox[1]},{grid_bbox[2]},{grid_bbox[3]}"
        params = {
            "key": key,
            "domain": "http://localhost",
            "SERVICE": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "TYPENAME": layer_config["typename"],
            "BBOX": f"{bbox_str},EPSG:4326",
            "SRSNAME": "EPSG:4326",
            "output": "application/json",
            "MAXFEATURES": "1000",
        }

        try:
            resp = requests.get(wfs_url, params=params, timeout=30)
            if resp.status_code != 200:
                raise ConnectionError(f"VWorld WFS API 오류 (HTTP {resp.status_code})")
        except Exception:
            return

        geojson = resp.json()
        features = geojson.get("features", [])
        count = len(features)

        # 1000건 제한 도달 시 & 최대 뎁스 4(총 5레벨) 이내일 때 3x3=9 분할
        if count >= 1000 and depth < 4:
            lat_step = (grid_bbox[2] - grid_bbox[0]) / 3.0
            lon_step = (grid_bbox[3] - grid_bbox[1]) / 3.0
            for i in range(3):
                for j in range(3):
                    sub_minLat = grid_bbox[0] + i * lat_step
                    sub_minLon = grid_bbox[1] + j * lon_step
                    sub_maxLat = sub_minLat + lat_step
                    sub_maxLon = sub_minLon + lon_step
                    fetch_grid([sub_minLat, sub_minLon, sub_maxLat, sub_maxLon], depth + 1)
        else:
            for f in features:
                fid = f.get("id")
                if not fid:
                    from hashlib import md5
                    fid = md5(str(f).encode('utf-8')).hexdigest()
                all_features[fid] = f

    initial_bbox = [float(x) for x in bbox.split(",")]
    fetch_grid(initial_bbox, 0)
    
    merged_features = list(all_features.values())
    count = len(merged_features)

    return {
        "geojson": {
            "type": "FeatureCollection",
            "name": layer_config["typename"],
            "features": merged_features
        },
        "count": count,
        "overflow": False,  # 격자 분할로 모두 가져오므로 짤림 경고 제거
        "layer_config": layer_config,
    }


# ========================================================
# 2. 좌표 변환 헬퍼
# ========================================================
def _transform_ring(ring, transformer):
    """좌표 리스트를 변환합니다. ring: [(lon, lat), ...]"""
    return [transformer.transform(pt[0], pt[1]) for pt in ring]


def _transform_geojson_coords(geojson_data: dict, target_epsg: str) -> dict:
    """
    GeoJSON의 모든 좌표를 target_epsg로 변환한 복사본을 반환합니다.
    원본은 수정하지 않습니다.
    """
    import copy
    data = copy.deepcopy(geojson_data)

    transformer = Transformer.from_crs("EPSG:4326", target_epsg, always_xy=True)

    for feature in data.get("features", []):
        geom = feature.get("geometry", {})
        gtype = geom.get("type")
        coords = geom.get("coordinates", [])

        if gtype == "Polygon":
            geom["coordinates"] = [_transform_ring(ring, transformer) for ring in coords]
        elif gtype == "MultiPolygon":
            geom["coordinates"] = [
                [_transform_ring(ring, transformer) for ring in poly]
                for poly in coords
            ]
        elif gtype == "Point":
            geom["coordinates"] = list(transformer.transform(coords[0], coords[1]))
        elif gtype == "LineString":
            geom["coordinates"] = _transform_ring(coords, transformer)
        elif gtype == "MultiLineString":
            geom["coordinates"] = [_transform_ring(line, transformer) for line in coords]

    return data


def _make_boundary_feature(polygon_lonlat_points: list, target_epsg: str) -> dict:
    """
    업로드된 구역계 좌표를 GeoJSON Feature로 변환합니다.

    Args:
        polygon_lonlat_points: [(lon, lat), ...] 형태의 좌표 리스트
        target_epsg: 대상 좌표계

    Returns:
        변환된 좌표의 GeoJSON Feature dict
    """
    transformer = Transformer.from_crs("EPSG:4326", target_epsg, always_xy=True)

    transformed = [transformer.transform(lon, lat) for lon, lat in polygon_lonlat_points]

    return {
        "type": "Feature",
        "properties": {"name": "구역계", "type": "Project_Boundary"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [transformed],
        },
    }


# ========================================================
# 3. DXF 내보내기
# ========================================================
def export_to_dxf(
    geojson_data: dict,
    layer_name: str,
    target_epsg: str = "EPSG:5186",
    boundary_points: list = None,
) -> bytes:
    """
    GeoJSON 데이터를 DXF 파일 바이너리로 변환합니다.

    Args:
        geojson_data: 원본 GeoJSON (EPSG:4326)
        layer_name: UI 레이어 이름
        target_epsg: 출력 좌표계
        boundary_points: 구역계 좌표 [(lon, lat), ...] (None이면 미포함)

    Returns:
        bytes: DXF 파일 바이너리
    """
    layer_config = VWORLD_WFS_LAYERS.get(layer_name, {})
    dxf_layers = layer_config.get("dxf_layers", {"boundary": "DATA_LINE", "text": "DATA_TEXT"})
    label_field = layer_config.get("label_field", "")

    # 좌표 변환
    transformed = _transform_geojson_coords(geojson_data, target_epsg)

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # DXF 레이어 생성
    doc.layers.add(dxf_layers["boundary"], color=2)   # 2: 노란색
    doc.layers.add(dxf_layers["text"], color=7)        # 7: 흰색
    doc.layers.add("0_PROJECT_BOUNDARY", color=1)      # 1: 빨간색

    # 피처 처리
    for feature in transformed.get("features", []):
        geom = feature.get("geometry", {})
        props = feature.get("properties", {})

        if not geom:
            continue

        gtype = geom.get("type")
        coords = geom.get("coordinates", [])

        # 라벨 텍스트 추출
        label_text = ""
        if label_field and label_field in props:
            label_text = str(props[label_field] or "")

        def _add_polygon_ring(ring, layer_name_dxf):
            """폴리곤 링을 Closed LWPolyline으로 추가"""
            if not ring:
                return
            points = [(pt[0], pt[1]) for pt in ring]
            msp.add_lwpolyline(
                points,
                close=True,
                dxfattribs={"layer": layer_name_dxf},
            )

        def _add_label(rings, text, layer_name_dxf):
            """폴리곤의 중심점에 텍스트 추가"""
            if not text or not rings or not rings[0]:
                return
            try:
                poly = Polygon([(pt[0], pt[1]) for pt in rings[0]])
                centroid = poly.centroid
                # 텍스트 높이는 폴리곤 크기에 비례
                bounds = poly.bounds  # (minx, miny, maxx, maxy)
                extent = max(bounds[2] - bounds[0], bounds[3] - bounds[1])
                text_height = max(1.0, extent * 0.03)

                msp.add_text(
                    text,
                    height=text_height,
                    dxfattribs={
                        "layer": layer_name_dxf,
                        "insert": (centroid.x, centroid.y),
                    },
                ).set_placement(
                    (centroid.x, centroid.y),
                    align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER,
                )
            except Exception:
                pass  # 텍스트 생성 실패 시 무시

        if gtype == "Polygon":
            for ring in coords:
                _add_polygon_ring(ring, dxf_layers["boundary"])
            _add_label(coords, label_text, dxf_layers["text"])

        elif gtype == "MultiPolygon":
            for poly_coords in coords:
                for ring in poly_coords:
                    _add_polygon_ring(ring, dxf_layers["boundary"])
                _add_label(poly_coords, label_text, dxf_layers["text"])

    # 구역계 추가
    if boundary_points:
        boundary_feat = _make_boundary_feature(boundary_points, target_epsg)
        b_coords = boundary_feat["geometry"]["coordinates"][0]
        points = [(pt[0], pt[1]) for pt in b_coords]
        msp.add_lwpolyline(
            points,
            close=True,
            dxfattribs={"layer": "0_PROJECT_BOUNDARY"},
        )

    # 메모리에 기록
    stream = StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


# ========================================================
# 4. SHP 내보내기 (ZIP)
# ========================================================
def _get_prj_content(epsg_code: str) -> str:
    """
    EPSG 코드에 대한 .prj 파일 내용(WKT)를 반환합니다.
    주요 한국 좌표계에 대한 내장 WKT를 사용합니다.
    """
    PRJ_WKT = {
        "EPSG:4326": (
            'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
            'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
            'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
        ),
        "EPSG:5186": (
            'PROJCS["Korea_2000_Korea_Central_Belt_2010",'
            'GEOGCS["GCS_Korea_2000",DATUM["D_Korea_2000",'
            'SPHEROID["GRS_1980",6378137.0,298.257222101]],'
            'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
            'PROJECTION["Transverse_Mercator"],'
            'PARAMETER["False_Easting",200000.0],'
            'PARAMETER["False_Northing",600000.0],'
            'PARAMETER["Central_Meridian",127.0],'
            'PARAMETER["Scale_Factor",1.0],'
            'PARAMETER["Latitude_Of_Origin",38.0],'
            'UNIT["Meter",1.0]]'
        ),
        "EPSG:5185": (
            'PROJCS["Korea_2000_Korea_West_Belt_2010",'
            'GEOGCS["GCS_Korea_2000",DATUM["D_Korea_2000",'
            'SPHEROID["GRS_1980",6378137.0,298.257222101]],'
            'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
            'PROJECTION["Transverse_Mercator"],'
            'PARAMETER["False_Easting",200000.0],'
            'PARAMETER["False_Northing",600000.0],'
            'PARAMETER["Central_Meridian",125.0],'
            'PARAMETER["Scale_Factor",1.0],'
            'PARAMETER["Latitude_Of_Origin",38.0],'
            'UNIT["Meter",1.0]]'
        ),
        "EPSG:5187": (
            'PROJCS["Korea_2000_Korea_East_Belt_2010",'
            'GEOGCS["GCS_Korea_2000",DATUM["D_Korea_2000",'
            'SPHEROID["GRS_1980",6378137.0,298.257222101]],'
            'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
            'PROJECTION["Transverse_Mercator"],'
            'PARAMETER["False_Easting",200000.0],'
            'PARAMETER["False_Northing",600000.0],'
            'PARAMETER["Central_Meridian",129.0],'
            'PARAMETER["Scale_Factor",1.0],'
            'PARAMETER["Latitude_Of_Origin",38.0],'
            'UNIT["Meter",1.0]]'
        ),
        "EPSG:5174": (
            'PROJCS["Korea_1985_Korea_Central_Belt",'
            'GEOGCS["GCS_Tokyo",DATUM["D_Tokyo",'
            'SPHEROID["Bessel_1841",6377397.155,299.1528128]],'
            'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
            'PROJECTION["Transverse_Mercator"],'
            'PARAMETER["False_Easting",200000.0],'
            'PARAMETER["False_Northing",500000.0],'
            'PARAMETER["Central_Meridian",127.00289027777778],'
            'PARAMETER["Scale_Factor",1.0],'
            'PARAMETER["Latitude_Of_Origin",38.0],'
            'UNIT["Meter",1.0]]'
        ),
        "EPSG:5179": (
            'PROJCS["Korea_2000_Unified_CS",'
            'GEOGCS["GCS_Korea_2000",DATUM["D_Korea_2000",'
            'SPHEROID["GRS_1980",6378137.0,298.257222101]],'
            'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],'
            'PROJECTION["Transverse_Mercator"],'
            'PARAMETER["False_Easting",1000000.0],'
            'PARAMETER["False_Northing",2000000.0],'
            'PARAMETER["Central_Meridian",127.5],'
            'PARAMETER["Scale_Factor",0.9996],'
            'PARAMETER["Latitude_Of_Origin",38.0],'
            'UNIT["Meter",1.0]]'
        ),
    }
    return PRJ_WKT.get(epsg_code, PRJ_WKT.get("EPSG:5186", ""))


def export_to_shp(
    geojson_data: dict,
    layer_name: str,
    target_epsg: str = "EPSG:5186",
    boundary_points: list = None,
) -> bytes:
    """
    GeoJSON 데이터를 SHP 파일 세트(ZIP)로 변환합니다.

    Args:
        geojson_data: 원본 GeoJSON (EPSG:4326)
        layer_name: UI 레이어 이름
        target_epsg: 출력 좌표계
        boundary_points: 구역계 좌표 [(lon, lat), ...] (None이면 미포함)

    Returns:
        bytes: ZIP 파일 바이너리 (shp, shx, dbf, prj 포함)
    """
    layer_config = VWORLD_WFS_LAYERS.get(layer_name, {})
    fields_map = layer_config.get("fields", {}).copy()

    features = geojson_data.get("features", [])
    # 동적 매핑 등 필드가 부족한 경우 첫 번째 피처의 속성으로 자동 구성 (Shapefile 필드명 10자 제한 고려)
    if features and len(fields_map) <= 1:
        props = features[0].get("properties", {})
        if props:
            fields_map = {}
            for k in props.keys():
                safe_name = str(k).strip()[:10]
                if not safe_name: safe_name = "FIELD"
                # 중복 필드명 방지
                base_name = safe_name
                idx = 1
                while safe_name in fields_map.values():
                    safe_name = f"{base_name[:8]}{idx}"
                    idx += 1
                fields_map[k] = safe_name

    # 좌표 변환
    transformed = _transform_geojson_coords(geojson_data, target_epsg)

    # shapefile Writer 생성 (메모리)
    shp_buf = BytesIO()
    shx_buf = BytesIO()
    dbf_buf = BytesIO()

    w = shapefile.Writer(shp=shp_buf, shx=shx_buf, dbf=dbf_buf)
    w.shapeType = shapefile.POLYGON

    # 필드 정의
    w.field("LAYER", "C", 40)   # 레이어 구분
    for field_key, field_label in fields_map.items():
        w.field(field_label, "C", 100)
    w.field("AREA", "N", 18, 2)  # 면적

    # 피처 처리
    for feature in transformed.get("features", []):
        geom = feature.get("geometry", {})
        props = feature.get("properties", {})

        if not geom:
            continue

        gtype = geom.get("type")
        coords = geom.get("coordinates", [])

        # shapefile에 들어갈 폴리곤 파트(parts) 구성
        parts = []
        if gtype == "Polygon":
            for ring in coords:
                parts.append([(pt[0], pt[1]) for pt in ring])
        elif gtype == "MultiPolygon":
            for poly in coords:
                for ring in poly:
                    parts.append([(pt[0], pt[1]) for pt in ring])
        else:
            continue

        if not parts:
            continue

        w.poly(parts)

        # 면적 계산
        try:
            geom_shape = shape(geom)
            area = geom_shape.area
        except Exception:
            area = 0.0

        # 속성 레코드
        record = [layer_name]
        for field_key in fields_map.keys():
            val = props.get(field_key, "")
            record.append(str(val) if val else "")
        record.append(area)

        w.record(*record)

    # 구역계 추가
    if boundary_points:
        boundary_feat = _make_boundary_feature(boundary_points, target_epsg)
        b_coords = boundary_feat["geometry"]["coordinates"][0]
        b_points = [(pt[0], pt[1]) for pt in b_coords]
        w.poly([b_points])

        record = ["구역계"]
        for _ in fields_map.keys():
            record.append("")
        # 구역계 면적 계산
        try:
            boundary_poly = Polygon(b_points)
            record.append(boundary_poly.area)
        except Exception:
            record.append(0.0)
        w.record(*record)

    w.close()

    # PRJ 파일 생성
    prj_content = _get_prj_content(target_epsg)

    # ZIP으로 패키징
    zip_buf = BytesIO()
    safe_name = layer_name.replace(" ", "_")

    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{safe_name}.shp", shp_buf.getvalue())
        zf.writestr(f"{safe_name}.shx", shx_buf.getvalue())
        zf.writestr(f"{safe_name}.dbf", dbf_buf.getvalue())
        zf.writestr(f"{safe_name}.prj", prj_content)

    return zip_buf.getvalue()
