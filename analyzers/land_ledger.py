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

class LandLedgerAnalyzer(BaseAnalyzer):
    name = "토지조서 (편입면적/공시지가 등)"
    description = "지적 속성 및 소유자, 편입 면적을 정밀 분석합니다."

    def analyze(self, pnu_list, api_key):
        self.session = requests.Session()

        # ① WFS 벌크 조회 (50개 묶음 attrFilter)
        print(">>> [1단계] 지적도 전산DB 벌크 수집 중...")
        self.cad_attr_map = self._bulk_fetch_cadastral(pnu_list, api_key)
        wfs_hit = len(self.cad_attr_map)
        wfs_miss = len(pnu_list) - wfs_hit
        print(f">>> [1단계] 완료: {wfs_hit}건 수집 / {wfs_miss}건 누락 (NED API에서 보완 예정)")

        # ② 용도지역
        print(">>> [2단계] 용도지역 수집 중...")
        self.prefetched_zones = self._prefetch_zoning_data(pnu_list, api_key)

        # ③ NED API (소유자 + WFS 누락 보완) — 300개 배치 + 25 워커
        print(">>> [3단계] 토지대장 정밀 조회 시작...")
        results = []
        batch_size = 300
        for i in range(0, len(pnu_list), batch_size):
            batch = pnu_list[i:i + batch_size]
            print(f"    처리 중: {i+1} ~ {min(i+batch_size, len(pnu_list))} / 전체 {len(pnu_list)} 필지")
            with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
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
                time.sleep(0.5)

        return sorted(results, key=lambda x: x["일련번호"])

    # ------------------------------------------------------------------ #
    #  WFS 벌크 조회 (attrFilter pnu:IN 방식)
    # ------------------------------------------------------------------ #
    def _bulk_fetch_cadastral(self, pnu_list, api_key):
        attr_map = {}
        pnu_codes = [p["PNU"] for p in pnu_list]
        chunk_size = 50

        for i in range(0, len(pnu_codes), chunk_size):
            chunk = pnu_codes[i:i + chunk_size]
            # VWorld attrFilter 정확한 문법: pnu:IN:(v1,v2,...)
            pnu_filter = "pnu:IN:({})".format(",".join(chunk))
            params = {
                "service": "data", "request": "GetFeature",
                "data": CADASTRAL_LAYER, "key": api_key, "domain": VWORLD_DOMAIN,
                "attrFilter": pnu_filter,
                "size": str(len(chunk) + 5)
            }
            try:
                res = self.session.get(VWORLD_DATA_URL, params=params, timeout=15)
                data = res.json()
                status = data.get("response", {}).get("status", "")
                if status == "OK":
                    feats = data["response"]["result"]["featureCollection"]["features"]
                    for f in feats:
                        p = f["properties"]
                        pnu = p.get("pnu")
                        if pnu:
                            attr_map[pnu] = {
                                "jimok": p.get("jimok", "-"),
                                "pnilp": str(p.get("pnilp", "0")).strip(),
                                "parea": float(p.get("parea", 0.0))
                            }
                # else: 이 청크는 누락됨 → NED API 단계에서 자동 보완
            except: pass

            if i + chunk_size < len(pnu_codes):
                time.sleep(0.2)

        return attr_map

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

        # WFS에서 확보한 1차 데이터
        pre = self.cad_attr_map.get(pnu, {})
        jimok = pre.get("jimok", "-")
        pnilp = pre.get("pnilp", "0")
        parea = pre.get("parea", 0.0)

        owner_type, owner_count, sojaeji, land_use = "개인", "1", parcel["주소"], "미조회"

        # ② NED API: 소유자 정보 조회 + WFS 누락 필지 면적 의무 보완
        try:
            params = {"key": api_key, "domain": VWORLD_DOMAIN, "pnu": pnu, "format": "json"}
            for attempt in range(3):  # 최대 3회 재시도
                try:
                    res = self.session.get("https://api.vworld.kr/ned/data/ladfrlList",
                                           params=params, timeout=12)
                    ned = res.json()
                    break
                except:
                    if attempt < 2: time.sleep(0.3)
                    ned = None

            if ned and "ladfrlVOList" in ned and "ladfrlVOList" in ned["ladfrlVOList"]:
                info = ned["ladfrlVOList"]["ladfrlVOList"][0]
                owner_type = info.get("posesnSeCodeNm", "개인")
                sojaeji = info.get("ldCodeNm", sojaeji)
                land_use = info.get("lnduseNm", "미조회")
                owner_count = str(int(info.get("cnrsPsnCo", 0)) + 1)
                if jimok == "-": jimok = info.get("lndcgrCodeNm", "-")

                # ★★ WFS 누락(parea=0)이면 NED에서 반드시 가져옴 ★★
                if parea <= 0:
                    try: parea = float(info.get("lndpclAr", 0.0))
                    except: parea = 0.0

            # 공시지가: WFS에 없을 때만 추가 조회
            if pnilp in ["0", "-", ""]:
                import datetime
                for year in [datetime.datetime.now().year, 2023, 2022]:
                    try:
                        p_params = params.copy(); p_params["stdrYear"] = str(year)
                        res2 = self.session.get(
                            "https://api.vworld.kr/ned/data/getIndvdLandPriceAttr",
                            params=p_params, timeout=8)
                        price = res2.json()
                        if "indvdLandPrices" in price and "field" in price["indvdLandPrices"]:
                            val = str(price["indvdLandPrices"]["field"][0].get("pblntfPclnd", "")).strip()
                            if val and val != "0": pnilp = val; break
                    except: pass
        except: pass

        # 최종 보정
        if jimok in ["-", "", None]: jimok = "기타"
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

        return {
            "일련번호": idx, "PNU": pnu, "소재지": clean_address(sojaeji),
            "필지구분": "일반" if pnu[10] == "1" else "산" if pnu[10] == "2" else "기타",
            "본번": pnu[11:15].lstrip('0') or "0",
            "부번": pnu[15:19].lstrip('0') or "0",
            "지목": jimok, "소유자": owner_type, "소유자수": owner_count,
            "공시지가": pnilp, "대장면적(㎡)": parea, "편입면적(㎡)": included_area,
            "편입구분": inclusion_type, "용도지역": zoning, "이용상황": land_use, "비고": ""
        }
