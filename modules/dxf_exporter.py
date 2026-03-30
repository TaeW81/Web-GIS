import ezdxf
from io import StringIO

def geojson_to_dxf(geojson_data: dict) -> bytes:
    """
    VWorld WFS 등에서 받은 GeoJSON 데이터를 DXF 파일 바이너리로 변환합니다.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    features = geojson_data.get('features', [])
    
    # 레이어 설정 (기본적으로 URBAN_AREA 레이어 생성)
    doc.layers.add("URBAN_AREA", color=1) # 1: 빨간색
    
    for feature in features:
        geom = feature.get('geometry', {})
        if not geom:
            continue
            
        gtype = geom.get('type')
        coords = geom.get('coordinates', [])
        
        def add_ring(ring):
            if not ring: return
            # GeoJSON 좌표는 [경도(LNG), 위도(LAT)] 순서입니다.
            points = [(pt[0], pt[1]) for pt in ring]
            msp.add_lwpolyline(points, close=True, dxfattribs={'layer': 'URBAN_AREA'})
            
        if gtype == 'Polygon':
            for ring in coords:
                add_ring(ring)
        elif gtype == 'MultiPolygon':
            for poly in coords:
                for ring in poly:
                    add_ring(ring)
                    
    # 메모리 버퍼에 기록
    stream = StringIO()
    doc.write(stream)
    return stream.getvalue().encode('utf-8')
