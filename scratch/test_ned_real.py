import requests
import json

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"
PNU = "1114010300100310000" # Seoul City Hall

# 1. Land Ledger Test
url = "https://api.vworld.kr/ned/data/ladfrlList"
params = {
    "key": VWORLD_KEY, "domain": "http://localhost", "pnu": PNU,
    "format": "json"
}
res = requests.get(url, params=params)
print("--- Land Ledger Response ---")
try:
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))
except:
    print(res.text)

# 2. Land Price Test
url_price = "https://api.vworld.kr/ned/data/getIndvdLandPriceAttr"
params_price = params.copy()
params_price["stdrYear"] = "2023"
res_price = requests.get(url_price, params=params_price)
print("\n--- Land Price Response ---")
try:
    print(json.dumps(res_price.json(), indent=2, ensure_ascii=False))
except:
    print(res_price.text)
