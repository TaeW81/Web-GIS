import requests

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"
PNU = "4145011600100150000" # Example PNU (Hanam-si, Deokpung-dong)

# 1. Land Ledger Test
url = "https://api.vworld.kr/ned/data/ladfrlList"
params = {
    "key": VWORLD_KEY, "domain": "http://localhost", "pnu": PNU,
    "format": "json", "numOfRows": "10", "pageNo": "1"
}
res = requests.get(url, params=params)
print("--- Land Ledger ---")
print(f"Status: {res.status_code}")
print(res.text[:500])

# 2. Land Price Test
url_price = "https://api.vworld.kr/ned/data/getIndvdLandPriceAttr"
params_price = params.copy()
params_price["stdrYear"] = "2023"
res_price = requests.get(url_price, params=params_price)
print("\n--- Land Price ---")
print(f"Status: {res_price.status_code}")
print(res_price.text[:500])
