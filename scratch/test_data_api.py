import requests
import json

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"
DATA_CODE = "LT_C_UM001"
# 서울 근처 BBOX (minLon, minLat, maxLon, maxLat) - Data API는 Lon, Lat 순서
BBOX = "127.0,37.5,127.1,37.6"

url = "https://api.vworld.kr/req/data"
params = {
    "key": VWORLD_KEY,
    "domain": "http://localhost",
    "service": "data",
    "version": "2.0",
    "request": "getfeature",
    "format": "json",
    "size": "100",
    "data": DATA_CODE,
    "geomfilter": f"BOX({BBOX})"
}

print(f"Requesting Data API: {url}")
try:
    resp = requests.get(url, params=params, timeout=30)
    print(f"Status Code: {resp.status_code}")
    data = resp.json()
    status = data.get("response", {}).get("status")
    print(f"Response Status: {status}")
    if status == "OK":
        features = data.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [])
        print(f"Feature count: {len(features)}")
    else:
        print("Error Response:", data)
except Exception as e:
    print(f"Error: {e}")
