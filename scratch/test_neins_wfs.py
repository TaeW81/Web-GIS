import requests
APIKEY = "GGDM-AU7W-FRD0-UPSC"
url = "https://ecvam.neins.go.kr/apicall.do"
params = {
    "APIKEY": APIKEY,
    "SERVICE": "WFS",
    "version": "1.1.0",
    "request": "GetCapabilities"
}
try:
    resp = requests.get(url, params=params, timeout=30)
    print(f"Status Code: {resp.status_code}")
    print(resp.text[:500])
    if "WFS_Capabilities" in resp.text:
        print("WFS IS SUPPORTED by NEINS apicall.do!")
except Exception as e:
    print(f"Error: {e}")
