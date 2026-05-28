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
from modules.compensation_calculator import get_compensation_ratios

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

# 이용상황 → 보상 분류 그룹 매핑 (현황분석조서 U열 채우기용)
# NED 토지특성정보(부동산공시가격알리미)의 이용상황 세부 분류를
# 예타지침 표 Ⅳ-28의 보상배율 그룹(전답/임야/공공기타/단독/주거기타/상업용,주상용)으로 그룹화.
LAND_USE_TO_COMP_GROUP = {
    # 농경지 → "전답"
    "전": "전답", "전기타": "전답",
    "답": "전답", "답기타": "전답",
    "과수원": "전답", "과": "전답",
    "채소밭": "전답", "묘목": "전답",
    # 임야 → "임야"
    "자연림": "임야", "토지임야": "임야", "조림": "임야", "용림": "임야",
    "노목": "임야", "유실수": "임야", "기타임야": "임야", "임야기타": "임야",
    # 도로/공공시설 → "공공기타"
    "도로등": "공공기타", "도로": "공공기타", "공원등": "공공기타",
    "전기/가스": "공공기타", "운수/통신": "공공기타", "공공기타": "공공기타",
    # 주거 → "단독" 또는 "주거기타"
    "단독": "단독", "단독기타": "단독",
    "주거나지": "주거기타", "주거기타": "주거기타",
    # 상업/주상 → "상업용,주상용"
    "상업용": "상업용,주상용", "상업나지": "상업용,주상용", "상업기타": "상업용,주상용",
    "주상용": "상업용,주상용", "주상나지": "상업용,주상용", "주상기타": "상업용,주상용",
    # 공업 → 표 Ⅳ-28에서는 "주거공업"으로 묶이지만 보상조서 U열에서는 별도 표기
    # (예타지침은 공업용을 주거와 묶는 시도별 분류만 존재. 보상조서 분류에는 없음)
    # 따라서 매핑 안 함 → 원본 그대로 표시 ("공업용" 등)
}


def _is_public_owner(owner_type):
    """소유자가 국유지/공유지/군유지/도유지/시유지면 True (보상조서상 '국ㆍ공유지')."""
    if not owner_type:
        return False
    s = str(owner_type)
    return any(k in s for k in ["국유", "공유", "군유", "도유", "시유"])


def _map_land_use_for_compensation(land_use):
    """이용상황 텍스트 → 보상 분류 그룹. 매핑 없으면 원본 그대로."""
    if not land_use or land_use in ("-", "미조회", ""):
        return ""
    return LAND_USE_TO_COMP_GROUP.get(str(land_use).strip(), str(land_use).strip())

