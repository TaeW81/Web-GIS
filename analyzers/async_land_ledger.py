"""
비동기(Async) 토지대장 분석기 — aiohttp를 활용한 초고속 API 통신 엔진
"""
import asyncio
import aiohttp
import time
import re
import urllib.parse
import concurrent.futures
from shapely.geometry import shape

from analyzers.base_analyzer import BaseAnalyzer
from modules.land_cache import LandDataCache
from config import VWORLD_DATA_URL, VWORLD_DOMAIN, CADASTRAL_LAYER

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

class AsyncLandLedgerAnalyzer(BaseAnalyzer):
    name = "토지조서 (편입면적/공시지가 등)"
    description = "초고속 비동기 엔진으로 지적 속성, 소유자, 편입 면적을 분석합니다."

    def __init__(self):
        super().__init__()
        self.cache = LandDataCache()

    async def _fetch_with_retry(self, session, url, params, max_retries=3, delay=0.5):
        for attempt in range(max_retries):
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        try:
                            return await response.json()
                        except:
                            text = await response.text()
                            if "OpenAPI Error" in text:
                                return {"error": "API_LIMIT"}
            except Exception:
                pass
            await asyncio.sleep(delay * (attempt + 1))
        return None

    async def _get_ned_data(self, session, sem, pnu, api_key, max_retries=5):
        async with sem:
            url = f"{VWORLD_DATA_URL}/wfs"
            params = {
                "key": api_key, "domain": VWORLD_DOMAIN,
                "SERVICE": "WFS", "VERSION": "1.1.0", "REQUEST": "GetFeature",
                "TYPENAME": "lp_pa_cbnd_bubun", "OUTPUT": "application/json",
                "EXCEPTIONS": "text/xml", "SRSNAME": "EPSG:5186",
                "CQL_FILTER": f"pnu='{pnu}'"
            }
            res = await self._fetch_with_retry(session, url, params, max_retries)
            if res and "features" in res and len(res["features"]) > 0:
                props = res["features"][0]["properties"]
                return {
                    "jimok": props.get("jibun", "")[-1:] if props.get("jibun") and not props.get("jibun")[-1:].isdigit() else "",
                    "owner": props.get("own_gbn", ""),
                    "area": float(props.get("parea", 0.0))
                }
            return None

    async def _get_address(self, session, sem, pnu, api_key, max_retries=3):
        async with sem:
            url = f"{VWORLD_DATA_URL}/search"
            params = {
                "service": "search", "request": "search", "version": "2.0",
                "crs": "EPSG:4326", "size": "1", "query": pnu,
                "type": "address", "category": "parcel", "format": "json",
                "errorformat": "json", "key": api_key
            }
            res = await self._fetch_with_retry(session, url, params, max_retries)
            if res and "response" in res and res["response"]["status"] == "OK":
                items = res["response"].get("result", {}).get("items", [])
                if items: return clean_address(items[0].get("address", {}).get("bldnm", ""))
            return ""

    async def _get_pnilp(self, session, sem, pnu, api_key, max_retries=2):
        async with sem:
            url = f"{VWORLD_DATA_URL}/data"
            params = {
                "service": "data", "request": "GetFeature",
                "data": "LT_C_LIDUPGQ", "key": api_key, "domain": VWORLD_DOMAIN,
                "attrFilter": f"pnu:=:{pnu}"
            }
            res = await self._fetch_with_retry(session, url, params, max_retries)
            if res and res.get("response", {}).get("status") == "OK":
                feats = res["response"].get("result", {}).get("featureCollection", {}).get("features", [])
                if feats: return str(feats[0]["properties"].get("pnilp", "누락"))
            return "누락"

    async def _process_pnu(self, session, sem, pnu_info, api_key, aggressive=False):
        pnu = pnu_info["PNU"]
        
        # 캐시 확인 (1차에서만)
        if not aggressive:
            cached = self.cache.get(pnu)
            if cached:
                # 불량 캐시가 아니면 즉시 반환
                if cached["jimok"] not in ["-", "누락"] and cached["parea"] > 0 and cached["pnilp"] not in ["-", "누락"]:
                    return {"pnu": pnu, "data": {
                        "jimok": cached["jimok"],
                        "owner": cached["owner_type"],
                        "area": cached["parea"],
                        "address": cached["sojaeji"],
                        "pnilp": cached["pnilp"]
                    }, "cached": True}

        max_r_ned = 7 if aggressive else 5
        max_r_addr = 5 if aggressive else 3
        
        # 동시에 3개 API 찌르기 (NED, 주소, 공시지가)
        task_ned = self._get_ned_data(session, sem, pnu, api_key, max_retries=max_r_ned)
        task_addr = self._get_address(session, sem, pnu, api_key, max_retries=max_r_addr)
        task_pnilp = self._get_pnilp(session, sem, pnu, api_key, max_retries=max_r_addr)
        
        ned_res, addr_res, pnilp_res = await asyncio.gather(task_ned, task_addr, task_pnilp)
        
        data = {
            "jimok": ned_res["jimok"] if ned_res else "누락",
            "owner": ned_res["owner"] if ned_res else "누락",
            "area": ned_res["area"] if ned_res else 0.0,
            "address": addr_res if addr_res else "주소 불명",
            "pnilp": pnilp_res if pnilp_res else "누락"
        }
        return {"pnu": pnu, "data": data, "cached": False}

    def _prefetch_zoning_data(self, pnu_list, api_key):
        import requests
        polys = [p.get("지적도형") for p in pnu_list if p.get("지적도형")]
        if not polys: return []
        
        from shapely.ops import unary_union
        union_poly = unary_union(polys)
        minx, miny, maxx, maxy = union_poly.bounds
        bbox = f"{minx},{miny},{maxx},{maxy}"
        
        zones = []
        layers = ["LT_C_UQ111", "LT_C_UQ112", "LT_C_UQ113", "LT_C_UQ114"]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            def fetch_zone(layer):
                url = f"{VWORLD_DATA_URL}/data"
                params = {
                    "service": "data", "request": "GetFeature", "data": layer,
                    "key": api_key, "domain": VWORLD_DOMAIN,
                    "geomFilter": f"BOX({bbox})", "size": "1000"
                }
                for _ in range(3):
                    try:
                        res = requests.get(url, params=params, timeout=10)
                        data = res.json()
                        feats = data.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [])
                        return feats
                    except:
                        time.sleep(1)
                return []
                
            futures = [executor.submit(fetch_zone, layer) for layer in layers]
            for f in concurrent.futures.as_completed(futures):
                zones.extend(f.result())
        return zones

    async def _async_analyze(self, pnu_list, api_key):
        sem = asyncio.Semaphore(50) # 한 번에 50개 동시 연결 허용
        conn = aiohttp.TCPConnector(limit=100)
        timeout = aiohttp.ClientTimeout(total=60)
        
        results_map = {}
        missing_pnus = []
        new_cache_entries = []
        pnu_map = {p["PNU"]: p for p in pnu_list}
        
        async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
            # 1차 분석
            tasks = [self._process_pnu(session, sem, p, api_key) for p in pnu_list]
            first_results = await asyncio.gather(*tasks)
            
            for res in first_results:
                pnu = res["pnu"]
                data = res["data"]
                results_map[pnu] = data
                
                # 누락 여부 검사
                if data["area"] == 0 or data["pnilp"] in ["누락", "-"] or data["owner"] in ["누락", "-"]:
                    missing_pnus.append(pnu_map[pnu])
                elif not res.get("cached"):
                    new_cache_entries.append((pnu, data))
            
            # 2차 보완 분석 (Aggressive Mode)
            if missing_pnus:
                print(f"    → 누락 필지 {len(missing_pnus)}건 감지. 2차 비동기 보완 분석 시작...")
                tasks2 = [self._process_pnu(session, sem, p, api_key, aggressive=True) for p in missing_pnus]
                second_results = await asyncio.gather(*tasks2)
                
                for res in second_results:
                    pnu = res["pnu"]
                    data = res["data"]
                    results_map[pnu] = data # 덮어쓰기
                    
                    if data["area"] > 0 and data["pnilp"] != "누락":
                        new_cache_entries.append((pnu, data))

        # DB 일괄 저장 (Bulk Insert)
        cache_items = []
        for pnu, data in new_cache_entries:
            cache_items.append((pnu, {
                "jimok": data["jimok"],
                "parea": data["area"],
                "pnilp": data["pnilp"],
                "owner_type": data["owner"],
                "sojaeji": data["address"]
            }))
        self.cache.put_batch(cache_items)
            
        return results_map

    def analyze(self, pnu_list, api_key):
        t_start = time.time()
        
        self.cache.reset_stats()
        print(f">>> [캐시] 로컬 DB 로드 (저장된 필지: {self.cache.get_cache_size()}건)")

        # 용도지역 (사전 로딩 - 동기)
        t_zone = time.time()
        print(">>> [1단계] 용도지역 수집 중 (병렬)...")
        prefetched_zones = self._prefetch_zoning_data(pnu_list, api_key)
        print(f"    → 용도지역 {len(prefetched_zones)}건 수집 완료 ({time.time()-t_zone:.1f}초)")

        # 비동기 속성 데이터 조회 실행
        t_attr = time.time()
        print(f">>> [2단계] 비동기 초고속 속성 조회 시작 (대상: {len(pnu_list)}건)...")
        
        # Streamlit 환경에서 asyncio loop 처리
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 이미 실행중인 루프가 있다면 둥지 틀기 방지용 thread 또는 별도 루프 사용해야 하지만,
                # 보통 Streamlit 스크립트 실행 스레드에서는 새 루프 생성이 안전함.
                import nest_asyncio
                nest_asyncio.apply()
                results_map = loop.run_until_complete(self._async_analyze(pnu_list, api_key))
            else:
                results_map = loop.run_until_complete(self._async_analyze(pnu_list, api_key))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            results_map = loop.run_until_complete(self._async_analyze(pnu_list, api_key))

        print(f"    → 속성 분석 완료 ({time.time()-t_attr:.1f}초)")
        
        stats = self.cache.get_stats()
        print(f"    → [캐시 통계] 히트: {stats['hits']}건, 미스: {stats['misses']}건")

        # 결과 조립
        final_results = []
        for i, parcel in enumerate(pnu_list, 1):
            pnu = parcel["PNU"]
            attr = results_map.get(pnu, {})
            
            jimok = JIMOK_MAP.get(attr.get("jimok", ""), attr.get("jimok", ""))
            owner_type = attr.get("owner", "확인불가")
            parea = attr.get("area", 0.0)
            pnilp = attr.get("pnilp", "누락")
            address = attr.get("address", parcel.get("소재지", ""))
            
            # 용도지역 & 산지구분 로직
            poly = parcel.get("지적도형")
            zoning_list = []
            mountain_zones = []
            if poly and prefetched_zones:
                centroid = poly.centroid
                for feat in prefetched_zones:
                    if shape(feat["geometry"]).intersects(centroid):
                        uname = feat["properties"].get("uname", "")
                        if uname and uname not in zoning_list:
                            zoning_list.append(uname)
                            if "산지" in uname or "임업용" in uname or "공익용" in uname:
                                mountain_zones.append(uname)
                                
            zoning = ", ".join(zoning_list) if zoning_list else "미조회"
            mountain_zone = ", ".join(mountain_zones) if mountain_zones else "-"
            
            # 면적 계산
            try: included_area = round(poly.area, 1) if poly else 0.0
            except: included_area = 0.0
            
            inclusion_type = "전체편입"
            if parea > 0 and included_area > 0:
                ratio = included_area / parea
                if ratio > 1.0 or ratio > 0.95: 
                    included_area = parea
                elif ratio < 0.95:
                    inclusion_type = "부분편입"
                    
            final_results.append({
                "일련번호": i,
                "PNU": pnu,
                "소재지": address,
                "필지구분": parcel.get("필지구분", ""),
                "본번": parcel.get("본번", ""),
                "부번": parcel.get("부번", ""),
                "지목": jimok,
                "소유자": owner_type,
                "소유자수": 1,
                "공시지가": pnilp,
                "대장면적(㎡)": parea,
                "편입면적(㎡)": included_area,
                "편입구분": inclusion_type,
                "용도지역": zoning,
                "산지구분": mountain_zone,
                "이용상황": "",
                "비고": ""
            })

        print(f">>> [총 소요 시간] 토지조서 분석 완료: {time.time()-t_start:.1f}초")
        return final_results
