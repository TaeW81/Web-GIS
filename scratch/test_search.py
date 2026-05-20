import requests
import json
from config import VWORLD_KEY

bbox = "126.9,37.5,127.0,37.6"
url = "https://api.vworld.kr/req/search"
params = {
    "service": "search",
    "request": "search",
    "version": "2.0",
    "crs": "EPSG:4326",
    "bbox": bbox,
    "size": 100,
    "type": "PLACE",
    "query": "산",
    "key": VWORLD_KEY,
    "format": "json",
    "errorformat": "json"
}
res = requests.get(url, params=params)
print("산:", res.status_code, res.json())

params["query"] = "IC"
res = requests.get(url, params=params)
print("IC:", res.status_code, res.json())
