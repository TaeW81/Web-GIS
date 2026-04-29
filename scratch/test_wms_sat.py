import requests
from PIL import Image
import io

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1" # From config.py
# 태백시 통동 주변 BBox (약 10km)
bbox = "128.9,37.1,129.1,37.3" 

params = {
    "service": "WMS",
    "request": "GetMap",
    "version": "1.3.0",
    "layers": "vworld_2dbase", # Try base first
    "crs": "EPSG:4326",
    "bbox": bbox,
    "width": "800",
    "height": "800",
    "format": "image/png",
    "key": VWORLD_KEY,
    "domain": "http://localhost"
}

print("Testing VWorld WMS...")
res = requests.get("http://api.vworld.kr/req/wms", params=params)
if res.status_code == 200:
    print("Success! Content length:", len(res.content))
    img = Image.open(io.BytesIO(res.content))
    img.save("test_wms.png")
else:
    print("Failed. Status:", res.status_code, res.text)

# Try satellite (unofficial layer name often used in some proxies)
params["layers"] = "vworld_sattellite"
print("Testing VWorld Satellite WMS...")
res = requests.get("http://api.vworld.kr/req/wms", params=params)
if res.status_code == 200:
    print("Satellite WMS Success!")
    img = Image.open(io.BytesIO(res.content))
    img.save("test_wms_sat.png")
else:
    print("Satellite WMS Failed.")
