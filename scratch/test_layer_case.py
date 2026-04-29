import requests

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"
layers = "LT_C_LHBLPN"
# Check both cases
for l in [layers, layers.lower()]:
    params = {
        "SERVICE": "WMS",
        "REQUEST": "GetMap",
        "VERSION": "1.3.0",
        "LAYERS": l,
        "CRS": "EPSG:3857",
        "BBOX": "-20037508.34,-20037508.34,20037508.34,20037508.34", # Global bbox just to see if it responds
        "WIDTH": "256",
        "HEIGHT": "256",
        "FORMAT": "image/png",
        "KEY": VWORLD_KEY,
        "DOMAIN": "http://localhost"
    }
    res = requests.get("https://api.vworld.kr/req/wms", params=params)
    print(f"Testing {l}: Status {res.status_code}, Content-Length {len(res.content)}")
    if b"InvalidLayer" in res.content:
        print(f"Result: Invalid Layer name for {l}")
    else:
        print(f"Result: Success (or other error) for {l}")
