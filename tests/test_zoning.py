import requests

# 1. 내가 브이월드에서 발급받은 인증키 (여기에 본인의 키를 넣으세요!)
VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"

# 2. 검색할 대상 (주소 또는 PNU)
# 예시: 강원특별자치도 태백시 통동 67-1 (보고서의 대상지)
TARGET_ADDRESS = "강원특별자치도 태백시 통동 67-1"

def get_zoning_by_address(address, api_key):
    print(f"[{address}] 용도지역 조회를 시작합니다...")
    
    # 1단계: 주소 검색 API를 통해 해당 위치의 좌표(X, Y) 가져오기
    # PNU 필터링이 불안정할 경우 주소 기반 검색이 가장 정확합니다.
    search_url = "https://api.vworld.kr/req/search"
    search_params = {
        "service": "search",
        "request": "search",
        "type": "ADDRESS",
        "category": "parcel",
        "query": address,
        "key": api_key,
        "domain": "http://localhost",
        "size": "1"
    }
    
    try:
        res = requests.get(search_url, params=search_params, timeout=10)
        data = res.json()
        
        if data.get('response', {}).get('status') != "OK":
            print(f"[실패] 주소 검색에 실패했습니다. (상태: {data.get('response', {}).get('status')})")
            return

        item = data['response']['result']['items'][0]
        point = item.get('point', {})
        x, y = point.get('x'), point.get('y')
        
        if not x or not y:
            print("[실패] 해당 주소의 좌표 정보를 가져올 수 없습니다.")
            return

        print(f"-> 좌표 확인 완료: (X:{x}, Y:{y})")
        geom_filter = f"POINT({x} {y})"

        # 2단계: 데이터 API를 통해 용도지역 공간 검색 (4개 주요 레이어)
        data_url = "https://api.vworld.kr/req/data"
        zoning_layers = {
            "LT_C_UQ111": "도시지역",
            "LT_C_UQ112": "관리지역",
            "LT_C_UQ113": "농림지역",
            "LT_C_UQ114": "자연환경보전지역"
        }
        
        found_zones = []
        for layer_code, layer_name in zoning_layers.items():
            zoning_params = {
                "service": "data",
                "request": "GetFeature",
                "data": layer_code,
                "key": api_key,
                "domain": "http://localhost",
                "geomFilter": geom_filter,
                "geometry": "false",
                "size": "10" 
            }
            
            z_res = requests.get(data_url, params=zoning_params, timeout=10)
            if z_res.status_code == 200:
                z_data = z_res.json()
                features = z_data.get('response', {}).get('result', {}).get('featureCollection', {}).get('features', [])
                for feat in features:
                    uname = feat['properties'].get('uname')
                    if uname:
                        found_zones.append(f"{layer_name}({uname})")
        
        if found_zones:
            # 중복 제거 및 정렬 후 출력
            unique_zones = sorted(list(set(found_zones)))
            print(f"[성공] 확인된 용도지역: {', '.join(unique_zones)}")
        else:
            print("[알림] 해당 위치에서 조회된 용도지역 정보가 없습니다.")

    except Exception as e:
        print(f"[오류] 실행 중 에러가 발생했습니다: {e}")

if __name__ == "__main__":
    get_zoning_by_address(TARGET_ADDRESS, VWORLD_KEY)
