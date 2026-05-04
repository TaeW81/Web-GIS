
import requests
import json
import sys

# Ensure UTF-8 output for Windows terminal
sys.stdout.reconfigure(encoding='utf-8')

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"
VWORLD_DOMAIN = "http://localhost"

def get_land_ledger_info(pnu):
    url = "https://api.vworld.kr/ned/data/ladfrlList"
    params = {
        "key": VWORLD_KEY,
        "domain": VWORLD_DOMAIN,
        "pnu": pnu,
        "format": "json"
    }
    
    resp = requests.get(url, params=params)
    data = resp.json()
    
    def find_info(data):
        if not data: return None
        if isinstance(data, list) and len(data) > 0: return data[0]
        if isinstance(data, dict):
            if "ldCodeNm" in data or "lndcgrCodeNm" in data: return data
            for k in ["ladfrlVOList", "ladfrlVO", "item"]:
                if k in data:
                    r = find_info(data[k])
                    if r: return r
        return None
        
    return find_info(data)

pnu = "4833025322108410041"
address = "경상남도 양산시 물금읍 증산리 841-41"

info = get_land_ledger_info(pnu)
if info:
    jimok = info.get("lndcgrCodeNm")
    area = info.get("lndpclAr")
    print(f"Address: {address}")
    print(f"Land Category (Jimok): {jimok}")
    print(f"Area: {area} m2")
else:
    print("Land ledger info not found.")
