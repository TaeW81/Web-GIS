import requests
from shapely.wkt import loads
from shapely.geometry import shape

# 1. 브이월드 인증키
VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"

# 2. 방금 전 단계에서 성공해서 얻어낸 결과물(WKT 문자열)을 여기에 그대로 붙여넣습니다.
# (너무 길어서 일부만 예시로 넣었습니다. 성공하신 전체 POLYGON 문자열로 교체하세요!)
WKT_STRING = "POLYGON ((126.85587673215356 37.40810437017179, 126.8557588955501 37.408119274164655, 126.85560089642985 37.40813625261782, 126.85587673215356 37.40810437017179))"

def extract_intersecting_pnus(wkt_polygon, api_key):
    print("1. 구역계 데이터를 분석합니다...")
    
    # 텍스트(WKT)를 파이썬이 계산할 수 있는 '도형(Polygon)' 객체로 변환
    try:
        my_boundary = loads(wkt_polygon)
    except Exception as e:
        print(f"❌ WKT 분석 에러: {e}")
        return None
    
    # 도형을 감싸는 최소/최개 사각형(Bounding Box) 좌표 구하기
    min_x, min_y, max_x, max_y = my_boundary.bounds
    print(f"-> 구역계 사각형 범위: 좌하({min_x:.4f}, {min_y:.4f}) ~ 우상({max_x:.4f}, {max_y:.4f})")
    
# 브이월드 서버에 보낼 사각형 필터 만들기 (콤마로만 구분)
    box_filter = f"BOX({min_x},{min_y},{max_x},{max_y})"
    
    print("\n2. 브이월드에서 해당 범위의 지적도를 통째로 가져옵니다...")
    url = "https://api.vworld.kr/req/data"
    params = {
        "service": "data",
        "request": "GetFeature",
        "data": "LP_PA_CBND_BUBUN", # 지적도 레이어
        "key": api_key,
        "domain": "http://localhost",
        "geomFilter": box_filter,   # 사각형 범위로 검색!
        "geometry": "true",         # 지적도의 폴리곤 모양도 같이 달라고 요청
        "size": "1000"              # 최대 1000개 필지까지 한 번에 가져오기
    }
    
    try:
        res = requests.get(url, params=params, timeout=15)
        data = res.json()
        
        status = data.get('response', {}).get('status')
        if status != "OK":
            print(f"-> 서버 응답 오류: {status}")
            if 'error' in data.get('response', {}):
                print(f"   내용: {data['response']['error'].get('text')}")
            return None

        features = data.get('response', {}).get('result', {}).get('featureCollection', {}).get('features', [])
        print(f"-> 서버에서 총 {len(features)}개의 필지 데이터를 긁어왔습니다.")
        
        print("\n3. 내 구역계와 진짜로 겹치는 필지만 정밀 필터링합니다 (가위질)...")
        included_parcels = []
        
        for feat in features:
            props = feat['properties']
            pnu = props.get('pnu')
            jibun = props.get('jibun')   # 지번 (예: 산 12-3)
            addr = props.get('addr')     # 주소
            
            # 지적도의 모양(Polygon) 정보 가져오기
            geom = feat.get('geometry')
            if not geom:
                continue
                
            # 지적도를 파이썬 도형 객체로 변환
            parcel_shape = shape(geom)
            
            # 핵심! 내 구역계(my_boundary)와 이 지적도(parcel_shape)가 교차(intersects)하는가?
            if my_boundary.intersects(parcel_shape):
                # 겹치는 부분을 잘라내서 면적 계산 (선택사항, 나중에 편입면적 구할 때 유용)
                # intersection_area = my_boundary.intersection(parcel_shape).area
                
                included_parcels.append({
                    "PNU": pnu,
                    "주소": addr,
                    "지번": jibun
                })
        
        print(f"\n✅ 정밀 필터링 완료! 총 {len(included_parcels)}개의 필지가 구역계에 포함됩니다.")
        
        # 결과 출력해보기 (최대 10개만)
        print("-" * 40)
        for i, parcel in enumerate(included_parcels[:10]):
            print(f"[{i+1}] PNU: {parcel['PNU']} | 주소: {parcel['주소']}")
        
        if len(included_parcels) > 10:
            print(f"... 외 {len(included_parcels) - 10}개 필지 더 있음")
            
        return included_parcels

    except Exception as e:
        print(f"❌ 에러 발생: {e}")

if __name__ == "__main__":
    # 코드 실행!
    extract_intersecting_pnus(WKT_STRING, VWORLD_KEY)
