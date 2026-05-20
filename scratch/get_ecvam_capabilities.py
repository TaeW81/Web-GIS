import requests

key = 'GGDM-AU7W-FRD0-UPSC'
url = f"https://ecvam.neins.go.kr/apicall.do?APIKEY={key}&SERVICE=WMS&REQUEST=GetCapabilities"

try:
    res = requests.get(url, timeout=10, verify=False)
    print(f"Status: {res.status_code}")
    print(f"Content Type: {res.headers.get('Content-Type')}")
    if res.status_code == 200:
        with open('scratch/ecvam_capabilities.xml', 'w', encoding='utf-8') as f:
            f.write(res.text)
        print("Capabilities saved to scratch/ecvam_capabilities.xml")
    else:
        print(res.text[:500])
except Exception as e:
    print(f"Error: {e}")
