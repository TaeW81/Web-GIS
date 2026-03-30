"""
토지속성 분석기 — 공시지가, 지목 등 토지 기본 정보 수집

데이터 소스: 브이월드 Data API (LP_PA_CBND_BUBUN)
"""
import requests
from analyzers.base_analyzer import BaseAnalyzer
from config import VWORLD_DATA_URL, VWORLD_DOMAIN, CADASTRAL_LAYER


class LandAttributeAnalyzer(BaseAnalyzer):
    name = "토지속성 (공시지가/지목)"
    description = "PNU별 공시지가, 지목 등 토지 기본 속성을 조회합니다."

    def analyze(self, pnu_list, api_key):
        """
        PNU 리스트의 각 필지에 대해 공시지가, 지목을 조회합니다.
        
        Returns:
            list[dict]: [{"PNU": ..., "주소": ..., "지목": ..., "공시지가(원/㎡)": ...}, ...]
        """
        results = []
        
        for parcel in pnu_list:
            pnu = parcel["PNU"]
            address = parcel["주소"]
            
            params = {
                "service": "data",
                "request": "GetFeature",
                "data": CADASTRAL_LAYER,
                "key": api_key,
                "domain": VWORLD_DOMAIN,
                "attrFilter": f"pnu:like:{pnu}",
            }
            
            try:
                res = requests.get(VWORLD_DATA_URL, params=params, timeout=10)
                data = res.json()
                
                if data.get("response", {}).get("status") == "OK":
                    features = data["response"]["result"]["featureCollection"]["features"]
                    props = features[0]["properties"]
                    
                    results.append({
                        "PNU": pnu,
                        "주소": address,
                        "지번": parcel.get("지번", ""),
                        "지목": props.get("jimok", "-"),
                        "공시지가(원/㎡)": props.get("pnilp", "-"),
                    })
                else:
                    # API에서 데이터를 못 찾은 경우에도 기본 정보는 기록
                    results.append({
                        "PNU": pnu,
                        "주소": address,
                        "지번": parcel.get("지번", ""),
                        "지목": "-",
                        "공시지가(원/㎡)": "-",
                    })
            except Exception:
                results.append({
                    "PNU": pnu,
                    "주소": address,
                    "지번": parcel.get("지번", ""),
                    "지목": "조회오류",
                    "공시지가(원/㎡)": "조회오류",
                })
        
        return results

    def get_columns(self):
        return ["PNU", "주소", "지번", "지목", "공시지가(원/㎡)"]
