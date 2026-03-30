import requests
import json

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"
url = "http://api.vworld.kr/req/data"

def debug_vworld():
    # 1. 51190 (태백 신코드)로 검색
    print("--- Searching with 51190 (HTTPS) ---")
    p1 = {
        "service": "data", "request": "GetFeature", "data": "LP_PA_CBND_BUBUN",
        "key": VWORLD_KEY, "domain": "http://localhost", "attrFilter": "pnu:like:51190", "size": "1"
    }
    try:
        r1 = requests.get("https://api.vworld.kr/req/data", params=p1, timeout=10)
        print(f"Status: {r1.status_code}")
        print(r1.json().get('response', {}).get('status'))
        if r1.json().get('response', {}).get('result'):
            print("Found Feature with 51190!")
    except Exception as e:
        print(f"Error 1: {e}")
    
    # 2. 42190 (태백 구코드)로 검색
    print("\n--- Searching with 42190 (HTTPS) ---")
    p2 = {
        "service": "data", "request": "GetFeature", "data": "LP_PA_CBND_BUBUN",
        "key": VWORLD_KEY, "domain": "http://localhost", "attrFilter": "pnu:like:42190", "size": "1"
    }
    try:
        r2 = requests.get("https://api.vworld.kr/req/data", params=p2, timeout=10)
        print(f"Status: {r2.status_code}")
        print(r2.json().get('response', {}).get('status'))
        if r2.json().get('response', {}).get('result'):
            print("Found Feature with 42190!")
    except Exception as e:
        print(f"Error 2: {e}")

    # 3. 다른 알려진 레이어로 검색 (동작 여부 확인)
    print("\n--- Searching Urban Zoning (LT_C_UQ111) ---")
    p3 = {
        "service": "data", "request": "GetFeature", "data": "LT_C_UQ111",
        "key": VWORLD_KEY, "domain": "http://localhost", "size": "1"
    }
    r3 = requests.get(url, params=p3)
    print(f"Status: {r3.status_code}")
    print(r3.json().get('response', {}).get('status'))

if __name__ == "__main__":
    debug_vworld()
