import requests

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"
url = "https://api.vworld.kr/req/data"
params = {
    "service": "data", "request": "GetFeature", "data": "LP_PA_CBND_BUBUN",
    "key": VWORLD_KEY, "domain": "http://localhost", "size": "1"
}
res = requests.get(url, params=params)
data = res.json()
print(data.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [{}])[0].get("properties", {}))
