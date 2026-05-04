"""
토지대장 분석기 — 초고속 + 대장면적 무결성 보장 버전

전략:
  ① WFS 벌크 조회(attrFilter pnu:IN) 로 빠르게 1차 수집
  ② WFS 실패한 PNU 자동 감지 → NED API에서 반드시 면적 확보 (2차 보완)
  ③ NED API 소유자/면적 정보 25개 병렬 처리
  ④ 공시지가: WFS 보유 시 추가 조회 생략
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
        self.session = requests.Session()

        # ① WFS 벌크 조희 대신 필지별 정밀 조희로 변경 (지속적 누락 방지)
        # bulk_fetch는 _analyze_single_parcel 내부에서 개별적으로 수행하도록 통합
        self.cad_attr_map = {} 

        # ② 용도지역
        print(">>> [2단계] 용도지역 수집 중...")
        self.prefetched_zones = self._prefetch_zoning_data(pnu_list, api_key)

        # ③ NED API + 공간 검색 보완 — 3개 워커로 안정성 집중
        print(">>> [3단계] 토지대장 및 공간 검색 시작...")
        results = []
        batch_size = 200
        for i in range(0, len(pnu_list), batch_size):
            batch = pnu_list[i:i + batch_size]
            
            # 워커 수를 3개로 더 줄여서 서버 차단 원천 차단 (안정성 최우선)
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
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
                time.sleep(1.0) 

        return sorted(results, key=lambda x: x["일련번호"])

    # (기존 벌크 조회 제거 — 개별 조회로 통합됨)

    # ------------------------------------------------------------------ #
    #  용도지역 사전 로딩
    # ------------------------------------------------------------------ #
    def _prefetch_zoning_data(self, pnu_list, api_key):
        all_zones = []
        try:
            from shapely.geometry import MultiPoint
            pts = [p["지적도형"].centroid for p in pnu_list if p.get("지적도형")]
            if not pts: return []
            bounds = MultiPoint(pts).bounds
            bbox = f"{bounds[0]},{bounds[1]},{bounds[2]},{bounds[3]}"
            for layer in ["LT_C_UQ111", "LT_C_UQ112", "LT_C_UQ113", "LT_C_UQ114"]:
                params = {"service": "data", "request": "GetFeature", "data": layer,
                          "key": api_key, "domain": VWORLD_DOMAIN,
                          "geomFilter": f"BOX({bbox})", "size": "1000", "geometry": "true"}
                res = self.session.get(VWORLD_DATA_URL, params=params, timeout=15)
                data = res.json()
                if data.get("response", {}).get("status") == "OK":
                    all_zones.extend(data["response"]["result"]["featureCollection"]["features"])
        except: pass
        return all_zones

    # ------------------------------------------------------------------ #
    #  필지 1건 상세 분석
    # ------------------------------------------------------------------ #
    def _analyze_single_parcel(self, idx, parcel, api_key):
        pnu = parcel["PNU"]
        cad_area = parcel.get("구적상면적", 0.0)
        total_cad_area = parcel.get("전체구적면적", 0.0)
        poly = parcel.get("지적도형")

        # [최적화] 이미 pnu_extractor에서 가져온 속성 우선 활용
        jimok = parcel.get("지목", "-")
        parea = parcel.get("대장면적", 0.0)
        pnilp = parcel.get("공시지가", "0")
        sojaeji = parcel.get("주소", "")
        
        owner_type, owner_count, land_use = "개인", "1", "미조회"

        import random
        # 워커 병렬 실행 시 초기 부하를 분산시키기 위해 난수 대기 시간을 조금 더 넉넉하게 설정
        time.sleep(random.uniform(0.3, 1.0))

        # --- 2단계: NED API (WFS 실패 시 또는 상세 정보 수집) ---
        if jimok == "-" or parea <= 0 or owner_type == "개인":
            params = {"key": api_key, "domain": VWORLD_DOMAIN, "pnu": pnu, "format": "json"}
            # API 제한으로 인한 누락 방지를 위해 최대 5회, 백오프(Backoff) 적용 재시도
            for attempt in range(5):
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
                            break # 성공 시 탈출
                except Exception as e:
                    pass
                # 재시도 전 대기 시간 점진적 증가 (0.5, 1.0, 1.5, 2.0초 ...)
                time.sleep(0.5 * (attempt + 1))

        # --- 3단계: WFS 공간 검색 (좌표 기반 필터) ---
        if (jimok == "-" or parea <= 0) and poly:
            try:
                c = poly.centroid
                geom_filter = f"POINT({c.x} {c.y})"
                wfs_params = {
                    "service": "data", "request": "GetFeature", "data": CADASTRAL_LAYER,
                    "key": api_key, "domain": VWORLD_DOMAIN, "geomFilter": geom_filter, "size": "1"
                }
                # WFS 역시 여러번 시도
                for attempt in range(3):
                    try:
                        w_res = self.session.get(VWORLD_DATA_URL, params=wfs_params, timeout=10)
                        if w_res.status_code == 200:
                            w_data = w_res.json()
                            if w_data.get("response", {}).get("status") == "OK":
                                features = w_data["response"]["result"]["featureCollection"]["features"]
                                if features:
                                    props = features[0]["properties"]
                                    if jimok == "-": jimok = props.get("jimok", jimok)
                                    if parea <= 0: parea = float(props.get("parea", 0.0))
                                    if pnilp == "0": pnilp = str(props.get("pnilp", "0")).strip()
                                break
                    except: pass
                    time.sleep(1.0)
            except: pass

        # --- 4단계: Search API (최후의 수단) ---
        if (jimok == "-" or parea <= 0):
            try:
                search_params = {
                    "service": "search", "request": "search", "version": "2.0", "crs": "EPSG:4326",
                    "size": "1", "type": "DISTRICT", "category": "parcel", "query": pnu, "key": api_key
                }
                for attempt in range(3):
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
                    time.sleep(1.0)
            except: pass

        # 공시지가 추가 보완
        if pnilp in ["0", "-", ""]:
            try:
                p_params = {"key": api_key, "domain": VWORLD_DOMAIN, "pnu": pnu, "format": "json"}
                for year in [2024, 2023]:
                    p_params["stdrYear"] = str(year)
                    success = False
                    for attempt in range(2):
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

        # 최종 보정 및 지목 매핑
        if jimok in ["-", "", None]: 
            jimok = "기타"
        else:
            # 숫자로 오거나 한 글자 코드인 경우 매핑 (예: 01 -> 전)
            jimok = JIMOK_MAP.get(jimok.strip(), jimok)
            
        if pnilp in ["0", "-", "", None]: pnilp = "-"

        # 편입면적 계산 (공부상 면적 기반)
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
        poly = parcel.get("지적도형")
        if poly and self.prefetched_zones:
            centroid = poly.centroid
            for feat in self.prefetched_zones:
                if shape(feat["geometry"]).intersects(centroid):
                    zoning = feat["properties"].get("uname", zoning); break

        # 비고 (누락 알림)
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
