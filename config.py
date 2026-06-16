"""
프로젝트 전역 설정 파일
- API 키, 좌표계, 레이어 코드 등을 한 곳에서 관리합니다.
- 키 우선순위: ① Streamlit secrets(웹 배포) → ② .env/환경변수(로컬) → ③ 기본값
"""
import os
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드 (로컬 실행용)
load_dotenv()


def _load_st_secrets():
    """Streamlit secrets를 dict로 안전 로드 (secrets.toml 없으면 빈 dict)."""
    try:
        import streamlit as st
        return dict(st.secrets)
    except Exception:
        return {}


_ST_SECRETS = _load_st_secrets()


def get_secret(name, default=""):
    """① Streamlit secrets → ② 환경변수/.env → ③ 기본값 순으로 값을 가져온다."""
    if name in _ST_SECRETS:
        return _ST_SECRETS[name]
    return os.getenv(name, default)


# ===== 웹 배포 모드 플래그 =====
#   로컬 실행 시 미설정(0) → 데스크톱 기능 사용 가능
#   웹 배포 시 secrets/env에 KH_WEB_MODE=1 → 데스크톱 전용 기능 숨김 + 로그인 보호
IS_WEB_MODE = str(get_secret("KH_WEB_MODE", "0")).strip().lower() in ("1", "true", "yes", "on")

# ===== API 키 =====
VWORLD_KEY = get_secret("VWORLD_KEY", "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1")
NIE_KEY = get_secret("NIE_KEY", "0b1a73c4402f5cc749ca03709d2850131f4c1e62b27c87ea7bdbe8dd19299bd7")
NGII_KEY = get_secret("NGII_KEY", "05A66BC66F48B4624F486A8590E4A98810E0DFB7B3")
ECVAM_KEY = get_secret("ECVAM_KEY", "GGDM-AU7W-FRD0-UPSC")

# ===== 분석 및 보고서 설정 =====
CADASTRAL_LAYER = "LP_PA_CBND_BUBUN"
OWNER_CATEGORIES = {
    "국유지": ["국", "기획재정부", "국토교통부", "국방부", "환경부", "산림청", "철도청", "경찰청", "교육부"],
    "공유지": ["시", "군", "구", "도", "서울특별시", "경기도", "강원도", "충청", "전라", "경상", "제주"],
    "공공기관": ["공사", "LH", "SH", "한국도로공사", "한국전력공사", "수자원공사", "철도공사"],
    "사유지": ["개인", "법인", "종중", "사찰", "교회", "단체", "기타"],
}

# ===== 좌표계 설정 =====
SOURCE_CRS = "EPSG:5186"   # 기본 캐드 도면 좌표계 (GRS80 중부원점)
TARGET_CRS = "EPSG:4326"   # WGS84 GPS 좌표계

# 한국 주요 좌표계 (사용자 요청 UI 기반 매핑)
KOREA_CRS = {
    "GRS80(현행)": {
        "서부": "EPSG:5185",
        "중부": "EPSG:5186",
        "동부": "EPSG:5187",
        "동해": "EPSG:5188",
        "UTMK": "EPSG:5179"
    },
    "베셀(Bessel)": {
        "서부": "EPSG:5173",
        "중부": "EPSG:5174",
        "동부": "EPSG:5176",
        "동해": "EPSG:5177",
        "제주": "EPSG:5175"
    },
    "WGS84/Google": {
        "WGS84": "EPSG:4326",
        "GoogleTM": "EPSG:3857"
    },
    "GRS80(과거)": {
        "서부": "EPSG:5181",
        "중부": "EPSG:5182",
        "동부": "EPSG:5183",
        "동해": "EPSG:5184",
        "제주": "EPSG:5180"
    }
}

# 한국 주요 좌표계 원점 위치 (Lon, Lat)
KOREA_CRS_ORIGINS = {
    "서부": (125.0, 38.0),
    "중부": (127.0, 38.0),
    "동부": (129.0, 38.0),
    "동해": (131.0, 38.0),
    "UTMK": (127.5, 38.0),
    "제주": (126.500289, 33.500408),
    "WGS84": (127.0, 38.0),
    "GoogleTM": (127.0, 38.0),
}

