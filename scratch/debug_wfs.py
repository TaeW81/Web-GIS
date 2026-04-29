import requests
import json

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"
TYPENAME = "lt_c_um001"
# 서울 근처 BBOX (minLat, minLon, maxLat, maxLon)
BBOX = "37.5,127.0,37.6,127.1"

url = "https://api.vworld.kr/req/wfs"
params = {
    "key": VWORLD_KEY,
    "SERVICE": "WFS",
    "version": "1.1.0",
    "request": "GetFeature",
    "TYPENAME": TYPENAME,
    "BBOX": f"{BBOX},EPSG:4326",
    "SRSNAME": "EPSG:4326",
    "output": "application/json",
    "domain": "http://localhost"
}

print(f"Requesting URL: {url}")
print(f"Params: {params}")

try:
    resp = requests.get(url, params=params, timeout=30)
    print(f"Status Code: {resp.status_code}")
    print(f"Headers: {resp.headers.get('Content-Type')}")
    
    if "json" in resp.headers.get("Content-Type", "").lower():
        data = resp.json()
        features = data.get("features", [])
        print(f"Feature count: {len(features)}")
        if features:
            print("First feature sample:", json.dumps(features[0], indent=2, ensure_ascii=False))
    else:
        print("Response is not JSON. Content:")
        print(resp.text[:500])
except Exception as e:
    print(f"Error: {e}")
