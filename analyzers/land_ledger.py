"""
토지조서(편입면적 포함) 분석기

데이터 소스: 브이월드 Data API (LP_PA_CBND_BUBUN)
구적 면적(CAD 면적)을 기반으로 편입 여부를 판별하고, 엑셀 양식에 맞춘 데이터를 생성합니다.
"""
import requests
from analyzers.base_analyzer import BaseAnalyzer
from config import VWORLD_DATA_URL, VWORLD_DOMAIN, CADASTRAL_LAYER

class LandLedgerAnalyzer(BaseAnalyzer):
    name = "토지조서 (편입면적/공시지가 등)"
    description = "사업부지 내 편입되는 지번의 공부상 면적, 편입면적, 공시지가 등을 분석하여 조서를 작성합니다."

    def analyze(self, pnu_list, api_key):
        """
        PNU 리스트의 각 필지에 대해 토지조서 양식에 맞는 데이터를 생성합니다.
        
        Args:
            pnu_list: [{'PNU': ..., '주소': ..., '지번': ..., '구적상면적': ..., '전체구적면적': ...}, ...]
        """
        results = []
        
        for idx, parcel in enumerate(pnu_list, start=1):
            pnu = parcel["PNU"]
            address = parcel["주소"]
            jibun = parcel.get("지번", "")
            cad_area = parcel.get("구적상면적", 0.0)
            total_cad_area = parcel.get("전체구적면적", 0.0)
            
            # 1. 브이월드 NED API(토지임야정보) 호출하여 면적, 지목, 소유구분 가져오기
            ned_url = "https://api.vworld.kr/ned/data/ladfrlList"
            params = {
                "key": api_key,
                "domain": VWORLD_DOMAIN,
                "pnu": pnu,
                "format": "json",
                "numOfRows": "10",
                "pageNo": "1"
            }
            
            jimok = "-"
            pnilp = "-"
            parea = 0.0
            owner_type = ""
            owner_count = ""
            
            try:
                res = requests.get(ned_url, params=params, timeout=10)
                data = res.json()
                
                # NED API 응답 구조: data['ladfrlVOList']['ladfrlVOList'] (리스트 형태)
                if "ladfrlVOList" in data and "ladfrlVOList" in data["ladfrlVOList"]:
                    info = data["ladfrlVOList"]["ladfrlVOList"][0]
                    jimok = info.get("lndcgrCodeNm", "-")
                    owner_type = info.get("posesnSeCodeNm", "") # 소유자 (사유지, 국유지 등)
                    
                    # 공유인수 (소유자수 계산)
                    cnrs = info.get("cnrsPsnCo", "0")
                    if str(cnrs).isdigit():
                        owner_count = str(int(cnrs) + 1)
                    else:
                        owner_count = "1"
                        
                    try:
                        parea = float(info.get("lndpclAr", 0.0))
                    except (ValueError, TypeError):
                        parea = 0.0

                # 1-2. 브이월드 NED API(개별공시지가속성조회) 호출하여 공시지가 가져오기
                price_url = "https://api.vworld.kr/ned/data/getIndvdLandPriceAttr"
                from datetime import datetime
                curr_year = datetime.now().year
                
                # 최신 연도부터 조회를 시도
                for year in [curr_year, curr_year - 1]:
                    price_params = params.copy()
                    price_params["stdrYear"] = str(year)
                    
                    res_price = requests.get(price_url, params=price_params, timeout=10)
                    data_price = res_price.json()
                    
                    if "indvdLandPrices" in data_price and "field" in data_price["indvdLandPrices"]:
                        price_info = data_price["indvdLandPrices"]["field"][0]
                        pnilp = price_info.get("pblntfPclnd", "-")
                        if pnilp != "-":
                            break

                # 만약 면적이나 공시지가 값이 없다면 기존 지적도 API로 폴백
                if parea == 0.0 or pnilp == "-":
                    fallback_params = {
                        "service": "data", "request": "GetFeature", "data": CADASTRAL_LAYER,
                        "key": api_key, "domain": VWORLD_DOMAIN, "attrFilter": f"pnu:like:{pnu}",
                    }
                    res_fb = requests.get(VWORLD_DATA_URL, params=fallback_params, timeout=10)
                    data_fb = res_fb.json()
                    if data_fb.get("response", {}).get("status") == "OK":
                        props = data_fb["response"]["result"]["featureCollection"]["features"][0]["properties"]
                        if jimok == "-": jimok = props.get("jimok", jimok)
                        if pnilp == "-": pnilp = props.get("pnilp", pnilp)
                        try:
                            parea = float(props.get("parea", parea))
                        except: pass

            except Exception as e:
                pass

            # 편입 구분 및 편입 면적 계산
            # CAD 면적 비율이 99% 이상이거나, CAD 전체 면적과 대장 면적의 오차가 매우 적을 때 등
            # 간단히 교차 면적이 전체 CAD 면적의 99% 이상이면 전부편입으로 간주
            if total_cad_area > 0 and (cad_area / total_cad_area) >= 0.99:
                inclusion_type = "전부편입"
                included_area = parea # 대장면적을 그대로 사용
            else:
                inclusion_type = "부분편입"
                included_area = cad_area # 구적상 교차 면적 사용
            
            # 소재지 파싱 (API에서 법정동명 `ldCodeNm` 제공 시 우선 사용)
            sojaeji_api = info.get("ldCodeNm", "")
            if sojaeji_api:
                sojaeji = sojaeji_api
            else:
                sojaeji = address
                if jibun and address.endswith(jibun):
                    sojaeji = address[:-len(jibun)].strip()
            
            # PNU 파싱 (필지구분, 본번, 부번)
            parcel_type = "일반"
            if len(pnu) == 19:
                p_type_code = pnu[10]
                parcel_type = "산" if p_type_code == "2" else "일반"
                main_jibun = str(int(pnu[11:15]))
                sub_jibun = str(int(pnu[15:19]))
                if sub_jibun == "0":
                    sub_jibun = ""
                
                # 추가적으로 API ldCodeNm이 없을 때를 대비한 정밀 지번 제거
                if not sojaeji_api:
                    j_str = ("산" if p_type_code == "2" else "") + main_jibun + (f"-{sub_jibun}" if sub_jibun else "")
                    j_str_space = ("산 " if p_type_code == "2" else "") + main_jibun + (f"-{sub_jibun}" if sub_jibun else "")
                    if sojaeji.endswith(j_str): sojaeji = sojaeji[:-len(j_str)].strip()
                    elif sojaeji.endswith(j_str_space): sojaeji = sojaeji[:-len(j_str_space)].strip()
            else:
                main_jibun = jibun
                sub_jibun = ""
                
            # 용도지역 추출 (LT_C_UQ111, LT_C_UQ112, LT_C_UQ113)
            zoning_info = ""
            try:
                # 필지의 중심점 구하기 (지적도형 폴리곤의 centroid)
                poly = parcel.get("지적도형")
                if poly:
                    centroid = poly.centroid
                    geom_filter = f"POINT({centroid.x} {centroid.y})"
                    
                    found_zones = []
                    # 핵심 레이어: LT_C_UQ111 (용도지역), 필요시 112, 113 추가 가능
                    for layer in ["LT_C_UQ111"]:
                        z_params = {
                            "service": "data", "request": "GetFeature", "data": layer,
                            "key": api_key, "domain": VWORLD_DOMAIN,
                            "geomFilter": geom_filter, "geometry": "false", "size": "10"
                        }
                        z_res = requests.get(VWORLD_DATA_URL, params=z_params, timeout=10)
                        if z_res.status_code == 200:
                            z_data = z_res.json()
                            features = z_data.get("response", {}).get("result", {}).get("featureCollection", {}).get("features", [])
                            for feat in features:
                                uname = feat["properties"].get("uname")
                                if uname:
                                    found_zones.append(uname)
                                    
                    zoning_info = ", ".join(sorted(set(found_zones))) if found_zones else "해당없음"
                else:
                    zoning_info = "도형없음"
            except Exception:
                zoning_info = "조회실패"
            
            # 이용상황 추정 (VWorld API 미제공으로 지목/소유자/용도지역 기반 추론)
            def _estimate_land_use(jmk, owner, zon):
                pub_owners = ["국유지", "시.도유지", "군유지", "시.군.구유지", "도유지"]
                infra_jmk = ["도로", "하천", "구거", "제방", "유지", "수도용지"]
                if owner in pub_owners or jmk in infra_jmk:
                    return "국ㆍ공유지"
                pub_other = ["학교용지", "공원", "체육용지", "철도용지", "주차장", "종교용지", "사적지", "묘지", "창고용지"]
                if jmk in pub_other:
                    return "공공기타"
                if jmk in ["대", "장"]: # 대지, 공장용지
                    if "상업" in zon:
                        return "상업용,주상용"
                    return "주거용,공업용"
                return "" # 전, 답, 임야 등은 필요에 따라 추가
                
            use_sittn = _estimate_land_use(jimok, owner_type, zoning_info)

            # 엑셀 양식에 맞춘 결과 딕셔너리 구성
            results.append({
                "일련번호": idx,
                "PNU": pnu,
                "소재지": sojaeji,
                "필지구분": parcel_type,
                "본번": main_jibun,
                "부번": sub_jibun,
                "지목": jimok,
                "소유자": owner_type,
                "소유자수": owner_count,
                "공시지가": pnilp,
                "대장면적(㎡)": parea,
                "편입면적(㎡)": round(included_area, 2),
                "편입구분": inclusion_type,
                "용도지역": zoning_info,
                "이용상황": use_sittn,
                "비고": ""
            })
            
        return results

    def get_columns(self):
        return [
            "일련번호", "PNU", "소재지", "필지구분", "본번", "부번", "지목", 
            "소유자", "소유자수", "공시지가", "대장면적(㎡)", "편입면적(㎡)", 
            "편입구분", "용도지역", "이용상황", "비고"
        ]