# ===== API End Points =====
# V-World 인증키에 등록한 도메인과 '일치'해야 함.
#   로컬: http://localhost (기본) / 웹 배포: secrets에 VWORLD_DOMAIN="https://...streamlit.app"
VWORLD_DOMAIN = get_secret("VWORLD_DOMAIN", "http://localhost")
VWORLD_DATA_URL = "https://api.vworld.kr/req/data"
VWORLD_SEARCH_URL = "https://api.vworld.kr/req/search"
VWORLD_WMS_URL = "https://api.vworld.kr/req/wms"
NIE_ECO_URL = "https://apis.data.go.kr/B553084/ecoapi/EcologyzmpService"
NIE_WMS_URL = "https://apis.data.go.kr/B553084/ecoapi/EcologyzmpService/wms/getEcologyzmpWMS"
NIE_WFS_URL = "https://apis.data.go.kr/B553084/ecoapi/EcologyzmpService/wfs/getEcologyzmpWFS"
ECVAM_WMS_URL = "https://ecvam.neins.go.kr/apicall.do"

# ===== VWorld WMTS 배경지도 타일 URL =====
VWORLD_TILE_URLS = {
    "일반지도": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Base/{{z}}/{{y}}/{{x}}.png",
    "위성영상": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Satellite/{{z}}/{{y}}/{{x}}.jpeg",
    "하이브리드": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Hybrid/{{z}}/{{y}}/{{x}}.png",
}

# ===== VWorld WMS 오버레이 레이어 카테고리 및 범례 URL 설정 =====
# ===== WMS 범례 URL 설정 =====
VWORLD_LEGEND_URL = "http://api.vworld.kr/req/image?key={key}&service=image&request=GetLegendGraphic&format=png&type=ALL&layer={layer}&style={layer}&LEGEND_OPTIONS=forceTitle:off"
NIE_LEGEND_URL = "{base_url}?ServiceKey={key}&service=WMS&request=GetLegendGraphic&format=image/png&layer={layer}"
ECVAM_LEGEND_URL = "https://ecvam.neins.go.kr/apicall.do?APIKEY={key}&SERVICE=WMS&REQUEST=GetLegendGraphic&FORMAT=image/png&LAYER={layer}&VERSION=1.1.0"

