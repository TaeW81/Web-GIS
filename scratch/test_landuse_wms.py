import requests
from PIL import Image
import io

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"
center = (127.0, 37.5) # Seoul area often has many plans
# BBox around center (approx 10km)
bbox = "126.9,37.4,127.1,37.6"

params = {
    "service": "WMS",
    "request": "GetMap",
    "version": "1.3.0",
    "layers": "LT_C_LHBLPN",
    "crs": "EPSG:4326",
    "bbox": bbox,
    "width": "800",
    "height": "800",
    "format": "image/png",
    "key": VWORLD_KEY,
    "domain": "http://localhost",
    "transparent": "true"
}

print("Testing Land Use Plan WMS...")
res = requests.get("http://api.vworld.kr/req/wms", params=params)
if res.status_code == 200:
    print("Success! Length:", len(res.content))
    if len(res.content) > 1000:
        img = Image.open(io.BytesIO(res.content))
        img.save("test_landuse_wms.png")
        print("Saved.")
    else:
        print("Empty image (likely no data in this area).")
else:
    print("Error:", res.status_code, res.text)
