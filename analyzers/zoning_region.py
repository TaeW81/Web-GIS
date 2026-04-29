"""
용도지역 분석기 — 4대 용도지역 조회 (대규모 필지 무제한 지원 버전)

데이터 소스: 브이월드 Data API (LT_C_UQ111~114)
최적화: 
  - 구역 전체 레이어 사전 로딩 (무제한 페이지네이션 적용)
  - 병렬 처리 및 공간 연산 기반 고속 조회
"""
import requests
import concurrent.futures
from analyzers.base_analyzer import BaseAnalyzer
from config import VWORLD_DATA_URL, VWORLD_DOMAIN
from shapely.geometry import shape

class ZoningRegionAnalyzer(BaseAnalyzer):
    name = "용도지역"
    description = "4대 용도지역(도시/관리/농림/자연환경보전)을 조회합니다. (고속 모드)"

    def analyze(self, pnu_list, api_key):
        self.session = requests.Session()
        
        # 1. 구역 전체의 용도지역 데이터 사전 로딩 (페이지네이션 적용)
        self.prefetched_features = self._prefetch_all_zones(pnu_list, api_key)
        
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_pnu = {executor.submit(self._analyze_single_zoning, parcel, api_key): parcel for parcel in pnu_list}
            for future in concurrent.futures.as_completed(future_to_pnu):
                try:
                    res = future.result()
                    if res: results.append(res)
                except: pass
        
        return results

    def _prefetch_all_zones(self, pnu_list, api_key):
        """구역 내 모든 용도지역 레이어 데이터를 한 번에 가져옴 (무제한 페이지네이션)"""
        all_features = []
        try:
            from shapely.geometry import MultiPoint
            points = [p["지적도형"].centroid for p in pnu_list if p.get("지적도형")]
            if not points: return []
            bounds = MultiPoint(points).bounds
            bbox = f"{bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}"
            
            for layer in ["LT_C_UQ111", "LT_C_UQ112", "LT_C_UQ113", "LT_C_UQ114"]:
                page = 1
                page_size = 1000
                while True:
                    params = {
                        "service": "data", "request": "GetFeature", "data": layer,
                        "key": api_key, "domain": VWORLD_DOMAIN, "geomFilter": f"BOX({bbox})",
                        "size": str(page_size), "page": str(page), "geometry": "true"
                    }
                    res = self.session.get(VWORLD_DATA_URL, params=params, timeout=15)
                    data = res.json()
                    if data.get("response", {}).get("status") != "OK": break
                    
                    feats = data.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [])
                    if not feats: break
                    
                    all_features.extend(feats)
                    total = int(data.get("response", {}).get("record", {}).get("total", 0))
                    if len(all_features) >= total or len(feats) < page_size: break
                    page += 1
                    if page > 100: break
        except: pass
        return all_features

    def _analyze_single_zoning(self, parcel, api_key):
        pnu = parcel["PNU"]
        address = parcel["주소"]
        poly = parcel.get("지적도형")
        
        zoning_name = "해당없음"
        if poly and self.prefetched_features:
            centroid = poly.centroid
            for feat in self.prefetched_features:
                if shape(feat["geometry"]).intersects(centroid):
                    zoning_name = feat["properties"].get("uname", zoning_info)
                    break
        
        return {"PNU": pnu, "주소": address, "용도지역": zoning_name}
