"""
PNU(필지고유번호) 추출 모듈

역할:
  - 구역계 Polygon의 Bounding Box로 브이월드에서 지적도를 가져옴 (무제한 페이지네이션)
  - shapely intersects()로 구역계에 편입되는 PNU만 정밀 필터링
"""
import requests
from shapely.geometry import shape
from shapely.ops import transform
from pyproj import Transformer
from config import VWORLD_DATA_URL, VWORLD_DOMAIN, CADASTRAL_LAYER

def extract_pnu_list(boundary_polygon, api_key):
    """
    구역계 폴리곤과 교차하는 모든 필지의 PNU 리스트를 추출합니다. (대규모 대응)
    """
    # 1. Bounding Box 계산 (검색 누락 방지를 위해 0.0001도 버퍼 추가)
    buffer = 0.0001
    min_x, min_y, max_x, max_y = boundary_polygon.bounds
    box_filter = f"BOX({min_x-buffer},{min_y-buffer},{max_x+buffer},{max_y+buffer})"
    
    project_to_meter = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True).transform
    try:
        boundary_polygon_m = transform(project_to_meter, boundary_polygon)
    except:
        boundary_polygon_m = boundary_polygon

    # 2. 브이월드 지적도 API 호출 (페이지네이션 적용)
    all_features = []
    page = 1
    page_size = 1000
    
    while True:
        params = {
            "service": "data", "request": "GetFeature", "data": CADASTRAL_LAYER,
            "key": api_key, "domain": VWORLD_DOMAIN, "geomFilter": box_filter,
            "geometry": "true", "size": str(page_size), "page": str(page)
        }
        
        # 네트워크/파싱 오류: 1페이지면 원인을 알 수 있게 전파, 이후 페이지면 가진 데이터로 마무리
        try:
            res = requests.get(VWORLD_DATA_URL, params=params, timeout=30)
            data = res.json()
        except Exception as net_err:
            if page == 1:
                raise RuntimeError(f"브이월드 연결/응답 오류: {net_err}")
            break

        status = data.get("response", {}).get("status")
        if status != "OK":
            if page == 1:
                err = data.get("response", {}).get("error", {})
                error_text = err.get("text") or err.get("code") or "알 수 없음"
                # 도메인/인증키 미등록 시 흔히 여기서 막힘 → 원인을 명확히 안내
                raise RuntimeError(
                    f"브이월드 응답 오류: {status} - {error_text}\n"
                    f"(요청 domain='{VWORLD_DOMAIN}') — 인증키에 이 도메인이 등록됐는지, "
                    f"웹 배포 시 VWORLD_DOMAIN secrets 설정이 배포 주소와 일치하는지 확인하세요."
                )
            else:
                break

        features = data.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [])
        if not features:
            break
        all_features.extend(features)

        record_info = data.get("response", {}).get("record", {})
        total_count = int(record_info.get("total", 0))
        if len(all_features) >= total_count or len(features) < page_size:
            break
        page += 1
        if page > 100:
            break  # 최대 10만 필지

    # 3. 정밀 필터링 및 중복 제거
    included = []
    seen_pnu = set()
    for feat in all_features:
        props = feat.get("properties", {})
        pnu = props.get("pnu", "")
        if not pnu or pnu in seen_pnu: continue
        
        geom = feat.get("geometry")
        if not geom: continue
        
        parcel_shape = shape(geom)
        if boundary_polygon.intersects(parcel_shape):
            try:
                parcel_shape_m = transform(project_to_meter, parcel_shape)
                intersection_m = boundary_polygon_m.intersection(parcel_shape_m)
                cad_area = intersection_m.area
                total_cad_area = parcel_shape_m.area
            except:
                cad_area = 0.0
                total_cad_area = 0.0

            included.append({
                "PNU": pnu, 
                "주소": props.get("addr", ""), 
                "지번": props.get("jibun", ""),
                "지목": props.get("jimok", "-"),
                "대장면적": float(props.get("parea", 0.0)),
                "공시지가": str(props.get("pnilp", "0")).strip(),
                "구적상면적": cad_area, 
                "전체구적면적": total_cad_area, 
                "지적도형": parcel_shape
            })
            seen_pnu.add(pnu)
    
    return included