VWORLD_WMS_CATEGORIES = {
    "기본 및 지적": {
        "지적도": "LP_PA_CBND_BUBUN",
        "사업지구경계도": "LT_C_LHZONE",
        "토지이용계획도": "LT_C_LHBLPN",
        "도로명주소건물": "LT_C_SPBD",
        "도로명주소도로": "LT_L_SPRD",
        "국가지명": "LT_P_NSNMSSITENM",
    },
    "행정경계": {
        "광역시도": "LT_C_ADSIDO",
        "시군구": "LT_C_ADSIGG",
        "읍면동": "LT_C_ADEMD",
        "리": "LT_C_ADRI",
    },
    "국토계획 (용도지역/지구/구역)": {
        "도시지역": "LT_C_UQ111",
        "관리지역": "LT_C_UQ112",
        "농림지역": "LT_C_UQ113",
        "자연환경보전지역": "LT_C_UQ114",
        "개발진흥지구": "LT_C_UQ129",
        "경관지구": "LT_C_UQ121",
        "고도지구": "LT_C_UQ123",
        "미관지구": "LT_C_UQ122",
        "방재지구": "LT_C_UQ125",
        "방화지구": "LT_C_UQ124",
        "보존지구": "LT_C_UQ126",
        "시설보호지구": "LT_C_UQ127",
        "취락지구": "LT_C_UQ128",
        "특정용도제한지구": "LT_C_UQ130",
        "개발제한구역": "LT_C_UD801",
        "국토계획구역": "LT_C_UQ141",
        "도시자연공원구역": "LT_C_UQ162",
        "수산자원보호구역": "LT_C_WGISARFISHER",
        "시가화조정구역": "LT_C_UQ161",
        "지구단위계획": "LT_C_UPISUQ161",
        "개발행위허가제한지역": "LT_C_UPISUQ171",
        "개발행위허가필지": "LT_C_UPISUQ174",
        "기반시설부담구역": "LT_C_UPISUQ173",
        "토지거래계약에관한허가구역": "LT_C_UPISUQ175",
    },
    "도시계획시설": {
        "도시계획(공간시설)": "LT_C_UPISUQ153",
        "도시계획(공공문화체육시설)": "LT_C_UPISUQ155",
        "도시계획(교통시설)": "LT_C_UPISUQ152",
        "도시계획(기타기반시설)": "LT_C_UPISUQ159",
        "도시계획(도로)": "LT_C_UPISUQ151",
        "도시계획(방재시설)": "LT_C_UPISUQ156",
        "도시계획(보건위생시설)": "LT_C_UPISUQ157",
        "도시계획(유통공급시설)": "LT_C_UPISUQ154",
        "도시계획(환경기초시설)": "LT_C_UPISUQ158",
    },
    "환경/보호/재해": {
        "가축사육제한구역": "LT_C_UM000",
        "대기환경규제지역": "LT_C_UM301",
        "습지보호지역": "LT_C_UM901",
        "야생동식물보호": "LT_C_UM221",
        "학교환경위생정화구역": "LT_C_UO101",
        "급경사재해예방지역": "LT_C_UP401",
        "산불위험예측지도": "LT_C_KFDRSSIGUGRADE",
        "재해위험지구": "LT_C_UP201",
        "지진대피소": "LT_P_EDRSE002",
        "지진해일대피소": "LT_P_ETQSHELTER",
        "생태계경관보전지역": "LT_C_WGISARECO",
        "습지보호구역": "LT_C_WGISARWET",
        "해안침수(100년빈도)": "LT_C_CDFRS100FRQ",
        "해안침수(최대범람)": "LT_C_CDFRSMAXFRQ",
        "산림보호구역": "LT_C_UF151",
        "백두대간보호지역": "LT_C_UF901",
    },
    "수자원/하천/연안": {
        "상수원보호": "LT_C_UM710",
        "수질측정망지점(하천/호소 등)": "LT_P_WEISSITEMA",
        "대권역": "LT_C_WKMBBSN",
        "중권역": "LT_C_WKMMBSN",
        "표준권역": "LT_C_WKMSBSN",
        "하천망": "LT_C_WKMSTRM",
        "하수종말처리시설": "LT_P_WEISPLAFACW",
        "지하수유동방향": "LT_L_GIMSDIREC",
        "저수지": "LT_C_RIRSV",
        "절대보전연안": "LT_C_WGISPLABS",
        "준보전연안": "LT_C_WGISPLJUN",
    },
    "농림/산지": {
        "농업진흥지역도": "LT_C_AGRIXUE101",
        "영농여건불리농지도": "LT_C_AGRIXUE102",
        "산지(보안림)": "LT_C_FLISFK300",
        "산지(자연휴양림)": "LT_C_FLISFK100",
        "산지(채종림)": "LT_C_FLISFK200",
        "임업 및 산촌 진흥권역": "LT_C_UF602",
        "산림입지도": "LT_C_FSDIFRSTS",
    },
    "주거 및 단지/산업": {
        "국민임대주택": "LT_C_UD610",
        "보금자리주택": "LT_C_UD620",
        "주거환경개선지구도": "LT_C_UD601",
        "시장정비구역": "LT_C_UB901",
        "단지경계": "LT_C_DAMDAN",
        "단지시설용지": "LT_C_DAMYOJ",
        "단지용도지역": "LT_C_DAMYOD",
        "벤처기업육성지역": "LT_C_UH701",
        "유통단지": "LT_C_UH501",
        "자유무역지역지정및운영": "LT_C_UH402",
        "국가산업단지": "LT_C_WGISIEGUG",
        "농공단지": "LT_C_WGISIENONG",
        "일반산업단지": "LT_C_WGISIEILBAN",
        "첨단산업단지": "LT_C_WGISIEDOSI",
    },
    "주요 상권/관광/문화재": {
        "주요상권": "LT_C_DGMAINBIZ",
        "관광지": "LT_C_UO601",
        "온천지구": "LT_C_UJ401",
        "문화재보호도": "LT_C_UO301",
        "전통사찰보존": "LT_C_UO501",
        "자전거길": "LT_L_BYCLINK",
        "산책로": "LT_L_TRKROAD,LT_P_TRKROAD",
        "등산로": "LT_L_FRSTCLIMB,LT_P_CLIMBALL",
    },
    "항공/교통": {
        "비행금지구역": "LT_C_AISPRHC",
        "비행제한구역": "LT_C_AISRESC",
        "위험구역": "LT_C_AISDNGC",
        "제한고도": "LT_L_AISROUTEU",
        "항공로": "LT_L_AISPATH",
        "관제권": "LT_C_AISCTRC",
        "비행장교통구역": "LT_C_AISATZC",
        "교통노드": "LT_P_MOCTNODE",
        "교통링크": "LT_L_MOCTLINK",
    }
}

