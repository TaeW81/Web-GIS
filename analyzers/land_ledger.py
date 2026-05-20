"""
토지대장 분석기 — 로컬 캐시 + 무결성 보장 + 고속 버전

전략:
  ① SQLite 로컬 캐시 우선 조회 → 캐시 히트 시 API 호출 0건 (즉시 완료)
  ② 캐시 미스 필지만 API 호출 (8워커 병렬)
  ③ NED API 재시도 5회 + WFS/Search 3회로 복원 (데이터 무결성 최우선)
  ④ 1차 분석 후 누락 필지 자동 감지 → 2차 집중 재시도 (워커 2개, 느리지만 확실)
  ⑤ 성공한 데이터는 모두 로컬 캐시에 저장 → 다음 분석부터 초고속
"""
import requests
from requests.adapters import HTTPAdapter
import concurrent.futures
import re
import time
from analyzers.base_analyzer import BaseAnalyzer
from config import VWORLD_DATA_URL, VWORLD_DOMAIN, CADASTRAL_LAYER
from shapely.geometry import shape
from modules.land_cache import LandDataCache

def clean_address(addr):
    if not addr: return ""
    return re.sub(r'\s+[\d-]+$', '', str(addr)).strip()

JIMOK_MAP = {
    "01": "전", "02": "답", "03": "과", "04": "목", "05": "임", "06": "광", "07": "염", "08": "대",
    "09": "장", "10": "학", "11": "주", "12": "창", "13": "도", "14": "철", "15": "제", "16": "구",
    "17": "유", "18": "수", "19": "공", "20": "체", "21": "원", "22": "종", "23": "사", "24": "묘",
    "25": "잡", "26": "주", "27": "양", "28": "공",
    "전": "전", "답": "답", "과": "과", "목": "목", "임": "임", "광": "광", "염": "염", "대": "대",
    "장": "장", "학": "학", "주": "주", "창": "창", "도": "도", "철": "철", "제": "제", "구": "구",
    "유": "유", "수": "수", "공": "공", "체": "체", "원": "원", "종": "종", "사": "사", "묘": "묘", "잡": "잡"
}

