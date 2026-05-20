import requests
import json
from config import VWORLD_KEY

url = "https://api.vworld.kr/req/wfs"
params = {
    "key": VWORLD_KEY,
    "domain": "http://localhost",
    "SERVICE": "WFS",
    "version": "1.1.0",
    "request": "GetFeature",
    "TYPENAME": "lt_l_moctlink",
    "BBOX": "14124000,4500000,14130000,4510000",
    "outputFormat": "application/json",
    "maxFeatures": 10000
}
res = requests.get(url, params=params)
if res.status_code == 200:
    try:
        data = res.json()
        print(len(data.get("features", [])))
        for f in data.get("features", []):
            rank = f["properties"].get("rd_rank_h", "")
            if "국도" in rank or "고속" in rank:
                print(rank, f["properties"].get("road_no"))
    except:
        print(res.text[:500])
else:
    print(res.status_code, res.text[:500])