# ===== 소유자별 주제도 그룹화 (UI 표시용) =====
MAP_SOURCES = {
    "브이월드 (VWorld)": VWORLD_WMS_CATEGORIES,
    "국립생태원 (NIE)": {
        "환경 주제도": {
            "생태자연도": "tbl_opn_eczm",
        }
    },
    "국토정보플랫폼": {
        "연속수치지형도(1/5000)": {
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # NGII 1/5000 연속수치지형도 — V-World 중계 레이어로 표시
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # 한계 안내:
            #   V-World WMS API 2.0 (169개 레이어)에 NGII 1/5000 수치지도의 분류별
            #   레이어는 도로중심선(LT_L_N3A0020000) 1개만 등록되어 있음.
            #   도시계획도로/면도/농로/국도/지방도/철도 등 세분화 분류는 NGII의 SHP
            #   원본 attribute(road_bt 등)에만 존재하며 WMS로는 분리 토글 불가.
            #
            # 현재 매핑 전략:
            #   - 모든 토글이 V-World의 LT_C_LANDINFOBASEMAP(LX맵=NGII 1/5000 통합)을
            #     기본 표시하되, 교통은 교통링크(LT_L_MOCTLINK = 도로+철도 분석망)를
            #     추가 활성화하여 도로/철도 가시성 강화.
            #
            # 향후 정확한 분류별 표시:
            #   1순위. NGII에서 1/5000 수치지도 SHP 다운로드 → data/ngii_shp/ 폴더
            #          저장 → 앱이 자동 인식하여 attribute 기반 분류별 색상 표시
            #          (별도 작업 2~3시간 필요)
            #   2순위. NGII OpenAPI(map.ngii.go.kr) 회원가입 + 정식 WMTS URL 발급 →
            #          config의 VWORLD_TILE_URLS에 NGII 타일 추가
            #
            # 코드 패턴 참고: LT_접두어 + 기하타입(L/C/P) + _N3A_ + 8자리코드
            #   N3A=면, N3L=선, N3P=점
            #   두 번째 글자: A=경계, B=교통, C=시설물, D=토양, E=수계, F=지형, G=식생, H=주기
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            "교통": "LT_L_MOCTLINK",              # 교통링크 (도로 + 철도 분석망) — 가장 포괄적
            "건물": "LT_C_LANDINFOBASEMAP",       # LX맵 통합 (건물 포함)
            "시설": "LT_C_LANDINFOBASEMAP",       # LX맵 통합
            "식생": "LT_C_FSDIFRSTS",             # 산림입지도 (식생 대용)
            "수계": "LT_C_LANDINFOBASEMAP",       # LX맵 통합 (수계 포함)
            "지형": "LT_C_LANDINFOBASEMAP",       # LX맵 통합 (등고선 포함)
            "경계": "LT_C_ADRI",                  # 행정경계(리)
            "주기": "LT_P_NSNMSSITENM",           # 국가지명 (주기/명칭)
            "표고점": "LT_C_LANDINFOBASEMAP",     # LX맵 통합 (표고점 포함)
        },
        "기본지도": {
            "LX맵(기본지도)": "LT_C_LANDINFOBASEMAP",
            "도로중심선": "LT_L_N3A0020000",
            "토지소유공간정보": "DT_D160",
            "연속지적도형정보": "DT_D002",
        },
        "도로시설물": {
            "차도구간": "LT_C_A3DRIVEWAYSECTION",
            "보도구간": "LT_C_A4SUBSIDIARYSECTION",
            "주차면": "LT_C_A5PARKINGLOT",
            "노면표시": "LT_C_B3SURFACEMARK",
            "노면선표시": "LT_L_B2SURFACELINEMARK",
            "안전표지(면)": "LT_C_B1SAFETYSIGN",
            "안전표지(점)": "LT_P_B1SAFETYSIGN",
            "신호등": "LT_P_C1TRAFFICLIGHT",
            "차량방호안전시설": "LT_L_C3VEHICLEPROTECTIONSAFETY",
            "과속방지턱": "LT_C_C4SPEEDBUMP",
            "높이장애물": "LT_L_C5HEIGHTBARRIER",
            "킬로포스트": "LT_P_C2KILOPOST",
            "지주": "LT_P_C6POSTPOINT",
        },
        "지형/지질/토양": {
            "토양도": "LT_C_GIMSSCS",
            "지질구조밀도": "LT_C_GIMSLINEA",
            "지질구조선": "LT_L_GIMSLINEA",
            "수문지질단위": "LT_C_GIMSHYDRO",
            "단층": "LT_L_GIMSFAULT",
            "배수등급": "LT_C_ASITSOILDRA",
            "유효토심": "LT_C_ASITSOILDEP",
            "심토토성": "LT_C_ASITDEEPSOIL",
            "자갈함량": "LT_C_ASITSURSTON",
            "해안선": "LT_L_TOISDEPCNTAH",
        },
    },
    "국토환경성평가 (ECVAM)": {
        "환경평가 종합": {
            "국토환경성평가(종합)": "nem_ecvam",
        },
        "환경생태적 평가": {
            "환경생태적 평가(종합)": "nem_eco",
            "01_임상도": "nem_eco_01",
            "02_녹지자연도": "nem_eco_02",
            "03_풍수해도": "nem_eco_03",
            "04_경사도": "nem_eco_04",
            "05_표고": "nem_eco_05",
            "07_토양": "nem_eco_07",
            "08_수계": "nem_eco_08",
        },
        "법제적 평가": {
            "법제적 평가(종합)": "nem_law",
            "01_공원": "nem_law_01",
            "02_도립공원": "nem_law_02",
            "03_녹지": "nem_law_03",
            "04_보호구": "nem_law_04",
            "05_도립보호구": "nem_law_05",
            "06_주변": "nem_law_06",
            "07_경": "nem_law_07",
            "08_멸종(특정)보호구": "nem_law_08",
            "09_특정": "nem_law_09",
            "10_자연": "nem_law_10",
            "11_자연환경": "nem_law_11",
            "12_수": "nem_law_12",
            "13_문화재": "nem_law_13",
            "14_보호림": "nem_law_14",
            "15_백두대간보호지": "nem_law_15",
            "16_산": "nem_law_16",
            "17_도립": "nem_law_17",
            "18_홍수": "nem_law_18",
            "19_도립": "nem_law_19",
            "20_보호구": "nem_law_20",
        },
    },
    "추후 추가 예정": {
        "산림 (준비중)": {
            "임상도": "FOREST_MAP_READY",
        }
    }
}