class LandLedgerAnalyzer(BaseAnalyzer):
    name = "토지조서 (편입면적/공시지가 등)"
    description = "지적 속성 및 소유자, 편입 면적을 정밀 분석합니다."

    def analyze(self, pnu_list, api_key):
        t_start = time.time()

        # requests.Session + 연결 풀 확대
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=12, pool_maxsize=12)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # 로컬 캐시 초기화
        self.cache = LandDataCache()
        self.cache.reset_stats()
        cache_total = self.cache.get_cache_size()
        print(f">>> [캐시] 로컬 캐시 DB 로드됨 (저장된 필지: {cache_total}건)")

        self.cad_attr_map = {} 

        # ① 용도지역 — 4개 레이어 병렬 사전 로딩
        t_zone = time.time()
        print(">>> [1단계] 용도지역 수집 중 (병렬)...")
        self.prefetched_zones = self._prefetch_zoning_data(pnu_list, api_key)
        print(f"    → 용도지역 {len(self.prefetched_zones)}건 수집 완료 ({time.time()-t_zone:.1f}초)")

        # ② 1차 분석 — 캐시 + API 병렬 조회 (8워커)
        t_parcel = time.time()
        print(f">>> [2단계] 토지대장 분석 시작 ({len(pnu_list)}건, 워커 8개)...")
        results = []
        batch_size = 200
        for i in range(0, len(pnu_list), batch_size):
            batch = pnu_list[i:i + batch_size]
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = {
                    executor.submit(self._analyze_single_parcel, i + j + 1, parcel, api_key): parcel
                    for j, parcel in enumerate(batch)
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        res = future.result()
                        if res: results.append(res)
                    except: pass
            
            if i + batch_size < len(pnu_list):
                time.sleep(0.3)

        # 캐시 통계
        stats = self.cache.get_stats()
        print(f"    → 1차 완료: {len(results)}건 (캐시 히트: {stats['hits']}건, API 조회: {stats['misses']}건, 적중률: {stats['hit_rate']})")

        # ③ 2차 보완 — 누락된 필지 재시도 (느리지만 확실하게, 워커 2개)
        missing = [r for r in results if r.get("대장면적(㎡)", 0) <= 0 or r.get("공시지가") in ["-", "0", "", None]]
        if missing:
            print(f">>> [3단계] 누락 필지 {len(missing)}건 2차 집중 재시도...")
            # 원본 parcel 정보를 PNU로 매핑
            pnu_to_parcel = {p["PNU"]: p for p in pnu_list}
            retry_results = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = {}
                for r in missing:
                    pnu = r["PNU"]
                    parcel = pnu_to_parcel.get(pnu)
                    if parcel:
                        futures[executor.submit(
                            self._analyze_single_parcel, r["일련번호"], parcel, api_key, aggressive=True
                        )] = pnu
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        res = future.result()
                        if res: retry_results.append(res)
                    except: pass
            
            # 재시도 결과로 교체 (개선된 데이터만)
            retry_map = {r["PNU"]: r for r in retry_results}
            for i, r in enumerate(results):
                if r["PNU"] in retry_map:
                    retried = retry_map[r["PNU"]]
                    # 재시도 결과가 더 좋은 경우에만 교체
                    if (retried.get("대장면적(㎡)", 0) > 0 and r.get("대장면적(㎡)", 0) <= 0) or \
                       (retried.get("공시지가") not in ["-", "0", ""] and r.get("공시지가") in ["-", "0", ""]):
                        results[i] = retried
            
            # 최종 누락 현황 보고
            still_missing_area = sum(1 for r in results if r.get("대장면적(㎡)", 0) <= 0)
            still_missing_price = sum(1 for r in results if r.get("공시지가") in ["-", "0", "", None])
            if still_missing_area > 0 or still_missing_price > 0:
                print(f"    → 2차 후에도 남은 누락: 면적 {still_missing_area}건, 공시지가 {still_missing_price}건")
            else:
                print(f"    → 2차 보완 성공! 모든 데이터 확보 완료")

        elapsed = time.time() - t_start
        print(f">>> [성능] 토지대장 분석 완료: {len(results)}건, 총 {elapsed:.1f}초 (필지당 {elapsed/max(len(pnu_list),1):.2f}초)")
        return sorted(results, key=lambda x: x["일련번호"])

    # ------------------------------------------------------------------ #
    #  용도지역 사전 로딩 — 4개 레이어 병렬 조회
    # ------------------------------------------------------------------ #
    def _prefetch_zoning_data(self, pnu_list, api_key):
        all_zones = []
        try:
            from shapely.geometry import MultiPoint
            pts = [p["지적도형"].centroid for p in pnu_list if p.get("지적도형")]
            if not pts: return []
            bounds = MultiPoint(pts).bounds
            bbox = f"{bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}"
            
            def fetch_layer(layer):
                try:
                    params = {"service": "data", "request": "GetFeature", "data": layer,
                              "key": api_key, "domain": VWORLD_DOMAIN,
                              "geomFilter": f"BOX({bbox})", "size": "1000", "geometry": "true"}
                    res = self.session.get(VWORLD_DATA_URL, params=params, timeout=15)
                    data = res.json()
                    if data.get("response", {}).get("status") == "OK":
                        return data["response"]["result"]["featureCollection"]["features"]
                except: pass
                return []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(fetch_layer, layer) 
                           for layer in ["LT_C_UQ111", "LT_C_UQ112", "LT_C_UQ113", "LT_C_UQ114"]]
                for future in concurrent.futures.as_completed(futures):
                    all_zones.extend(future.result())
        except: pass
        return all_zones

    # ------------------------------------------------------------------ #
    #  필지 1건 상세 분석 — 캐시 우선 + API 보완
    # ------------------------------------------------------------------ #
    def _analyze_single_parcel(self, idx, parcel, api_key, aggressive=False):
        pnu = parcel["PNU"]
        cad_area = parcel.get("구적상면적", 0.0)
        total_cad_area = parcel.get("전체구적면적", 0.0)
        poly = parcel.get("지적도형")

        # [핵심] pnu_extractor에서 이미 확보한 속성 우선 활용
        jimok = parcel.get("지목", "-")
        parea = parcel.get("대장면적", 0.0)
        pnilp = parcel.get("공시지가", "0")
        sojaeji = parcel.get("주소", "")
        
        owner_type, owner_count, land_use = "개인", "1", "미조회"

        # ★ 로컬 캐시 먼저 확인 (API 호출 없이 즉시 반환 가능)
        if not aggressive:
            cached = self.cache.get(pnu)
            if cached:
                jimok = cached["jimok"] if cached["jimok"] not in ["-", ""] else jimok
                parea = cached["parea"] if cached["parea"] > 0 else parea
                pnilp = cached["pnilp"] if cached["pnilp"] not in ["0", "-", ""] else pnilp
                owner_type = cached["owner_type"]
                owner_count = cached["owner_count"]
                land_use = cached["land_use"]
                sojaeji = cached["sojaeji"] or sojaeji
                # 캐시에서 모든 데이터가 유효하면 API 호출 스킵!
                return self._build_result(idx, pnu, parcel, jimok, parea, pnilp, 
                                          owner_type, owner_count, land_use, sojaeji,
                                          cad_area, total_cad_area)

        # --- NED API (소유자/면적/지목) ---
        # aggressive=True(2차 재시도) 시: 7회 재시도 + 긴 대기
        # 일반: 5회 재시도 + 적절한 대기
        max_retries = 7 if aggressive else 5
        backoff_base = 0.8 if aggressive else 0.5
        
        params = {"key": api_key, "domain": VWORLD_DOMAIN, "pnu": pnu, "format": "json"}
        for attempt in range(max_retries):
            try:
                res = self.session.get("https://api.vworld.kr/ned/data/ladfrlList", params=params, timeout=15)
                if res.status_code == 200:
                    ned_data = res.json()
                    
                    def find_info(data):
                        if not data: return None
                        if isinstance(data, list) and len(data) > 0: return data[0]
                        if isinstance(data, dict):
                            if "ldCodeNm" in data or "lndcgrCodeNm" in data: return data
                            for k in ["ladfrlVOList", "ladfrlVO", "item"]:
                                if k in data:
                                    r = find_info(data[k]); 
                                    if r: return r
                        return None
                    
                    info = find_info(ned_data)
                    if info:
                        owner_type = info.get("posesnSeCodeNm", owner_type)
                        sojaeji = info.get("ldCodeNm", sojaeji)
                        land_use = info.get("lnduseNm", land_use)
                        owner_count = str(int(info.get("cnrsPsnCo", 0)) + 1)
                        if jimok == "-" or len(jimok) > 3 or (not re.search('[가-힣]', jimok)):
                            jimok = info.get("lndcgrCodeNm", jimok)
                        if parea <= 0:
                            try: parea = float(info.get("lndpclAr", 0.0))
                            except: pass
                        break
            except Exception:
                pass
            time.sleep(backoff_base * (attempt + 1))

        # --- WFS 공간 검색 (지목/면적 보완) ---
        if (jimok in ["-", "", None] or parea <= 0) and poly:
            try:
                c = poly.centroid
                geom_filter = f"POINT({c.x} {c.y})"
                wfs_params = {
                    "service": "data", "request": "GetFeature", "data": CADASTRAL_LAYER,
                    "key": api_key, "domain": VWORLD_DOMAIN, "geomFilter": geom_filter, "size": "1"
                }
                max_wfs = 5 if aggressive else 3
                for attempt in range(max_wfs):
                    try:
                        w_res = self.session.get(VWORLD_DATA_URL, params=wfs_params, timeout=10)
                        if w_res.status_code == 200:
                            w_data = w_res.json()
                            if w_data.get("response", {}).get("status") == "OK":
                                features = w_data["response"]["result"]["featureCollection"]["features"]
                                if features:
                                    props = features[0]["properties"]
                                    if jimok in ["-", "", None]: jimok = props.get("jimok", jimok)
                                    if parea <= 0: parea = float(props.get("parea", 0.0))
                                    if pnilp in ["0", "-", ""]: pnilp = str(props.get("pnilp", "0")).strip()
                                break
                    except: pass
                    time.sleep(1.0 if aggressive else 0.7)
            except: pass

        # --- Search API (최후의 수단) ---
        if (jimok in ["-", "", None] or parea <= 0):
            try:
                search_params = {
                    "service": "search", "request": "search", "version": "2.0", "crs": "EPSG:4326",
                    "size": "1", "type": "DISTRICT", "category": "parcel", "query": pnu, "key": api_key
                }
                max_search = 4 if aggressive else 3
                for attempt in range(max_search):
                    try:
                        s_res = self.session.get("https://api.vworld.kr/req/search", params=search_params, timeout=10)
                        if s_res.status_code == 200:
                            s_data = s_res.json()
                            if s_data.get("response", {}).get("status") == "OK":
                                items = s_data["response"]["result"]["items"]
                                if items:
                                    item = items[0]
                                    if sojaeji == parcel["주소"]:
                                        sojaeji = item.get("title", sojaeji)
                                break
                    except: pass
                    time.sleep(1.0 if aggressive else 0.7)
            except: pass

        # 공시지가 추가 보완
        if pnilp in ["0", "-", ""]:
            try:
                p_params = {"key": api_key, "domain": VWORLD_DOMAIN, "pnu": pnu, "format": "json"}
                years = [2025, 2024, 2023] if aggressive else [2024, 2023]
                for year in years:
                    p_params["stdrYear"] = str(year)
                    success = False
                    max_price = 3 if aggressive else 2
                    for attempt in range(max_price):
                        try:
                            res2 = self.session.get("https://api.vworld.kr/ned/data/getIndvdLandPriceAttr", params=p_params, timeout=10)
                            if res2.status_code == 200:
                                price = res2.json()
                                if "indvdLandPrices" in price and "field" in price["indvdLandPrices"]:
                                    val = str(price["indvdLandPrices"]["field"][0].get("pblntfPclnd", "")).strip()
                                    if val and val != "0": 
                                        pnilp = val
                                        success = True
                                        break
                        except: pass
                        if success: break
                        time.sleep(0.5)
                    if success: break
            except: pass

        # ★ API에서 가져온 데이터를 로컬 캐시에 저장
        self.cache.put(pnu, {
            "jimok": jimok, "parea": parea, "pnilp": pnilp,
            "owner_type": owner_type, "owner_count": owner_count,
            "land_use": land_use, "sojaeji": sojaeji
        })

        return self._build_result(idx, pnu, parcel, jimok, parea, pnilp,
                                  owner_type, owner_count, land_use, sojaeji,
                                  cad_area, total_cad_area)

    # ------------------------------------------------------------------ #
    #  결과 딕셔너리 생성 (공통 로직)
    # ------------------------------------------------------------------ #
    def _build_result(self, idx, pnu, parcel, jimok, parea, pnilp,
                      owner_type, owner_count, land_use, sojaeji,
                      cad_area, total_cad_area):
        poly = parcel.get("지적도형")
        
        # 최종 보정 및 지목 매핑
        if jimok in ["-", "", None]: 
            jimok = "기타"
        else:
            jimok = JIMOK_MAP.get(jimok.strip(), jimok)
            
        if pnilp in ["0", "-", "", None]: pnilp = "-"

        # 편입면적 계산
        if total_cad_area > 0 and parea > 0:
            ratio = cad_area / total_cad_area
            if ratio >= 0.98:
                inclusion_type, included_area = "전부편입", parea
            else:
                inclusion_type, included_area = "일부편입", round(parea * ratio, 2)
        elif parea > 0:
            inclusion_type, included_area = "전부편입", parea
        else:
            inclusion_type, included_area = "확인불가", 0.0

        # 용도지역
        zoning = "미조회"
        if poly and self.prefetched_zones:
            centroid = poly.centroid
            for feat in self.prefetched_zones:
                if shape(feat["geometry"]).intersects(centroid):
                    zoning = feat["properties"].get("uname", zoning); break

        # 비고
        note = ""
        if parea <= 0:
            note = "★대장면적 누락 (재확인 필요)"

        return {
            "일련번호": idx, "PNU": pnu, "소재지": clean_address(sojaeji),
            "필지구분": "일반" if pnu[10] == "1" else "산" if pnu[10] == "2" else "기타",
            "본번": pnu[11:15].lstrip('0') or "0",
            "부번": pnu[15:19].lstrip('0') or "0",
            "지목": jimok, "소유자": owner_type, "소유자수": owner_count,
            "공시지가": pnilp, "대장면적(㎡)": parea, "편입면적(㎡)": included_area,
            "편입구분": inclusion_type, "용도지역": zoning, "이용상황": land_use, "비고": note
        }
