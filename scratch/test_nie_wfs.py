import requests
NIE_KEY = "0b1a73c4402f5cc749ca03709d2850131f4c1e62b27c87ea7bdbe8dd19299bd7"
url = "https://apis.data.go.kr/B553084/ecoapi/EcologyzmpService/wfs/getEcologyzmpWMS" # Use WMS endpoint first
params = {
    "ServiceKey": NIE_KEY,
    "SERVICE": "WFS",
    "version": "1.1.0",
    "request": "GetCapabilities"
}
try:
    resp = requests.get(url, params=params, timeout=30)
    print(f"Status Code: {resp.status_code}")
    print(resp.text[:500])
    if "WFS_Capabilities" in resp.text:
        print("WFS IS SUPPORTED by NIE!")
except Exception as e:
    print(f"Error: {e}")
