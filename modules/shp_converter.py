import io
import shapefile
import ezdxf
import pyproj
from shapely.geometry import mapping, shape

def format_value(val, decimal_places):
    if isinstance(val, (int, float)):
        try: return f"{float(val):.{decimal_places}f}"
        except: return str(val)
    return str(val)

def convert_shp_to_dxf_bytes(shp_io, shx_io, dbf_io, field_settings=None, text_size=2.0):
    """
    SHP, SHX, DBF 바이너리 데이터를 입력받아 DXF 바이너리(BytesIO)를 반환합니다.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # 기본 레이어
    doc.layers.new(name='GEOMETRY', dxfattribs={'color': 7})
    
    if field_settings:
        for f_name in field_settings.keys():
            if f_name not in doc.layers:
                doc.layers.new(name=f_name, dxfattribs={'color': 2})
                
    # pyshp Reader는 파일 경로뿐만 아니라 파일 객체(io)도 지원합니다.
    with shapefile.Reader(shp=shp_io, shx=shx_io, dbf=dbf_io, encoding='cp949') as sf:
        fields = [f[0] for f in sf.fields[1:]]
        for shape_rec in sf.shapeRecords():
            geom = shape_rec.shape
            record = shape_rec.record
            
            # 폴리라인/폴리곤 처리 (3: PolyLine, 5: Polygon, 8: MultiPoint 등)
            if geom.shapeType in [3, 5, 8, 13, 15]:
                for i in range(len(geom.parts)):
                    si = geom.parts[i]
                    ei = geom.parts[i+1] if i+1 < len(geom.parts) else len(geom.points)
                    msp.add_lwpolyline(geom.points[si:ei], dxfattribs={'layer': 'GEOMETRY'})
            
            # 포인트 처리 (1: Point, 11: PointZ 등)
            elif geom.shapeType in [1, 11, 21]:
                msp.add_point(geom.points[0], dxfattribs={'layer': 'GEOMETRY'})
            
            # 속성 텍스트 추가
            if field_settings:
                pts = geom.points
                if pts:
                    # 중심점 계산 (단순 평균)
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                    
                    ai = 0
                    for fn, pr in field_settings.items():
                        if fn in fields:
                            v = record[fields.index(fn)]
                            if v is not None:
                                tv = format_value(v, pr)
                                msp.add_text(tv, dxfattribs={'layer': fn, 'height': text_size}).set_placement((cx, cy - (ai * text_size * 1.5)))
                                ai += 1
                                
    # 결과를 StringIO로 받아 bytes로 인코딩하여 반환
    out_buf = io.StringIO()
    doc.write(out_buf)
    return out_buf.getvalue().encode('utf-8')

def get_shp_fields_from_io(shp_io, shx_io, dbf_io):
    """SHP 파일 객체들로부터 필드 목록을 추출합니다."""
    try:
        with shapefile.Reader(shp=shp_io, shx=shx_io, dbf=dbf_io, encoding='cp949') as sf:
            return [f[0] for f in sf.fields[1:]]
    except Exception:
        return []

def get_shp_geojson(shp_io, shx_io, dbf_io, source_epsg="EPSG:5186"):
    """
    SHP 데이터를 읽어 지도 표시용 GeoJSON(WGS84)으로 변환합니다.
    """
    features = []
    try:
        transformer = pyproj.Transformer.from_crs(source_epsg, "EPSG:4326", always_xy=True)
        
        with shapefile.Reader(shp=shp_io, shx=shx_io, dbf=dbf_io, encoding='cp949') as sf:
            fields = [f[0] for f in sf.fields[1:]]
            for shape_rec in sf.shapeRecords():
                geom = shape_rec.shape
                record = shape_rec.record
                
                # 좌표 변환 (pyshp geometries -> WGS84)
                new_points = []
                if geom.points:
                    for p in geom.points:
                        lon, lat = transformer.transform(p[0], p[1])
                        new_points.append([lon, lat])
                
                # 단순화된 GeoJSON 구조 생성 (Folium 호환)
                if geom.shapeType in [3, 5, 13, 15]: # PolyLine, Polygon
                    # 파트(Part) 처리
                    coords = []
                    for i in range(len(geom.parts)):
                        si = geom.parts[i]
                        ei = geom.parts[i+1] if i+1 < len(geom.parts) else len(geom.points)
                        part_pts = new_points[si:ei]
                        if geom.shapeType in [5, 15]: # Polygon은 닫혀야 함
                            coords.append(part_pts)
                        else:
                            coords.append(part_pts)
                    
                    type_str = "Polygon" if geom.shapeType in [5, 15] else "MultiLineString"
                    geometry = {"type": type_str, "coordinates": coords}
                elif geom.shapeType in [1, 11, 21]: # Point
                    geometry = {"type": "Point", "coordinates": new_points[0]}
                else:
                    continue

                properties = {fields[i]: record[i] for i in range(len(fields))}
                features.append({
                    "type": "Feature",
                    "geometry": geometry,
                    "properties": properties
                })
        
        return {"type": "FeatureCollection", "features": features}
    except Exception as e:
        print(f"GeoJSON 변환 오류: {e}")
        return None