class LandLedgerAnalyzer(BaseAnalyzer):
    name = "토지조서 (편입면적/공시지가 등)"
    description = "지적 속성 및 소유자, 편입 면적을 정밀 분석합니다."

    def analyze(self, pnu_list, api_key):
        t_start = time.time()

        # requests.Session + 연결 풀 확대 (40워커 × 3 서브스레드 동시 호출 대비)
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=64, pool_maxsize=64)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # 로컬 캐시 초기화
        self.cache = LandDataCache()
        self.cache.reset_stats()
        cache_total = self.cache.get_cache_size()
        print(f">>> [캐시] 로컬 캐시 DB 로드됨 (저장된 필지: {cache_total}건)")

        self.cad_attr_map = {} 

        # ① 용도지역 + 지적도 + 공시지가 — 일괄 사전 로딩 (BBOX 1회 호출)
        t_prefetch = time.time()
        print(">>> [1단계] 지역 전체 데이터 일괄 수집 중 (용도지역+지적도+공시지가)...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as prefetch_exec:
            fut_zone = prefetch_exec.submit(self._prefetch_zoning_data, pnu_list, api_key)
            fut_cad = prefetch_exec.submit(self._prefetch_cadastral_data, pnu_list, api_key)
            fut_price = prefetch_exec.submit(self._prefetch_land_price_data, pnu_list, api_key)
            
            self.prefetched_zones = fut_zone.result()
            self.prefetched_cadastral = fut_cad.result()  # {pnu: {jimok, parea, pnilp, ...}}
            self.prefetched_prices = fut_price.result()    # {pnu: 공시지가}
        
        print(f"    → 용도지역 {len(self.prefetched_zones)}건, 지적도 {len(self.prefetched_cadastral)}건, 공시지가 {len(self.prefetched_prices)}건 ({time.time()-t_prefetch:.1f}초)")

        # ② 1차 분석 — 캐시 히트는 즉시 결과 생성, API 필요 필지만 병렬 호출
        t_parcel = time.time()
        cache_hit_count = 0
        prefetch_hit_count = 0
        api_parcels = []  # [(idx, parcel), ...] API 호출이 필요한 필지
        results = []
        cache_hit_pnus = set()  # 캐시 히트된 PNU 추적 — 2차 재시도에서 제외용

        # 캐시 히트 → 즉시 결과 생성 (스레드 우회), 나머지는 API 호출 대상으로 분류
        for i, parcel in enumerate(pnu_list, 1):
            pnu = parcel["PNU"]
            cached = self.cache.get(pnu)
            if cached:
                cache_hit_count += 1
                cache_hit_pnus.add(pnu)
                results.append(self._build_cached_result(i, parcel, cached))
                continue

            # 사전로딩으로 모든 필드가 충족된 필지도 NED(소유자) 호출은 필요하므로 분류만 집계
            cad = self.prefetched_cadastral.get(pnu, {})
            price = self.prefetched_prices.get(pnu)
            if cad.get("jimok") and cad.get("parea", 0) > 0 and (cad.get("pnilp", "0") not in ["0", "-", ""] or price):
                prefetch_hit_count += 1

            api_parcels.append((i, parcel))

        print(f">>> [2단계] 필지 분석 ({len(pnu_list)}건: 캐시 {cache_hit_count}건, 사전로딩 {prefetch_hit_count}건, API호출 {len(api_parcels)}건)")

        # API 호출 필요한 필지만 병렬 처리 (워커 40개)
        batch_size = 200
        for i in range(0, len(api_parcels), batch_size):
            batch = api_parcels[i:i + batch_size]

            with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
                futures = {
                    executor.submit(self._analyze_single_parcel, idx, parcel, api_key): parcel
                    for idx, parcel in batch
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        res = future.result()
                        if res: results.append(res)
                    except: pass

        # 캐시 통계
        stats = self.cache.get_stats()
        print(f"    → 1차 완료: {len(results)}건 (캐시: {stats['hits']}건, API: {stats['misses']}건, 적중률: {stats['hit_rate']})")

        # ③ 2차 보완 — 누락된 필지 재시도 (느리지만 확실하게, 워커 2개)
        # ⭐ 캐시 히트된 PNU는 이미 API 시도 이력이 있으므로 재시도 제외 (도로/하천 등 공시지가 없는 케이스 무한 retry 방지)
        missing = [r for r in results
                   if r["PNU"] not in cache_hit_pnus
                   and (r.get("대장면적(㎡)", 0) <= 0 or r.get("공시지가") in ["-", "0", "", None])]
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
    #  지적도(연속지적도) 사전 로딩 — BBOX 일괄 조회로 지목/면적/공시지가 한 번에 확보
    # ------------------------------------------------------------------ #
    def _prefetch_cadastral_data(self, pnu_list, api_key):
        """연속지적도 레이어에서 BBOX 범위 내 모든 필지의 지목/면적/공시지가를 일괄 조회"""
        cad_map = {}
        try:
            from shapely.geometry import MultiPoint
            pts = [p["지적도형"].centroid for p in pnu_list if p.get("지적도형")]
            if not pts: return {}
            bounds = MultiPoint(pts).bounds
            bbox = f"{bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}"
            
            # 페이지 단위로 전체 데이터 수집 (1000건씩)
            page = 1
            while True:
                try:
                    params = {
                        "service": "data", "request": "GetFeature", "data": CADASTRAL_LAYER,
                        "key": api_key, "domain": VWORLD_DOMAIN,
                        "geomFilter": f"BOX({bbox})", "size": "1000", "page": str(page)
                    }
                    res = self.session.get(VWORLD_DATA_URL, params=params, timeout=15)
                    data = res.json()
                    if data.get("response", {}).get("status") == "OK":
                        features = data["response"]["result"]["featureCollection"]["features"]
                        for feat in features:
                            props = feat["properties"]
                            pnu = props.get("pnu", "")
                            if pnu:
                                cad_map[pnu] = {
                                    "jimok": props.get("jimok", ""),
                                    "parea": float(props.get("parea", 0.0)),
                                    "pnilp": str(props.get("pnilp", "0")).strip(),
                                    "jibun": props.get("jibun", ""),
                                }
                        if len(features) < 1000:
                            break  # 마지막 페이지
                        page += 1
                    else:
                        break
                except:
                    break
        except: pass
        return cad_map

    # ------------------------------------------------------------------ #
    #  개별공시지가 사전 로딩 — BBOX 일괄 조회
    # ------------------------------------------------------------------ #
    def _prefetch_land_price_data(self, pnu_list, api_key):
        """개별공시지가 레이어에서 BBOX 범위 내 모든 필지의 공시지가를 일괄 조회"""
        price_map = {}
        try:
            from shapely.geometry import MultiPoint
            pts = [p["지적도형"].centroid for p in pnu_list if p.get("지적도형")]
            if not pts: return {}
            bounds = MultiPoint(pts).bounds
            bbox = f"{bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}"
            
            # 공시지가 레이어 (LT_C_AISPC_INDVDLNDPRICE)
            try:
                params = {
                    "service": "data", "request": "GetFeature", 
                    "data": "LT_C_AISPC_INDVDLNDPRICE",
                    "key": api_key, "domain": VWORLD_DOMAIN,
                    "geomFilter": f"BOX({bbox})", "size": "1000"
                }
                res = self.session.get(VWORLD_DATA_URL, params=params, timeout=15)
                data = res.json()
                if data.get("response", {}).get("status") == "OK":
                    features = data["response"]["result"]["featureCollection"]["features"]
                    for feat in features:
                        props = feat["properties"]
                        pnu = props.get("pnu", "")
                        val = str(props.get("pblntfPclnd", "")).strip()
                        if pnu and val and val != "0":
                            price_map[pnu] = val
            except: pass
        except: pass
        return price_map

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

        # ★ 사전로딩 데이터 활용 (BBOX 일괄 조회 결과)
        cad_prefetch = getattr(self, 'prefetched_cadastral', {}).get(pnu, {})
        price_prefetch = getattr(self, 'prefetched_prices', {}).get(pnu)
        
        if cad_prefetch:
            if cad_prefetch.get("jimok") and jimok in ["-", "", None]:
                jimok = cad_prefetch["jimok"]
            if cad_prefetch.get("parea", 0) > 0 and parea <= 0:
                parea = cad_prefetch["parea"]
            if cad_prefetch.get("pnilp", "0") not in ["0", "-", ""] and pnilp in ["0", "-", ""]:
                pnilp = cad_prefetch["pnilp"]
        
        if price_prefetch and pnilp in ["0", "-", ""]:
            pnilp = price_prefetch

        # ============================================
        # ⚡ NED API만 호출 (사전로딩으로 WFS/공시지가 이미 확보)
        # ============================================
        max_retries = 7 if aggressive else 5
        backoff_base = 0.4 if aggressive else 0.3

        def _call_ned():
            """NED API — 소유자/면적/지목"""
            _owner, _count, _jimok, _parea, _sojaeji, _land_use = None, None, None, None, None, None
            params = {"key": api_key, "domain": VWORLD_DOMAIN, "pnu": pnu, "format": "json"}
            for attempt in range(max_retries):
                try:
                    res = self.session.get("https://api.vworld.kr/ned/data/ladfrlList", params=params, timeout=12)
                    if res.status_code == 200:
                        ned_data = res.json()
                        def find_info(data):
                            if not data: return None
                            if isinstance(data, list) and len(data) > 0: return data[0]
                            if isinstance(data, dict):
                                if "ldCodeNm" in data or "lndcgrCodeNm" in data: return data
                                for k in ["ladfrlVOList", "ladfrlVO", "item"]:
                                    if k in data:
                                        r = find_info(data[k])
                                        if r: return r
                            return None
                        info = find_info(ned_data)
                        if info:
                            _owner = info.get("posesnSeCodeNm")
                            _sojaeji = info.get("ldCodeNm")
                            _land_use = info.get("lnduseNm")
                            _count = str(int(info.get("cnrsPsnCo", 0)) + 1)
                            _jimok = info.get("lndcgrCodeNm")
                            try: _parea = float(info.get("lndpclAr", 0.0))
                            except: pass
                            return {"owner": _owner, "count": _count, "jimok": _jimok, 
                                    "parea": _parea, "sojaeji": _sojaeji, "land_use": _land_use}
                except: pass
                time.sleep(backoff_base * (attempt + 1))
            return None

        def _call_wfs():
            """WFS 공간 검색 — 사전로딩에서 못 가져온 경우만 실행"""
            # 사전로딩에서 이미 지목+면적 확보했으면 스킵
            if jimok not in ["-", "", None] and parea > 0:
                return None
            if not poly: return None
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
                        w_res = self.session.get(VWORLD_DATA_URL, params=wfs_params, timeout=8)
                        if w_res.status_code == 200:
                            w_data = w_res.json()
                            if w_data.get("response", {}).get("status") == "OK":
                                features = w_data["response"]["result"]["featureCollection"]["features"]
                                if features:
                                    return features[0]["properties"]
                    except: pass
                    time.sleep(0.5 if aggressive else 0.3)
            except: pass
            return None

        def _call_land_characteristics():
            """NED 토지특성정보 — 공시지가 + 이용상황 + 지목 + 면적 + 용도지역을 한 번에 확보.
            (구 _call_price 대체. getIndvdLandPriceAttr는 가격만, getLandCharacteristics는 종합 정보 제공)

            ⭐ stdrYear 파라미터를 안 넣어야 모든 연도 데이터가 반환됨.
            stdrYear=2024 로 제한하면 빈 결과가 자주 나옴 (테스트로 확인).
            모든 연도 데이터 중 lastUpdtDt 최신 + ladUseSittnNm 있는 항목 우선 선택."""
            try:
                p_params = {"key": api_key, "domain": VWORLD_DOMAIN, "pnu": pnu, "format": "json"}
                max_attempts = 3 if aggressive else 2
                for attempt in range(max_attempts):
                    try:
                        res2 = self.session.get(
                            "https://api.vworld.kr/ned/data/getLandCharacteristics",
                            params=p_params, timeout=10
                        )
                        if res2.status_code == 200:
                            data = res2.json()
                            fields = data.get("landCharacteristicss", {}).get("field", [])
                            if fields:
                                # 가장 최신 lastUpdtDt + ladUseSittnNm 있는 항목 우선
                                best = max(fields, key=lambda f: (
                                    1 if f.get("ladUseSittnNm") else 0,
                                    str(f.get("lastUpdtDt") or ""),
                                ))
                                pnilp_val = str(best.get("pblntfPclnd") or "").strip()
                                try:
                                    parea_val = float(best.get("lndpclAr") or 0)
                                except (ValueError, TypeError):
                                    parea_val = 0.0
                                return {
                                    "jimok": best.get("lndcgrCodeNm") or None,
                                    "parea": parea_val if parea_val > 0 else None,
                                    "pnilp": pnilp_val if pnilp_val and pnilp_val != "0" else None,
                                    "land_use": best.get("ladUseSittnNm") or None,
                                    "zone1": best.get("prposArea1Nm") or None,
                                    "zone2": best.get("prposArea2Nm") or None,
                                    "sojaeji": best.get("ldCodeNm") or None,
                                }
                    except: pass
                    time.sleep(0.3)
            except: pass
            return None

        # ⚡ NED는 항상 호출, WFS는 사전로딩 실패 시만, 토지특성정보로 공시지가/이용상황 확보
        ned_result = _call_ned()
        wfs_result = _call_wfs()
        char_result = _call_land_characteristics()

        # NED 결과 적용 (ladfrlList — 소유자/소유자수/소재지 우선)
        if ned_result:
            if ned_result["owner"]: owner_type = ned_result["owner"]
            if ned_result["sojaeji"]: sojaeji = ned_result["sojaeji"]
            if ned_result["land_use"]: land_use = ned_result["land_use"]  # ladfrlList는 보통 미반환
            if ned_result["count"]: owner_count = ned_result["count"]
            if ned_result["jimok"] and (jimok == "-" or len(jimok) > 3 or not re.search('[가-힣]', jimok)):
                jimok = ned_result["jimok"]
            if ned_result["parea"] and (parea <= 0):
                parea = ned_result["parea"]

        # WFS 결과로 누락 데이터 보완 (사전로딩 실패 시만 호출됨)
        if wfs_result:
            if jimok in ["-", "", None]: jimok = wfs_result.get("jimok", jimok)
            if parea <= 0: parea = float(wfs_result.get("parea", 0.0))
            if pnilp in ["0", "-", ""]: pnilp = str(wfs_result.get("pnilp", "0")).strip()

        # 토지특성정보 결과 적용 (getLandCharacteristics — 공시지가/이용상황/지목/면적/용도지역)
        if char_result is not None:
            if char_result.get("pnilp") and pnilp in ["0", "-", ""]:
                pnilp = char_result["pnilp"]
            new_land_use = char_result.get("land_use")
            if new_land_use:
                land_use = new_land_use  # ⭐ 이용상황 R열 채우기
            if char_result.get("jimok") and jimok in ["-", "", None]:
                jimok = char_result["jimok"]
            if char_result.get("parea") and parea <= 0:
                parea = char_result["parea"]
            if char_result.get("sojaeji") and not sojaeji:
                sojaeji = char_result["sojaeji"]

        # API 시도 후 land_use가 여전히 "미조회"이면 빈문자열로 변환하여 캐시 저장 →
        # 다음 분석 시 cache.get()이 valid로 처리하여 무한 재페치 방지.
        # (NED가 일부 PNU 예: 도로/하천에 이용상황 데이터를 아예 안 줘서 char_result=None 인 경우 포함)
        # 단, ned_result도 None이면 NED 전체가 일시적 실패일 수 있으니 retry 위해 "미조회" 유지.
        if land_use == "미조회" and (ned_result is not None or char_result is not None):
            land_use = ""

        # --- Search API (최후의 수단 — 위 3개에서 모두 실패한 경우만) ---
        if jimok in ["-", "", None] or parea <= 0:
            try:
                search_params = {
                    "service": "search", "request": "search", "version": "2.0", "crs": "EPSG:4326",
                    "size": "1", "type": "DISTRICT", "category": "parcel", "query": pnu, "key": api_key
                }
                max_search = 4 if aggressive else 3
                for attempt in range(max_search):
                    try:
                        s_res = self.session.get("https://api.vworld.kr/req/search", params=search_params, timeout=8)
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
                    time.sleep(0.5 if aggressive else 0.3)
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
    #  캐시 히트 결과 생성 (executor 우회용 고속 경로)
    # ------------------------------------------------------------------ #
    def _build_cached_result(self, idx, parcel, cached):
        """캐시 데이터로 결과 직접 생성. _analyze_single_parcel의 캐시 경로와 동일한 fallback 로직 적용."""
        pnu = parcel["PNU"]
        cad_area = parcel.get("구적상면적", 0.0)
        total_cad_area = parcel.get("전체구적면적", 0.0)
        jimok = cached["jimok"] if cached["jimok"] not in ["-", ""] else parcel.get("지목", "-")
        parea = cached["parea"] if cached["parea"] > 0 else parcel.get("대장면적", 0.0)
        pnilp = cached["pnilp"] if cached["pnilp"] not in ["0", "-", ""] else parcel.get("공시지가", "0")
        owner_type = cached["owner_type"]
        owner_count = cached["owner_count"]
        land_use = cached["land_use"]
        sojaeji = cached["sojaeji"] or parcel.get("주소", "")
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

        # 공시지가 처리: 숫자로 변환 (엑셀 W열 수식 J*L*(T+V)/2 동작을 위해)
        # 값 없으면 "-" 텍스트로 표시 (수식에서 ISNUMBER=FALSE → 0 처리)
        if pnilp in ["0", "-", "", None]:
            pnilp = "-"
        elif not isinstance(pnilp, (int, float)):
            try:
                pnilp = int(str(pnilp).replace(",", "").strip())
            except (ValueError, TypeError):
                pnilp = "-"

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

        # ★ 진흥지역 판별 (용도지역 데이터에서 농업진흥/보호구역 매칭)
        promotion_zone = "-"
        if poly and self.prefetched_zones:
            centroid = poly.centroid
            for feat in self.prefetched_zones:
                uname = feat["properties"].get("uname", "")
                if "농업진흥" in uname or "농업보호" in uname or "진흥" in uname:
                    if shape(feat["geometry"]).intersects(centroid):
                        promotion_zone = uname
                        break
        # 용도지역명에서 진흥지역 추출
        if promotion_zone == "-" and "진흥" in zoning:
            promotion_zone = zoning

        # ★ 농지구분 (지목 기반 자동 분류)
        farmland_type = "-"
        if jimok in ["전", "답", "과"]:
            farmland_type = "농지"
        elif jimok in ["목"]:
            farmland_type = "목장용지"
        elif jimok in ["임"]:
            farmland_type = "임야"

        # ★ 산지구분 (필지구분 + 지목 기반)
        mountain_type = "-"
        pnu_type = pnu[10] if len(pnu) > 10 else "1"
        if pnu_type == "2":  # 산번지
            mountain_type = "산지"
        elif jimok == "임":
            mountain_type = "산지"

        # 비고
        note = ""
        if parea <= 0:
            note = "★대장면적 누락 (재확인 필요)"

        # 보상조서용 분류 (S~V열)
        # 국공유지: 용도지역(S), 보상배율(T,V) 모두 빈칸 + 이용상황(U)="국ㆍ공유지"
        # 사유지(개인/법인/종중 등): 용도지역(S) + 이용상황 그룹(U) 매핑
        # 보상배율(T, V): KDI 표 Ⅳ-28에서 시도+그룹 기반 자동 조회
        #   - data/compensation_ratio.json 참조 (출처: 예타 총괄지침 2018.4)
        if _is_public_owner(owner_type):
            comp_zoning = ""
            comp_land_use = "국ㆍ공유지"
            comp_ratio_zoning = ""
            comp_ratio_use = ""
        else:
            comp_zoning = zoning if zoning not in ("미조회", "-", "", None) else ""
            comp_land_use = _map_land_use_for_compensation(land_use)
            # ★ 보상배율 자동 조회 (KDI 표 Ⅳ-28, 시도+그룹 기준)
            r_zoning, r_use = get_compensation_ratios(pnu, zoning, land_use)
            comp_ratio_zoning = r_zoning if r_zoning is not None else ""
            comp_ratio_use = r_use if r_use is not None else ""

        return {
            "일련번호": idx, "PNU": pnu, "소재지": clean_address(sojaeji),
            "필지구분": "일반" if pnu_type == "1" else "산" if pnu_type == "2" else "기타",
            "본번": pnu[11:15].lstrip('0') or "0",
            "부번": pnu[15:19].lstrip('0') or "0",
            "지목": jimok, "소유자": owner_type, "소유자수": owner_count,
            "공시지가": pnilp, "대장면적(㎡)": parea, "편입면적(㎡)": included_area,
            "편입구분": inclusion_type, "용도지역": zoning,
            "진흥지역": promotion_zone, "농지구분": farmland_type, "산지구분": mountain_type,
            # 이용상황: "미조회"=API 미시도 또는 실패, ""=API 응답에 데이터 없음 — 둘 다 "-"로 표시
            "이용상황": land_use if land_use and land_use != "미조회" else "-",
            # ★ 보상조서용 컬럼 (S~V) — 표 Ⅳ-28 기반 자동 채움
            "용도지역(보상)": comp_zoning,           # S
            "보상배율(용도)": comp_ratio_zoning,      # T  (자동: KDI 표 Ⅳ-28)
            "이용상황(보상)": comp_land_use,          # U
            "보상배율(이용)": comp_ratio_use,         # V  (자동: KDI 표 Ⅳ-28)
            # ★ 토지보상비(W) — excel_exporter에서 행 단위 수식으로 작성
            #   수식: =IFERROR(IF(OR(U="국ㆍ공유지", NOT(ISNUMBER(J))), 0, J*L*(T+V)/2), 0)
            "토지보상비(원)": "",                     # W  (수식 placeholder)
            "비고": note,                             # X
        }
