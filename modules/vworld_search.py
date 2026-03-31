import requests

def search_place(query: str, api_key: str) -> dict:
    """
    VWorld Search API를 사용하여 장소(PLACE)를 검색하고 첫 번째 결과의 위경도(EPSG:4326)를 반환합니다.

    Args:
        query: 검색할 장소명 (예: '야탑역')
        api_key: VWorld API 키

    Returns:
        dict: {'lat': float, 'lon': float, 'name': str} 또는 검색 실패 시 None
    """
    url = "https://api.vworld.kr/req/search"
    params = {
        "page": "1",
        "type": "PLACE",
        "request": "search",
        "apiKey": api_key,
        "domain": "http://localhost",
        "crs": "EPSG:4326",  # Folium이 사용하는 위경도 좌표계 반환
        "query": query,
        "size": "1"  # 첫 번째 결과만 가져옴
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("response", {}).get("status") == "OK":
                items = data["response"]["result"]["items"]
                if items:
                    point = items[0]["point"]
                    return {
                        "lat": float(point["y"]),
                        "lon": float(point["x"]),
                        "name": items[0]["title"]
                    }
    except Exception as e:
        print(f"VWorld Search API Error: {e}")
        
    return None
