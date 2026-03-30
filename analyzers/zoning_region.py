"""
용도지역 분석기 — 4대 용도지역 조회

데이터 소스: 브이월드 Data API
  - LT_C_UQ111: 도시지역
  - LT_C_UQ112: 관리지역
  - LT_C_UQ113: 농림지역
  - LT_C_UQ114: 자연환경보전지역

방식: 주소 → 좌표 검색(Search API) → 좌표로 4개 용도지역 레이어 공간 검색
"""
import requests
from analyzers.base_analyzer import BaseAnalyzer
from config import (
    VWORLD_DATA_URL,
    VWORLD_SEARCH_URL,
    VWORLD_DOMAIN,
    ZONING_LAYERS,
)


class ZoningRegionAnalyzer(BaseAnalyzer):
    name = "용도지역"
    description = "4대 용도지역(도시/관리/농림/자연환경보전)을 조회합니다."

    def analyze(self, pnu_list, api_key):
        """
        PNU 리스트의 각 필지에 대해 용도지역을 조회합니다.
        
        Returns:
            list[dict]: [{"PNU": ..., "주소": ..., "용도지역": ...}, ...]
        """
        results = []
        
        for parcel in pnu_list:
            pnu = parcel["PNU"]
            address = parcel["주소"]
            
            # 1단계: 주소로 좌표(X, Y) 검색
            point = self._get_point_by_address(address, api_key)
            
            if not point:
                results.append({
                    "PNU": pnu,
                    "주소": address,
                    "용도지역": "좌표조회실패",
                })
                continue
            
            # 2단계: 좌표로 4개 용도지역 레이어 검색
            zones = self._query_zoning_layers(point, api_key)
            
            results.append({
                "PNU": pnu,
                "주소": address,
                "용도지역": ", ".join(zones) if zones else "해당없음",
            })
        
        return results

    def _get_point_by_address(self, address, api_key):
        """주소 검색 API를 통해 좌표(x, y) 반환"""
        params = {
            "service": "search",
            "request": "search",
            "type": "ADDRESS",
            "category": "parcel",
            "query": address,
            "key": api_key,
            "domain": VWORLD_DOMAIN,
            "size": "1",
        }
        
        try:
            res = requests.get(VWORLD_SEARCH_URL, params=params, timeout=10)
            data = res.json()
            
            if data.get("response", {}).get("status") == "OK":
                items = data["response"]["result"]["items"]
                if items:
                    point = items[0].get("point", {})
                    x, y = point.get("x"), point.get("y")
                    if x and y:
                        return {"x": x, "y": y}
        except Exception:
            pass
        
        return None

    def _query_zoning_layers(self, point, api_key):
        """좌표(POINT)로 4개 용도지역 레이어 공간 검색"""
        geom_filter = f"POINT({point['x']} {point['y']})"
        found_zones = []
        
        for layer_code, layer_name in ZONING_LAYERS.items():
            params = {
                "service": "data",
                "request": "GetFeature",
                "data": layer_code,
                "key": api_key,
                "domain": VWORLD_DOMAIN,
                "geomFilter": geom_filter,
                "geometry": "false",
                "size": "10",
            }
            
            try:
                res = requests.get(VWORLD_DATA_URL, params=params, timeout=10)
                if res.status_code == 200:
                    data = res.json()
                    features = (
                        data.get("response", {})
                        .get("result", {})
                        .get("featureCollection", {})
                        .get("features", [])
                    )
                    for feat in features:
                        uname = feat["properties"].get("uname")
                        if uname:
                            found_zones.append(f"{layer_name}({uname})")
            except Exception:
                continue
        
        return sorted(set(found_zones))

    def get_columns(self):
        return ["PNU", "주소", "용도지역"]
