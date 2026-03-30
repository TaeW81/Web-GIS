import requests

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"

def check_vworld_raw():
    url = "https://api.vworld.kr/req/data"
    params = {
        "service": "data", "request": "GetFeature", "data": "LP_PA_CBND_BUBUN",
        "key": VWORLD_KEY, "domain": "http://localhost", "attrFilter": "pnu:like:42110", "size": "1"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        print(f"Status Code: {r.status_code}")
        print("Raw Response Fragment:")
        print(r.text[:500])
        try:
            data = r.json()
            print("Status in JSON:", data.get('response', {}).get('status'))
        except:
            print("Failed to parse JSON")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_vworld_raw()
