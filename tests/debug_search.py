import requests

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"

def check_search_api(query):
    print(f"--- Searching with Search API (Query: {query}) ---")
    url = "https://api.vworld.kr/req/search"
    params = {
        "service": "search",
        "request": "search",
        "type": "ADDRESS",
        "category": "parcel",
        "query": query,
        "key": VWORLD_KEY,
        "domain": "http://localhost",
        "size": "1"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        print(f"Status: {r.status_code}")
        data = r.json()
        status = data.get('response', {}).get('status')
        print(f"VWorld Status: {status}")
        
        if status == "OK":
            items = data.get('response', {}).get('result', {}).get('items', [])
            if items:
                point = items[0].get('point')
                print(f"Found Point: {point}")
                return point
        else:
            print(f"Response: {data}")
    except Exception as e:
        print(f"Error: {e}")
    return None

if __name__ == "__main__":
    # 5119010700100670001 (신코드)
    check_search_api("5119010700100670001")
    # 4219010700100670001 (구코드)
    check_search_api("4219010700100670001")
    # 주소로 검색
    check_search_api("강원특별자치도 태백시 통동 67-1")
