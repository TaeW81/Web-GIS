import requests
from pyproj import Transformer
import json

bbox_4326 = [126.9, 37.5, 127.0, 37.6]
t = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
min_x, min_y = t.transform(bbox_4326[0], bbox_4326[1])
max_x, max_y = t.transform(bbox_4326[2], bbox_4326[3])

url = "https://api.vworld.kr/req/wfs"
params = {
    "key": "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1",
    "domain": "http://localhost",
    "SERVICE": "WFS",
    "version": "1.1.0",
    "request": "GetFeature",
    "TYPENAME": "lt_l_moctlink",
    "BBOX": f"{min_x},{min_y},{max_x},{max_y}",
    "CQL_FILTER": "rd_rank_h='고속국도' OR rd_rank_h='일반국도'",
    "outputFormat": "application/json",
    "maxFeatures": 1000
}
res = requests.get(url, params=params)
data = res.json()
print("Features:", len(data.get("features", [])))
