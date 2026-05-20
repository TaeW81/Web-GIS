import requests
import json
from config import VWORLD_KEY

bbox = "126.9,37.5,127.0,37.6"
url = "https://api.vworld.kr/req/wfs"
params = {
    "key": VWORLD_KEY,
    "domain": "http://localhost",
    "SERVICE": "WFS",
    "version": "1.1.0",
    "request": "GetFeature",
    "TYPENAME": "lt_l_moctlink",
    "BBOX": bbox,
    "outputFormat": "application/json",
    "maxFeatures": 1000
}
res = requests.get(url, params=params)
print("moctlink:", res.status_code, len(res.json().get('features', [])) if res.status_code==200 else res.text)

params["TYPENAME"] = "lt_c_ademd"
res = requests.get(url, params=params)
print("ademd:", res.status_code, len(res.json().get('features', [])) if res.status_code==200 else res.text)
