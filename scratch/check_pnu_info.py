import requests
import json

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"
PNU = "4833025322105150011"

def get_pnu_info(pnu):
    # NED API only, as it's more reliable for attributes
    url = "https://api.vworld.kr/ned/data/ladfrlList"
    params = {
        "key": VWORLD_KEY,
        "domain": "http://localhost",
        "pnu": pnu,
        "format": "json"
    }
    
    try:
        print(f"Requesting info for PNU: {pnu}")
        res = requests.get(url, params=params, timeout=30)
        data = res.json()
        
        if "ladfrlVOList" in data:
            vo = data["ladfrlVOList"]
            if isinstance(vo, dict) and "ladfrlVOList" in vo:
                info_list = vo["ladfrlVOList"]
                if isinstance(info_list, list) and len(info_list) > 0:
                    info = info_list[0]
                elif isinstance(info_list, dict):
                    info = info_list
                else:
                    print("No info found in list")
                    return
                
                print("\n--- Result ---")
                print(f"PNU: {pnu}")
                print(f"소재지: {info.get('ldCodeNm')}")
                print(f"지목: {info.get('lndcgrCodeNm')}")
                print(f"면적: {info.get('lndpclAr')} sqm")
                print(f"소유: {info.get('posesnSeCodeNm')}")
            else:
                print("Structure not as expected")
                print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print("PNU not found in NED")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_pnu_info(PNU)
