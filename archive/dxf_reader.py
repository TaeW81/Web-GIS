import ezdxf
from pyproj import Transformer
from shapely.geometry import Polygon

# 1. 테스트용 DXF 파일 경로 (캐드에서 폴리라인으로 그린 구역계 파일)
DXF_FILE_PATH = "test_boundary.dxf"

def read_dxf_and_convert(file_path):
    print(f"[{file_path}] DXF 파일 분석을 시작합니다...")
    
    try:
        # DXF 파일 열기
        doc = ezdxf.readfile(file_path)
        msp = doc.modelspace()
        
        # 도면에서 폴리라인(LWPOLYLINE) 찾기
        polylines = msp.query('LWPOLYLINE')
        
        if not polylines:
            print("❌ 도면에서 폴리라인(구역계)을 찾을 수 없습니다.")
            return None
        
        # 첫 번째 폴리라인의 꼭짓점(Vertex) 좌표 추출
        boundary_entity = polylines[0]
        # ezdxf의 최신 문법에 맞추어 점 추출. get_points('xy')는 최신 ezdxf API에 따라 다를 수 있으나 사용자 제공 코드 유지
        try:
            cad_points = boundary_entity.get_points('xy')
        except AttributeError:
            # get_points가 없을 경우 대체 방법 (ezdxf 최신 버전 호환)
            cad_points = [(p[0], p[1]) for p in boundary_entity.get_points(format='xy')]
            
        print(f"-> 캐드 좌표 추출 완료: 총 {len(cad_points)}개의 꼭짓점 발견")
        
        # --- 좌표 변환 세팅 ---
        # 실무 캐드 도면은 보통 중부원점(EPSG:5186) 또는 구소삼각원점(EPSG:5174)을 씁니다.
        # 브이월드 등 API는 GPS 좌표인 WGS84(EPSG:4326)를 씁니다.
        # 여기서는 최신 지적도에서 많이 쓰는 GRS80 중부원점(EPSG:5186)을 가정합니다.
        transformer = Transformer.from_crs("EPSG:5186", "EPSG:4326", always_xy=True)
        
        gps_points = []
        for x, y in cad_points:
            # 캐드 좌표(X,Y) -> 위경도(Lon,Lat)로 변환
            lon, lat = transformer.transform(x, y)
            gps_points.append((lon, lat))
            
        print("-> GPS 위경도 좌표로 변환 완료!")
        
        # 변환된 좌표로 '면(Polygon)' 객체 생성
        boundary_polygon = Polygon(gps_points)
        
        # 결과 확인 (WKT 형태의 문자열로 출력)
        print("\n✅ 최종 생성된 구역계 폴리곤 데이터(WKT 형식):")
        print(boundary_polygon.wkt)
        
        return boundary_polygon

    except IOError:
        print(f"❌ 파일을 찾을 수 없습니다: {file_path}")
    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")

if __name__ == "__main__":
    polygon_data = read_dxf_and_convert(DXF_FILE_PATH)
