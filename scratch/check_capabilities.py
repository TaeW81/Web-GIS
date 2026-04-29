import requests
VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"
url = "https://api.vworld.kr/req/wfs"
params = {
    "key": VWORLD_KEY,
    "SERVICE": "WFS",
    "version": "1.1.0",
    "request": "GetCapabilities",
    "domain": "http://localhost"
}
resp = requests.get(url, params=params)
with open("scratch/wfs_capabilities.xml", "w", encoding="utf-8") as f:
    f.write(resp.text)
print("Capabilities saved.")
