"""
DXF 파일 파싱 및 좌표 변환 모듈

역할:
  - ezdxf로 DXF 파일에서 LWPOLYLINE(구역계) 추출
  - pyproj로 CAD 좌표(EPSG:5186) → GPS 좌표(EPSG:4326) 변환
  - shapely Polygon 객체 + GPS 좌표 리스트 반환
"""
import ezdxf
from pyproj import Transformer
from shapely.geometry import Polygon
from config import SOURCE_CRS, TARGET_CRS


def parse_dxf(file_path, source_crs=None, target_crs=None):
    """
    DXF 파일을 읽어 GPS 좌표로 변환된 Polygon과 좌표 리스트를 반환합니다.
    
    Args:
        file_path (str): DXF 파일 경로
        source_crs (str): 원본 좌표계 (기본값: config.SOURCE_CRS)
        target_crs (str): 변환 좌표계 (기본값: config.TARGET_CRS)
    
    Returns:
        dict: {
            "polygon": shapely.Polygon,        # 구역계 폴리곤 객체
            "gps_points": [(lat, lon), ...],    # Folium용 (위도, 경도) 리스트
            "lonlat_points": [(lon, lat), ...], # Shapely용 (경도, 위도) 리스트
            "center": (lat, lon),               # 중심점 (지도 카메라 위치)
            "num_vertices": int                 # 꼭짓점 개수
        }
        또는 에러 시 None
    """
    src = source_crs or SOURCE_CRS
    tgt = target_crs or TARGET_CRS
    
    try:
        # 1. DXF 파일 열기 및 폴리라인 추출
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()
        polylines = msp.query('LWPOLYLINE')
        
        if not polylines:
            raise ValueError("도면에서 폴리라인(구역계)을 찾을 수 없습니다.")
        
        # 첫 번째 폴리라인의 꼭짓점 좌표 추출
        boundary = polylines[0]
        cad_points = list(boundary.get_points('xy'))
        
        # 2. 좌표 변환 (CAD → GPS)
        transformer = Transformer.from_crs(src, tgt, always_xy=True)
        
        gps_points = []      # Folium용: (위도, 경도) 순서
        lonlat_points = []   # Shapely/API용: (경도, 위도) 순서
        
        for x, y in cad_points:
            lon, lat = transformer.transform(x, y)
            gps_points.append((lat, lon))
            lonlat_points.append((lon, lat))
        
        # 3. Shapely 폴리곤 생성
        polygon = Polygon(lonlat_points)
        
        # 4. 중심점 계산 (지도 카메라 위치)
        center_lat = sum(p[0] for p in gps_points) / len(gps_points)
        center_lon = sum(p[1] for p in gps_points) / len(gps_points)
        
        return {
            "polygon": polygon,
            "gps_points": gps_points,
            "lonlat_points": lonlat_points,
            "center": (center_lat, center_lon),
            "num_vertices": len(cad_points),
        }
    
    except IOError:
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
    except Exception as e:
        raise RuntimeError(f"DXF 파싱 중 오류: {e}")
