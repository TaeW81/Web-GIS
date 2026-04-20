"""
프로젝트 전역 설정 파일
- API 키, 좌표계, 레이어 코드 등을 한 곳에서 관리합니다.
- .env 파일에서 환경변수를 로드합니다.
"""
import os
from dotenv import load_dotenv

# .env 파일에서 환경변수 로드
load_dotenv()

# ===== API 키 =====
VWORLD_KEY = os.getenv("VWORLD_KEY", "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1")

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

# ===== VWorld API 기본 설정 =====
VWORLD_DOMAIN = "http://localhost"
VWORLD_DATA_URL = "https://api.vworld.kr/req/data"
VWORLD_SEARCH_URL = "https://api.vworld.kr/req/search"
VWORLD_WMS_URL = "https://api.vworld.kr/req/wms"

# ===== VWorld WMTS 배경지도 타일 URL =====
VWORLD_TILE_URLS = {
    "일반지도": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Base/{{z}}/{{y}}/{{x}}.png",
    "위성영상": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Satellite/{{z}}/{{y}}/{{x}}.jpeg",
    "하이브리드": f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Hybrid/{{z}}/{{y}}/{{x}}.png",
}

# ===== VWorld WMS 오버레이 레이어 카테고리 및 범례 URL 설정 =====
VWORLD_WMS_URL = "http://api.vworld.kr/req/wms"
VWORLD_LEGEND_URL = "http://api.vworld.kr/req/image?key={key}&service=image&request=GetLegendGraphic&format=png&type=ALL&layer={layer}&style={layer}&LEGEND_OPTIONS=forceTitle:off"

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

# 하위 호환성을 위해 기존 변수 생성 (모든 레이어 플래튼)
VWORLD_WMS_LAYERS = {}
for category, layers in VWORLD_WMS_CATEGORIES.items():
    VWORLD_WMS_LAYERS.update(layers)

# ===== VWorld Data API 레이어 코드 =====
# PNU 추출용
CADASTRAL_LAYER = "LP_PA_CBND_BUBUN"

# 용도지역 레이어 (4대 용도지역)
ZONING_LAYERS = {
    "LT_C_UQ111": "도시지역",
    "LT_C_UQ112": "관리지역",
    "LT_C_UQ113": "농림지역",
    "LT_C_UQ114": "자연환경보전지역",
}

# ===== VWorld WFS 다운로드 가능 레이어 정의 =====
# key: WMS UI 레이어 이름
# value: { typename(WFS 레이어코드), fields(속성 필드 매핑), geometry_type, label_field(DXF 텍스트용) }
VWORLD_WFS_LAYERS = {
    "지적도": {
        "typename": "lp_pa_cbnd_bubun",
        "fields": {
            "pnu": "PNU",
            "jibun": "지번",
            "jimok": "지목",
            "bonbeon": "본번",
            "bubeon": "부번",
        },
        "geometry_type": "Polygon",
        "label_field": "jibun",
        "dxf_layers": {
            "boundary": "CADASTRAL_LINE",
            "text": "JIBEON_TEXT",
        },
    },
    "도시지역": {
        "typename": "lt_c_uq111",
        "fields": {"gid": "GID", "uname": "용도명"},
        "geometry_type": "Polygon",
        "label_field": "uname",
        "dxf_layers": {
            "boundary": "URBAN_AREA_LINE",
            "text": "URBAN_AREA_TEXT",
        },
    },
    "관리지역": {
        "typename": "lt_c_uq112",
        "fields": {"gid": "GID", "uname": "용도명"},
        "geometry_type": "Polygon",
        "label_field": "uname",
        "dxf_layers": {
            "boundary": "MANAGE_AREA_LINE",
            "text": "MANAGE_AREA_TEXT",
        },
    },
    "농림지역": {
        "typename": "lt_c_uq113",
        "fields": {"gid": "GID", "uname": "용도명"},
        "geometry_type": "Polygon",
        "label_field": "uname",
        "dxf_layers": {
            "boundary": "AGRI_AREA_LINE",
            "text": "AGRI_AREA_TEXT",
        },
    },
    "자연환경보전지역": {
        "typename": "lt_c_uq114",
        "fields": {"gid": "GID", "uname": "용도명"},
        "geometry_type": "Polygon",
        "label_field": "uname",
        "dxf_layers": {
            "boundary": "NATURE_AREA_LINE",
            "text": "NATURE_AREA_TEXT",
        },
    },
    "사업지구경계도": {
        "typename": "lt_c_lhzone",
        "fields": {"gid": "GID", "name": "명칭"},
        "geometry_type": "Polygon",
        "label_field": "name",
        "dxf_layers": {
            "boundary": "PROJECT_ZONE_LINE",
            "text": "PROJECT_ZONE_TEXT",
        },
    },
    "개발제한구역": {
        "typename": "lt_c_ud801",
        "fields": {"gid": "GID", "name": "명칭"},
        "geometry_type": "Polygon",
        "label_field": "name",
        "dxf_layers": {
            "boundary": "GREEN_BELT_LINE",
            "text": "GREEN_BELT_TEXT",
        },
    },
}

# --- 동적 WFS 레이어 매핑 ---
# VWORLD_WFS_LAYERS에 하드코딩되지 않은 WMS 항목들도 일괄 추출 대상이 되도록 자동 추가합니다.
for cat_name, layers in VWORLD_WMS_CATEGORIES.items():
    for layer_name, code in layers.items():
        if layer_name not in VWORLD_WFS_LAYERS:
            # 쉼표로 여러 코드가 연결된 경우 첫 번째 코드 사용
            primary_code = code.split(',')[0].strip()
            VWORLD_WFS_LAYERS[layer_name] = {
                "typename": primary_code.lower(),
                "fields": {"gid": "GID"}, # 기본 범용 필드
                "geometry_type": "Unknown",
                "label_field": "",
                "dxf_layers": {
                    "boundary": f"{primary_code.upper()}_LINE",
                    "text": f"{primary_code.upper()}_TEXT",
                },
            }
