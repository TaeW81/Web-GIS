import requests
from PIL import Image
import io

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"

params = {
    "service": "image",
    "request": "getmap",
    "key": VWORLD_KEY,
    "center": "129.011,37.172",
    "zoom": "11",
    "size": "800,800",
    "basemap": "PHOTO", # Corrected
    "layers": "LT_C_LHBLPN",
    "crs": "EPSG:4326",
    "format": "png"
}

res = requests.get("http://api.vworld.kr/req/image", params=params)
if res.status_code == 200 and len(res.content) > 1000:
    Image.open(io.BytesIO(res.content)).save("test_image_service_photo.png")
    print("Success with PHOTO")
else:
    print("Error:", res.text)