# 하위 호환성을 위해 기존 변수 생성 (모든 레이어 플래튼)
VWORLD_WMS_LAYERS = {}
for category, layers in VWORLD_WMS_CATEGORIES.items():
    VWORLD_WMS_LAYERS.update(layers)

# 국립생태원 레이어도 포함
VWORLD_WMS_LAYERS.update({"생태자연도": "LT_C_AS001"})

# ===== VWorld Data API 레이어 코드 =====
CADASTRAL_LAYER = "LP_PA_CBND_BUBUN"

# 용도지역 레이어 (4대 용도지역)
ZONING_LAYERS = {
    "LT_C_UQ111": "도시지역",
    "LT_C_UQ112": "관리지역",
    "LT_C_UQ113": "농림지역",
    "LT_C_UQ114": "자연환경보전지역",
}

# ===== VWorld WFS 다운로드 가능 레이어 정의 =====
VWORLD_WFS_LAYERS = {
    "지적도": {
        "typename": "lp_pa_cbnd_bubun",
        "fields": {"pnu": "PNU", "jibun": "지번", "jimok": "지목", "bonbeon": "본번", "bubeon": "부번"},
        "geometry_type": "Polygon",
        "label_field": "jibun",
        "dxf_layers": {"boundary": "CADASTRAL_LINE", "text": "JIBEON_TEXT"},
    },
    "도시지역": {
        "typename": "lt_c_uq111",
        "fields": {"gid": "GID", "uname": "용도명"},
        "geometry_type": "Polygon",
        "label_field": "uname",
        "dxf_layers": {"boundary": "URBAN_AREA_LINE", "text": "URBAN_AREA_TEXT"},
    },
    "관리지역": {
        "typename": "lt_c_uq112",
        "fields": {"gid": "GID", "uname": "용도명"},
        "geometry_type": "Polygon",
        "label_field": "uname",
        "dxf_layers": {"boundary": "MANAGE_AREA_LINE", "text": "MANAGE_AREA_TEXT"},
    },
    "농림지역": {
        "typename": "lt_c_uq113",
        "fields": {"gid": "GID", "uname": "용도명"},
        "geometry_type": "Polygon",
        "label_field": "uname",
        "dxf_layers": {"boundary": "AGRI_AREA_LINE", "text": "AGRI_AREA_TEXT"},
    },
    "자연환경보전지역": {
        "typename": "lt_c_uq114",
        "fields": {"gid": "GID", "uname": "용도명"},
        "geometry_type": "Polygon",
        "label_field": "uname",
        "dxf_layers": {"boundary": "NATURE_AREA_LINE", "text": "NATURE_AREA_TEXT"},
    },
    "사업지구경계도": {
        "typename": "lt_c_lhzone",
        "fields": {"gid": "GID", "name": "명칭"},
        "geometry_type": "Polygon",
        "label_field": "name",
        "dxf_layers": {"boundary": "PROJECT_ZONE_LINE", "text": "PROJECT_ZONE_TEXT"},
    },
    "개발제한구역": {
        "typename": "lt_c_ud801",
        "fields": {"gid": "GID", "name": "명칭"},
        "geometry_type": "Polygon",
        "label_field": "name",
        "dxf_layers": {"boundary": "GREEN_BELT_LINE", "text": "GREEN_BELT_TEXT"},
    },
    "생태자연도": {
        "source": "NIE",
        "typename": "tbl_opn_eczm",
        "fields": {"eczm_grad": "등급", "plnt_cln_ttle": "식생명"},
        "geometry_type": "Polygon",
        "label_field": "eczm_grad",
        "dxf_layers": {"boundary": "ECOLOGY_LINE", "text": "ECOLOGY_TEXT", "hatch": "ECOLOGY_HATCH"},
    },
    "국토환경성평가(종합)": {
        "source": "ECVAM",
        "typename": "nem_ecvam",
        "fields": {"gid": "GID"},
        "geometry_type": "Polygon",
        "label_field": "",
        "dxf_layers": {"boundary": "ECVAM_LINE", "text": "ECVAM_TEXT", "hatch": "ECVAM_HATCH"},
    },
    "환경생태적 평가(종합)": {
        "source": "ECVAM",
        "typename": "nem_eco",
        "fields": {"gid": "GID"},
        "geometry_type": "Polygon",
        "label_field": "",
        "dxf_layers": {"boundary": "ECVAM_ECO_LINE", "text": "ECVAM_ECO_TEXT", "hatch": "ECVAM_ECO_HATCH"},
    },
    "법제적 평가(종합)": {
        "source": "ECVAM",
        "typename": "nem_law",
        "fields": {"gid": "GID"},
        "geometry_type": "Polygon",
        "label_field": "",
        "dxf_layers": {"boundary": "ECVAM_LAW_LINE", "text": "ECVAM_LAW_TEXT", "hatch": "ECVAM_LAW_HATCH"},
    },
}

# --- 동적 WFS 레이어 매핑 (MAP_SOURCES의 모든 레이어) ---
for source_name, categories in MAP_SOURCES.items():
    for cat_name, layers in categories.items():
        for layer_name, code in layers.items():
            if layer_name not in VWORLD_WFS_LAYERS and "READY" not in str(code):
                primary_code = code.split(',')[0].strip()
                # 소스별 WFS 설정
                if source_name == "국토환경성평가 (ECVAM)":
                    wfs_source = "ECVAM"
                    typename = primary_code  # ECVAM은 원본 대소문자 유지
                elif source_name == "국립생태원 (NIE)":
                    wfs_source = "NIE"
                    typename = primary_code
                else:
                    wfs_source = "VWORLD"
                    typename = primary_code.lower()
                
                VWORLD_WFS_LAYERS[layer_name] = {
                    "source": wfs_source,
                    "typename": typename,
                    "fields": {"gid": "GID"},
                    "geometry_type": "Unknown",
                    "label_field": "",
                    "dxf_layers": {"boundary": f"{primary_code.upper()}_LINE", "text": f"{primary_code.upper()}_TEXT", "hatch": f"{primary_code.upper()}_HATCH"},
                }
