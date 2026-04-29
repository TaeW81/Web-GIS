"""
토지대장 분석기 — 토지 속성 및 편입 분석 (대용량 데이터 안정성 극대화 버전)

개선사항:
  - 사전 로딩(Prefetch) 시 BBox 분할 호출로 누락 방지
  - NED API 호출 시 재시도(Retry) 및 타임아웃 최적화
  - 공시지가/면적 데이터 누락 시 2차 풀백 로직 강화
"""
import requests
import concurrent.futures
import re
import time
from analyzers.base_analyzer import BaseAnalyzer
from config import VWORLD_DATA_URL, VWORLD_DOMAIN, CADASTRAL_LAYER
from shapely.geometry import shape

def clean_address(addr):
    if not addr: return ""
    return re.sub(r'\s+[\d-]+$', '', str(addr)).strip()

class LandLedgerAnalyzer(BaseAnalyzer):
    name = "토지조서 (편입면적/공시지가 등)"
    description = "지적 속성 및 소유자, 편입 면적을 정밀 분석합니다."

    def analyze(self, pnu_list, api_key):
        self.session = requests.Session()
        # 1. 사전 로딩 (BBox 분할 및 페이지네이션으로 데이터 유실 원천 차단)
        self.cad_attr_map = self._prefetch_cadastral_attributes(pnu_list, api_key)
        self.prefetched_zones = self._prefetch_zoning_data(pnu_list, api_key)
        
        results = []
        # 워커 수를 약간 줄여 API 부하 조절 (안정성 우선)
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_pnu = {
                executor.submit(self._analyze_single_parcel, i+1, parcel, api_key): parcel 
                for i, parcel in enumerate(pnu_list)
            }
            for future in concurrent.futures.as_completed(future_to_pnu):
                try:
                    res = future.result()
                    if res: results.append(res)
                except: pass
        
        return sorted(results, key=lambda x: x["일련번호"])

    def _fetch_with_retry(self, url, params, retries=2):
        for i in range(retries + 1):
            try:
                res = self.session.get(url, params=params, timeout=15)
                if res.status_code == 200: return res.json()
            except:
                if i < retries: time.sleep(0.5)
        return None

    def _prefetch_data_robust(self, layer, pnu_list, api_key):
        """구역을 그리드로 분할하거나 필지별 BBox로 데이터를 가져와 누락을 방지"""
        all_features = []
        seen_pnu = set()
        
        # 500개씩 묶어서 각각의 BBox로 요청 (대규모 구역 대응)
        batch_size = 500
        for i in range(0, len(pnu_list), batch_size):
            batch = pnu_list[i:i+batch_size]
            from shapely.geometry import MultiPoint
            points = [p["지적도형"].centroid for p in batch if p.get("지적도형")]
            if not points: continue
            bounds = MultiPoint(points).bounds
            bbox = f"{bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}"
            
            page = 1
            while True:
                params = {
                    "service": "data", "request": "GetFeature", "data": layer,
                    "key": api_key, "domain": VWORLD_DOMAIN, "geomFilter": f"BOX({bbox})",
                    "size": "1000", "page": str(page), "geometry": "true"
                }
                data = self._fetch_with_retry(VWORLD_DATA_URL, params)
                if not data or data.get("response", {}).get("status") != "OK": break
                
                features = data.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [])
                if not features: break
                
                for f in features:
                    p_pnu = f["properties"].get("pnu")
                    if p_pnu and p_pnu not in seen_pnu:
                        all_features.append(f)
                        seen_pnu.add(p_pnu)
                
                total = int(data.get("response", {}).get("record", {}).get("total", 0))
                if len(features) < 1000 or page * 1000 >= total: break
                page += 1
                if page > 50: break
        return all_features

    def _prefetch_cadastral_attributes(self, pnu_list, api_key):
        attr_map = {}
        features = self._prefetch_data_robust(CADASTRAL_LAYER, pnu_list, api_key)
        for f in features:
            p = f["properties"]
            attr_map[p["pnu"]] = {
                "jimok": p.get("jimok", "-"),
                "pnilp": p.get("pnilp", "-"),
                "parea": float(p.get("parea", 0.0))
            }
        return attr_map

    def _prefetch_zoning_data(self, pnu_list, api_key):
        all_zones = []
        for layer in ["LT_C_UQ111", "LT_C_UQ112", "LT_C_UQ113", "LT_C_UQ114"]:
            all_zones.extend(self._prefetch_data_robust(layer, pnu_list, api_key))
        return all_zones

    def _analyze_single_parcel(self, idx, parcel, api_key):
        pnu = parcel["PNU"]
        cad_area = parcel.get("구적상면적", 0.0)
        total_cad_area = parcel.get("전체구적면적", 0.0)
        
        pre_attr = self.cad_attr_map.get(pnu, {})
        jimok = pre_attr.get("jimok", "-")
        pnilp = str(pre_attr.get("pnilp", "-")).strip()
        parea = pre_attr.get("parea", 0.0)
        
        # 1차 풀백: 사전 로딩에 면적이 없으면 구적면적(전체) 사용
        if parea <= 0: parea = total_cad_area
        
        owner_type, owner_count, sojaeji_raw, land_use = "개인", "1", parcel["주소"], "미조회"
        gubun_code = pnu[10]
        gubun_nm = "일반" if gubun_code == "1" else "산" if gubun_code == "2" else "기타"
        bonbeon = pnu[11:15].lstrip('0') or "0"; bubeon = pnu[15:19].lstrip('0') or "0"

        # NED API (토지대장)
        try:
            params = {"key": api_key, "domain": VWORLD_DOMAIN, "pnu": pnu, "format": "json"}
            ned_data = self._fetch_with_retry("https://api.vworld.kr/ned/data/ladfrlList", params)
            if ned_data and "ladfrlVOList" in ned_data and "ladfrlVOList" in ned_data["ladfrlVOList"]:
                info = ned_data["ladfrlVOList"]["ladfrlVOList"][0]
                if jimok == "-": jimok = info.get("lndcgrCodeNm", "-")
                owner_type = info.get("posesnSeCodeNm", "개인")
                sojaeji_raw = info.get("ldCodeNm", sojaeji_raw)
                land_use = info.get("lnduseNm", "미조회")
                cnrs = info.get("cnrsPsnCo", "0")
                owner_count = str(int(cnrs) + 1) if str(cnrs).isdigit() else "1"
                # 대장면적 업데이트 (NED 우선)
                try:
                    val = float(info.get("lndpclAr", 0.0))
                    if val > 0: parea = val
                except: pass

            # 공시지가 조회 (최근 5년)
            if pnilp in ["-", "0", "None", ""]:
                import datetime
                this_year = datetime.datetime.now().year
                for year in range(this_year, this_year - 5, -1):
                    p_params = params.copy(); p_params["stdrYear"] = str(year)
                    price_data = self._fetch_with_retry("https://api.vworld.kr/ned/data/getIndvdLandPriceAttr", p_params)
                    if price_data and "indvdLandPrices" in price_data and "field" in price_data["indvdLandPrices"]:
                        price_val = str(price_data["indvdLandPrices"]["field"][0].get("pblntfPclnd", "")).strip()
                        if price_val and price_val not in ["0", ""]:
                            pnilp = price_val
                            break
        except: pass

        # 지목/공시지가 최종 보정
        if jimok == "-" or not jimok: jimok = "기타"
        if pnilp in ["-", "0", "None", ""]: pnilp = "0"

        # 편입면적 계산 (대장면적 기반)
        if total_cad_area > 0 and (cad_area / total_cad_area) >= 0.98:
            inclusion_type, included_area = "전부편입", parea
        else:
            inclusion_type, included_area = "일부편입", round(cad_area, 2)
        
        # 용도지역
        zoning_info = "미조회"
        poly = parcel.get("지적도형")
        if poly and self.prefetched_zones:
            centroid = poly.centroid
            for feat in self.prefetched_zones:
                if shape(feat["geometry"]).intersects(centroid):
                    zoning_info = feat["properties"].get("uname", zoning_info)
                    break
        
        return {
            "일련번호": idx, "PNU": pnu, "소재지": clean_address(sojaeji_raw),
            "필지구분": gubun_nm, "본번": bonbeon, "부번": bubeon,
            "지목": jimok, "소유자": owner_type, "소유자수": owner_count,
            "공시지가": pnilp, "대장면적(㎡)": parea, "편입면적(㎡)": included_area,
            "편입구분": inclusion_type, "용도지역": zoning_info, "이용상황": land_use, "비고": ""
        }
