"""
🗺️ Web-GIS 기반 현황분석 자동화 플랫폼 (안정성 강화 버전)
메인 Streamlit 애플리케이션
"""
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium
import folium
import tempfile
import os

import hashlib
import pickle
import traceback

from config import VWORLD_KEY, VWORLD_TILE_URLS, VWORLD_WMS_CATEGORIES, MAP_SOURCES, KOREA_CRS, KOREA_CRS_ORIGINS, VWORLD_WFS_LAYERS
from modules.dxf_parser import parse_dxf
from modules.pnu_extractor import extract_pnu_list
from modules.map_builder import create_map
from modules.excel_exporter import create_multi_sheet_excel
from modules.spatial_downloader import fetch_wfs_data, export_to_dxf, export_to_shp
from modules.vworld_search import search_place
from analyzers import get_all_analyzers
from report.word_report import LandReportGenerator
from report.free_transfer_generator import FreeTransferGenerator

# ============================
st.set_page_config(page_title="KH LandHub | 통합 토지 분석 플랫폼", layout="wide", page_icon="🌏")
st.title("🌏 KH LandHub : 통합 토지 분석 플랫폼")
st.caption("건화(KH)의 공간정보 정밀 스캔 기술이 집약된 GIS 기반 토지·건축물 현황분석 자동화 솔루션")

# --- 프로젝트 단위 캐시 디렉토리 ---
PROJECT_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "project_cache")
os.makedirs(PROJECT_CACHE_DIR, exist_ok=True)

def _file_hash(uploaded_file):
    """업로드된 DXF 파일의 이름+크기로 고유 해시 생성"""
    key = f"{uploaded_file.name}_{uploaded_file.size}"
    return hashlib.md5(key.encode()).hexdigest()

def _load_project_cache(file_hash):
    """프로젝트 캐시 파일에서 분석 결과를 로드"""
    cache_path = os.path.join(PROJECT_CACHE_DIR, f"{file_hash}.pkl")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as f:
                return pickle.load(f)
        except:
            pass
    return None

def _save_project_cache(file_hash, all_sheets):
    """분석 결과를 프로젝트 캐시 파일로 저장"""
    cache_path = os.path.join(PROJECT_CACHE_DIR, f"{file_hash}.pkl")
    try:
        with open(cache_path, "wb") as f:
            pickle.dump(all_sheets, f)
    except:
        pass

# ============================
# KH LandHub 디자인 시스템 (CSS)
# ============================
# 컬러 토큰
#   --kh-primary: KH 메인 파랑 (#1565c0)
#   --kh-primary-light: 호버/배경 (#e3f2fd)
#   --kh-accent: 강조 (#ff6f00)
#   --kh-success: 성공 (#2e7d32)
#   --kh-text: 본문 (#2d3748)
#   --kh-text-muted: 보조 (#718096)
st.markdown("""
    <style>
    :root {
        --kh-primary: #1565c0;
        --kh-primary-light: #e3f2fd;
        --kh-accent: #ff6f00;
        --kh-success: #2e7d32;
        --kh-warning: #f57c00;
        --kh-text: #2d3748;
        --kh-text-muted: #718096;
        --kh-border: #e2e8f0;
    }

    /* ─── 섹션 헤더 스타일 (사이드바 1./2./...) ─── */
    .kh-section {
        font-size: 14px;
        font-weight: 700;
        color: var(--kh-primary);
        margin: 14px 0 6px 0;
        padding: 4px 0 4px 8px;
        border-left: 3px solid var(--kh-primary);
        background: var(--kh-primary-light);
        border-radius: 0 4px 4px 0;
    }
    .kh-subsection {
        font-size: 12px;
        font-weight: 600;
        color: var(--kh-text-muted);
        margin: 8px 0 2px 4px;
    }

    /* ─── 사이드바 체크박스 컴팩트 ─── */
    div[data-testid="stSidebar"] div[data-testid="stCheckbox"] {
        margin-bottom: 0 !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stCheckbox"] label {
        font-size: 12.5px !important;
        line-height: 1.3 !important;
    }

    /* ─── Expander 컴팩트 (더 빡빡하게) ─── */
    div[data-testid="stExpander"] {
        border: 1px solid var(--kh-border) !important;
        border-radius: 5px !important;
        margin-bottom: 2px !important;          /* 6→2 */
    }
    div[data-testid="stExpander"] div[data-testid="stVerticalBlock"] {
        gap: 0.05rem !important;                /* 0.25→0.05 */
    }
    div[data-testid="stExpanderDetails"] {
        padding: 0.3rem 0.6rem !important;      /* 0.5/0.7 → 0.3/0.6 */
    }
    div[data-testid="stExpanderSummary"] {
        padding: 0.1rem 0.5rem !important;
        min-height: 1.7rem !important;          /* 2 → 1.7 */
        font-size: 13px !important;
    }
    /* Expander 안의 컬럼 사이 간격 축소 */
    div[data-testid="stExpander"] div[data-testid="stHorizontalBlock"] {
        gap: 0.4rem !important;
    }

    /* ─── 사이드바 탭 ─── */
    div[data-testid="stSidebar"] button[data-baseweb="tab"] {
        padding: 4px 10px !important;
        font-size: 12px !important;
    }

    /* ─── 라디오 가로 컴팩트 ─── */
    div[data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 0.4rem !important;
    }
    div[data-testid="stSidebar"] div[role="radiogroup"] label {
        font-size: 12.5px !important;
    }

    /* ─── 버튼 컴팩트 + 일관성 ─── */
    div[data-testid="stSidebar"] div[data-testid="stButton"] button {
        font-size: 12.5px !important;
        padding: 0.25rem 0.6rem !important;
        min-height: 32px !important;
        border-radius: 5px !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stButton"] {
        margin-bottom: 3px !important;
    }

    /* ─── 메인 영역 ─── */
    /* "분석 패널" 같은 큰 헤더 축소 */
    .kh-panel-title {
        font-size: 14px;
        font-weight: 600;
        color: var(--kh-text-muted);
        margin: 0 0 6px 0;
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* ─── 텍스트 입력 ─── */
    div[data-testid="stTextInput"] input {
        font-size: 13px !important;
    }

    /* ─── 다운로드 버튼 — 전부 그린톤으로 통일 ─── */
    /*   type="primary"든 일반이든 일관된 KH 다운로드 컬러로  */
    div[data-testid="stDownloadButton"] button {
        background-color: var(--kh-success) !important;  /* #2e7d32 */
        color: white !important;
        border: 1px solid #1b5e20 !important;
        font-weight: 600 !important;
        transition: background-color 0.15s ease;
    }
    div[data-testid="stDownloadButton"] button:hover {
        background-color: #1b5e20 !important;
        border-color: #0d3812 !important;
    }
    div[data-testid="stDownloadButton"] button:focus {
        background-color: #1b5e20 !important;
        box-shadow: 0 0 0 3px rgba(46, 125, 50, 0.25) !important;
    }
    div[data-testid="stDownloadButton"] button:active {
        background-color: #0d3812 !important;
    }
    /* 다운로드 버튼 안의 텍스트/아이콘도 흰색 강제 */
    div[data-testid="stDownloadButton"] button p,
    div[data-testid="stDownloadButton"] button span,
    div[data-testid="stDownloadButton"] button svg {
        color: white !important;
        fill: white !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ============================
# 데이터 변수 및 상태 초기화
# ============================
DEFAULT_CENTER = [37.39293, 126.97286]  # 성지스타위드
for k, v in [('map_center', DEFAULT_CENTER), ('map_zoom', 16), ('last_uploaded_file', None), 
             ('last_crs_origin', "중부"), ('last_crs_cat', "GRS80(현행)"), ('last_epsg', ""),
             ('map_force_center_id', 1), ('last_base_map', "일반지도"),
             ('map_layers', ["지적도", "연속지적도"])]: # 기본 렌더링 레이어
    if k not in st.session_state:
        st.session_state[k] = v

dxf_result = {"center": st.session_state.map_center, "gps_points": [], "num_vertices": 0, "polygon": None}

# ============================
# 사이드바 (모든 조작 기능 통합)
# ============================
with st.sidebar:
    # 📡 건화(KH) 공식 브랜딩 섹션
    logo_col, text_col = st.columns([1, 3.5], gap="small")
    with logo_col:
        st.image("assets/kunhwa_logo.png", use_container_width=True)
    with text_col:
        st.markdown(
            "<div style='margin-top: 5px; line-height: 1.3;'>"
            "<strong style='font-size: 1.1rem; color: #1e293b;'>🌏 KH LandHub</strong><br>"
            "<span style='font-size: 0.8rem; color: gray;'>통합 토지 분석 플랫폼</span>"
            "</div>", 
            unsafe_allow_html=True
        )
    # ----------------------------------------
    # * 지도 이동 (장소 검색)
    # ----------------------------------------
    # 지도 이동은 공간 절약을 위해 상단에 바로 배치
    col1, col2 = st.columns([3, 1])
    search_query = col1.text_input("검색어 입력", label_visibility="collapsed", placeholder="장소검색 (예: 평촌역)")
    if col2.button("이동", use_container_width=True):
        if search_query:
            with st.spinner("검색 중..."):
                place_result = search_place(search_query, VWORLD_KEY)
                if place_result:
                    st.session_state.map_center = [place_result['lat'], place_result['lon']]
                    st.session_state.map_zoom = 15
                    st.session_state.map_force_center_id += 1
                    st.session_state.search_marker = place_result
                    st.success(f"✅ '{place_result['name']}'(으)로 이동했습니다.")
                else:
                    st.error("❌ 검색 결과를 찾을 수 없습니다.")

    # ----------------------------------------
    # 1. 구역계 범위 지정 (DXF 업로드 또는 지도에서 직접 그리기)
    # ----------------------------------------
    st.markdown("<p class='kh-section'>1. 구역계 범위 지정</p>", unsafe_allow_html=True)

    boundary_mode = st.radio(
        "구역계 지정 방식",
        options=["📁 DXF 파일 업로드", "🖌️ 지도에서 직접 그리기"],
        horizontal=True,
        label_visibility="collapsed",
        key="boundary_mode",
    )

    uploaded_file = None
    is_new_file = False

    if boundary_mode == "📁 DXF 파일 업로드":
        uploaded_file = st.file_uploader("구역계 파일(.dxf)", type=["dxf"], label_visibility="collapsed")
        if uploaded_file and st.session_state.get('last_uploaded_file') != uploaded_file.name:
            is_new_file = True
            st.session_state.last_uploaded_file = uploaded_file.name
    else:
        # 지도에서 직접 그리기 모드 (적용/지움 버튼은 지도 패널 상단에 표시 — 더 직관적)
        st.markdown(
            "<p style='font-size:12px; color:#555; margin: 4px 0 4px 0; line-height:1.5;'>"
            "지도 좌상단의 <b>⬢/▭ 도구</b>로 영역을 그리고<br>"
            "<b>지도 위쪽의 적용/지움 버튼</b>을 누르세요.<br>"
            "<span style='color:#888;'>다각형: 꼭짓점 클릭 → 마지막 점 더블클릭으로 닫기</span><br>"
            "<span style='color:#888;'>사각형: 드래그</span>"
            "</p>",
            unsafe_allow_html=True,
        )

    # ★ 구역계 범위 존재 여부 — DXF 업로드 또는 지도에서 그린 영역 둘 중 하나라도 있으면 OK
    _has_boundary = (uploaded_file is not None) or (st.session_state.get("drawn_dxf_result") is not None)

    # 좌표계 설정 — expander로 접어서 공간 절약 (DXF 업로드 시 기본 펼침)
    with st.expander("📐 도면 좌표계", expanded=bool(uploaded_file)):
        crs_cat = st.radio("분류", options=list(KOREA_CRS.keys()), horizontal=True, label_visibility="collapsed")
        crs_origin = st.radio("원점", options=list(KOREA_CRS[crs_cat].keys()), horizontal=True)
        selected_epsg = st.text_input("EPSG 코드 (직접 입력 가능)", value=KOREA_CRS[crs_cat][crs_origin])

    crs_changed = False
    if st.session_state.get('last_epsg') != selected_epsg:
        crs_changed = True
        st.session_state.last_epsg = selected_epsg
    if st.session_state.last_crs_origin != crs_origin or st.session_state.last_crs_cat != crs_cat:
        crs_changed = True
        st.session_state.last_crs_origin = crs_origin
        st.session_state.last_crs_cat = crs_cat
        if not uploaded_file and crs_origin in KOREA_CRS_ORIGINS:
            lon, lat = KOREA_CRS_ORIGINS[crs_origin]
            st.session_state.map_center = [lat, lon]
            st.session_state.map_zoom = 10
            st.session_state.map_force_center_id += 1
            dxf_result["center"] = [lat, lon]

    # 좌표계 목록 및 동기화 인덱스 계산
    dl_crs_options = {
        "GRS80 중부 (EPSG:5186)": "EPSG:5186", "GRS80 서부 (EPSG:5185)": "EPSG:5185",
        "GRS80 동부 (EPSG:5187)": "EPSG:5187", "GRS80 동해 (EPSG:5188)": "EPSG:5188",
        "UTMK (EPSG:5179)": "EPSG:5179", 
        "Bessel 서부 (EPSG:5173)": "EPSG:5173", "Bessel 중부 (EPSG:5174)": "EPSG:5174",
        "Bessel 동부 (EPSG:5176)": "EPSG:5176", "Bessel 동해 (EPSG:5177)": "EPSG:5177",
        "Bessel 제주 (EPSG:5175)": "EPSG:5175", "WGS84 (EPSG:4326)": "EPSG:4326",
    }
    dl_crs_values = list(dl_crs_options.values())
    try:
        sync_index = dl_crs_values.index(selected_epsg)
    except ValueError:
        sync_index = 0

    st.markdown("<p class='kh-section'>2. 지도 레이어 및 데이터 추출</p>", unsafe_allow_html=True)
    
    
    layer_title_col, layer_btn_col = st.columns([3, 1])
    with layer_title_col:
        st.markdown("<p style='font-size:13px; font-weight:bold; margin: 0; padding-top: 5px;'>지도 레이어 설정 <span style='font-weight:normal; font-size:11px;'>(체크시 지도 직접 반영)</span></p>", unsafe_allow_html=True)
    with layer_btn_col:
        if st.button("초기화", use_container_width=True):
            for source_dict in MAP_SOURCES.values():
                for layers in source_dict.values():
                    for layer_name in layers.keys():
                        st.session_state[f"chk_{layer_name}"] = False
                        
    selected_dl_layers = []
    
    # 소속 기관별 탭 구성 (가로 공간 활용)
    source_tabs = st.tabs(list(MAP_SOURCES.keys()))
    
    for i, (source_name, categories) in enumerate(MAP_SOURCES.items()):
        with source_tabs[i]:
            for cat_name, layers in categories.items():
                # 연속수치지형도는 기본 펼침 + 카테고리 전용 "전체 선택 해제" 버튼
                is_ngii_topo = (cat_name == "연속수치지형도(1/5000)")
                expanded = (cat_name == "기본 및 지적") or is_ngii_topo

                with st.expander(f"📁 {cat_name}", expanded=expanded):
                    # 연속수치지형도 전용 — 카테고리 내 9개만 일괄 해제 + 한계 안내
                    if is_ngii_topo:
                        st.markdown(
                            "<p style='font-size:11px; color:#888; margin: 0 0 6px 4px; line-height:1.4;'>"
                            "※ V-World 중계 한계로 분류별 세분화(도시계획도로/면도/농로/국도/철도)는 "
                            "통합 LX맵으로 표시됩니다. 정확한 분류 표시는 NGII SHP 로컬 통합 필요."
                            "</p>",
                            unsafe_allow_html=True,
                        )
                        if st.button("전체 선택 해제", key=f"clear_cat_{cat_name}", use_container_width=True):
                            for ln in layers.keys():
                                st.session_state[f"chk_{ln}"] = False
                            st.rerun()

                    # 2단 컬럼으로 배치하여 세로 길이 단축
                    cols = st.columns(2)
                    for idx, (layer_name, code) in enumerate(layers.items()):
                        target_col = cols[idx % 2]
                        check_key = f"chk_{layer_name}"
                        is_default = (layer_name == "연속지적도" or layer_name == "지적도")

                        if check_key not in st.session_state:
                            st.session_state[check_key] = is_default

                        # 추후 추가 예정 항목은 비활성화 표시
                        if "READY" in str(code):
                            target_col.checkbox(f"🚫 {layer_name}", value=False, disabled=True, help="준비 중인 레이어입니다.")
                        else:
                            if target_col.checkbox(layer_name, key=check_key):
                                selected_dl_layers.append(layer_name)
    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
                    
    # 마지막 클릭한 레이어 추적 방어 로직
    old_layers = st.session_state.get('map_layers', [])
    newly_checked = [x for x in selected_dl_layers if x not in old_layers]
    if newly_checked:
        st.session_state.last_checked_layer = newly_checked[-1]
    elif st.session_state.get('last_checked_layer') not in selected_dl_layers:
        st.session_state.last_checked_layer = selected_dl_layers[-1] if selected_dl_layers else None
        
    st.session_state.map_layers = selected_dl_layers
    # 다운로드 좌표계 및 추출 버튼 배치
    btn_col1, btn_col2 = st.columns([1.2, 1])
    with btn_col1:
        dl_crs_label = st.selectbox("다운로드 좌표계", options=list(dl_crs_options.keys()), index=sync_index, label_visibility="collapsed")
        st.session_state.dl_target_epsg = dl_crs_options[dl_crs_label]
    
    with btn_col2:
        submit_layer_btn = st.button("🚀 일괄 추출하기", type="primary", use_container_width=True)

    if submit_layer_btn:
        if not _has_boundary:
            st.warning("⚠️ 구역계 범위가 없어 추출할 수 없습니다. DXF 업로드 또는 지도에서 그리기로 구역계를 지정해주세요.")
        else:
            st.session_state.do_wfs_download = True
            if "dl_result_bytes_list" in st.session_state:
                del st.session_state["dl_result_bytes_list"]

    # ----------------------------------------
    # 3. 국토정보플랫폼 벡터 추출 (추후: API 직접 연동)
    # ----------------------------------------
    # 분석기 등록 (UI 섹션 아님)
    
    all_analyzers = get_all_analyzers()
    selected_analyzers = all_analyzers

    # ----------------------------------------
    # 5. 대상지 현황 분석 보고서  (컴팩트 레이아웃: 2-컬럼 그리드 + 좁은 마진)
    # ----------------------------------------
    st.markdown(
        """
        <style>
        /* 5번 섹션 버튼 그룹의 세로 간격을 좁힘 */
        section[data-testid="stSidebar"] div[data-testid="stButton"] { margin-bottom: 2px; }
        section[data-testid="stSidebar"] div[data-testid="stButton"] button {
            min-height: 32px;
            padding: 0.15rem 0.4rem;
            font-size: 12.5px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<p class='kh-section'>3. 대상지 현황 분석 보고서</p>", unsafe_allow_html=True)

    _SUB = "<p style='font-weight:600; font-size:12px; color:#555; margin: 6px 0 1px 6px;'>{}</p>"

    # --- 5-1. 자동현황 분석결과 (Excel) — 2개 버튼을 한 줄에 ---
    st.markdown(_SUB.format("① 자동현황 분석 (Excel)"), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        btn_analysis = st.button("📊 분석 실행 (토지대장)", use_container_width=True, key="btn_analysis_main")
    with c2:
        btn_force_reanalyze = st.button("🔄 강제 재분석", use_container_width=True, key="btn_force_reanalyze")

    # --- 5-2. 공적장부 작성 — 4개 버튼 ---
    st.markdown(_SUB.format("② 공적장부 작성"), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        btn_mountain = st.button("🌲 편입산지조서", use_container_width=True, key="btn_mountain")
        btn_free_transfer = st.button("👥 소유자 구분도", use_container_width=True, key="btn_free_transfer")
    with c2:
        btn_farmland = st.button("🌾 편입농지조서", use_container_width=True, key="btn_farmland", disabled=True, help="준비중")
        btn_agreement = st.button("📋 무상귀속 협의요청서", use_container_width=True, key="btn_agreement")

    # --- 5-3. 보고서 ---
    st.markdown(_SUB.format("③ 현황 분석 보고서"), unsafe_allow_html=True)
    btn_report = st.button("📄 보고서 (Doc, Hwp)", use_container_width=True, key="btn_report")

    # --- 5-4. 기타 ---
    st.markdown(_SUB.format("④ 기타"), unsafe_allow_html=True)
    btn_qbs = st.button("🗺️ QBS 위치도 (PPT)", use_container_width=True, key="btn_qbs")

    # --- 버튼 핸들러 ---
    # ★ 5번 섹션의 모든 버튼은 그리기 모드에서도 동작하도록:
    #   PNU 추출이 아직 안 됐으면 자동 트리거 (DXF 모드는 line 573에서 자동, 그리기 모드는 여기서)
    def _ensure_pnu_extract():
        """PNU 미추출 상태면 자동 추출 트리거 (그리기 모드에서 '✅ 그린 영역 적용' 안 눌렀어도 동작)."""
        if not st.session_state.get("pnu_list"):
            st.session_state.do_pnu_extract = True

    if btn_analysis:
        if not _has_boundary:
            st.warning("구역계 범위를 먼저 지정해주세요 (DXF 업로드 또는 지도에서 그리기).")
        else:
            _ensure_pnu_extract()
            st.session_state.do_status_analysis = True
            st.session_state.force_reanalyze = False  # 캐시 우선

    if btn_force_reanalyze:
        if not _has_boundary:
            st.warning("구역계 범위를 먼저 지정해주세요 (DXF 업로드 또는 지도에서 그리기).")
        else:
            _ensure_pnu_extract()
            st.session_state.do_status_analysis = True
            st.session_state.force_reanalyze = True  # 캐시 무시, API 재호출

    if btn_mountain:
        if not _has_boundary:
            st.warning("구역계 범위를 먼저 지정해주세요 (DXF 업로드 또는 지도에서 그리기).")
        else:
            _ensure_pnu_extract()
            st.session_state.do_mountain_report = True

    if btn_report:
        if not _has_boundary:
            st.warning("구역계 범위를 먼저 지정해주세요 (DXF 업로드 또는 지도에서 그리기).")
        else:
            _ensure_pnu_extract()
            st.session_state.do_word_report = True

    if btn_qbs:
        if not _has_boundary:
            st.warning("구역계 범위를 먼저 지정해주세요 (DXF 업로드 또는 지도에서 그리기).")
        else:
            _ensure_pnu_extract()
            st.session_state.do_qbs = True

    if btn_free_transfer:
        if not _has_boundary:
            st.warning("구역계 범위를 먼저 지정해주세요 (DXF 업로드 또는 지도에서 그리기).")
        else:
            _ensure_pnu_extract()
            st.session_state.do_free_transfer = True

    if btn_agreement:
        if not _has_boundary:
            st.warning("구역계 범위를 먼저 지정해주세요 (DXF 업로드 또는 지도에서 그리기).")
        else:
            _ensure_pnu_extract()
            st.session_state.do_agreement = True

    # ----------------------------------------
    # 6. 기타 프로그램 (웹 변환기 - 가벼운 버전)
    # ----------------------------------------
    st.markdown("<p class='kh-section'>4. 기타 도구</p>", unsafe_allow_html=True)
    
    with st.expander("🛠️ SHP to DXF 웹 변환기", expanded=False):
        st.markdown("<p style='font-size:12px; color:gray;'>방법 1: 아래 박스에 <b>폴더를 통째로 드래그</b>하세요.<br>방법 2: [로컬 전용] 버튼을 눌러 내 컴퓨터 폴더를 선택하세요.</p>", unsafe_allow_html=True)
        
        # --- [로컬 전용] 폴더 선택 기능 ---
        col_local1, col_local2 = st.columns([1.8, 1])
        local_path_input = col_local1.text_input("내 컴퓨터 폴더 경로 직접 입력", value=st.session_state.get("local_selected_path", ""), placeholder="예: D:/GIS_Data", label_visibility="collapsed")
        btn_local_select = col_local2.button("📁 폴더 선택창", use_container_width=True)
        
        selected_path = None
        if btn_local_select:
            try:
                import tkinter as tk
                from tkinter import filedialog
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True) # 창을 최상단으로
                selected_path = filedialog.askdirectory()
                root.destroy()
                if selected_path:
                    st.session_state.local_selected_path = selected_path
            except Exception as tk_err:
                st.warning("💡 스레드 제한으로 선택창이 열리지 않을 수 있습니다. 왼쪽 칸에 경로를 직접 입력(복사+붙여넣기)해 주세요.")
                
        # 텍스트 입력값 변경 시 세션 상태 동기화
        if local_path_input and local_path_input != st.session_state.get("local_selected_path"):
            st.session_state.local_selected_path = local_path_input
            
        if st.session_state.get("local_selected_path"):
            path_to_check = st.session_state.local_selected_path.strip()
            if os.path.exists(path_to_check) and os.path.isdir(path_to_check):
                # 폴더 내 shp 파일 찾기
                shp_files = [f for f in os.listdir(path_to_check) if f.lower().endswith('.shp')]
                if shp_files:
                    st.session_state.found_shp_in_local = shp_files
                else:
                    st.session_state.found_shp_in_local = []
                    st.error("❌ 해당 폴더에 SHP 파일이 없습니다.")
            else:
                st.session_state.found_shp_in_local = []
                st.error("❌ 유효하지 않은 폴더 경로입니다.")
        
        # 로컬 폴더 선택 결과가 있을 경우 파일 선택 UI
        target_shp_name = None
        if st.session_state.get("local_selected_path") and st.session_state.get("found_shp_in_local"):
            target_shp_name = st.selectbox("변환할 SHP 선택", options=st.session_state.found_shp_in_local)
            st.info(f"선택된 경로: {st.session_state.local_selected_path}")
        
        st.markdown("---")
        
        # 기존 파일 업로더 (웹 배포용)
        uploaded_shp_files = st.file_uploader("또는 여기에 폴더/파일 드래그", type=["shp", "shx", "dbf"], accept_multiple_files=True, key="shp_dxf_uploader_v2", label_visibility="visible")
        
        # 데이터 소스 결정 (로컬 폴더 vs 업로드 파일)
        shp_data, shx_data, dbf_data = None, None, None
        shp_display_name = ""

        if target_shp_name and st.session_state.get("local_selected_path"):
            # 로컬 파일 읽기
            base_p = os.path.join(st.session_state.local_selected_path, os.path.splitext(target_shp_name)[0])
            try:
                with open(base_p + ".shp", "rb") as f: shp_data = f.read()
                with open(base_p + ".shx", "rb") as f: shx_data = f.read()
                with open(base_p + ".dbf", "rb") as f: dbf_data = f.read()
                shp_display_name = target_shp_name
            except:
                st.error("⚠️ 로컬 파일을 읽는 중 오류가 발생했습니다. (세트 파일 누락 등)")
        elif uploaded_shp_files:
            # 업로드 파일에서 찾기
            f_shp = next((f for f in uploaded_shp_files if f.name.lower().endswith(".shp")), None)
            f_shx = next((f for f in uploaded_shp_files if f.name.lower().endswith(".shx")), None)
            f_dbf = next((f for f in uploaded_shp_files if f.name.lower().endswith(".dbf")), None)
            if f_shp and f_shx and f_dbf:
                shp_data, shx_data, dbf_data = f_shp.getvalue(), f_shx.getvalue(), f_dbf.getvalue()
                shp_display_name = f_shp.name

        if shp_data and shx_data and dbf_data:
            from modules.shp_converter import get_shp_fields_from_io, convert_shp_to_dxf_bytes
            import io
            
            # 필드 정보 읽기
            fields = get_shp_fields_from_io(io.BytesIO(shp_data), io.BytesIO(shx_data), io.BytesIO(dbf_data))
            
            if fields:
                st.markdown("---")
                st.markdown("<p style='font-size:13px; font-weight:bold;'>속성 필드 및 소수점 설정</p>", unsafe_allow_html=True)
                
                selected_fields = {}
                cols = st.columns(2)
                for idx, f_name in enumerate(fields):
                    with cols[idx % 2]:
                        f_col1, f_col2 = st.columns([1, 1])
                        is_sel = f_col1.checkbox(f_name, key=f"shp_f_v2_{f_name}")
                        if is_sel:
                            prec = f_col2.number_input("소수점", min_value=0, max_value=10, value=0, step=1, key=f"shp_p_v2_{f_name}", label_visibility="collapsed")
                            selected_fields[f_name] = prec
                
                txt_size = st.slider("텍스트 크기", 0.1, 10.0, 2.0, 0.1, key="shp_txt_size_v2")
                
                if st.button("🚀 변환 및 다운로드 준비", type="primary", use_container_width=True):
                    try:
                        with st.spinner("DXF 파일 생성 중..."):
                            dxf_bytes = convert_shp_to_dxf_bytes(
                                io.BytesIO(shp_data), 
                                io.BytesIO(shx_data), 
                                io.BytesIO(dbf_data), 
                                selected_fields, 
                                txt_size
                            )
                            st.session_state.shp_convert_result = dxf_bytes
                            st.session_state.shp_convert_name = os.path.splitext(shp_display_name)[0] + ".dxf"
                            st.success("✅ 변환이 완료되었습니다. 아래 버튼을 눌러 저장하세요.")
                    except Exception as e:
                        st.error(f"❌ 변환 오류: {e}")
                    
                    if st.session_state.get("shp_convert_result"):
                        st.download_button(
                            label="📥 변환된 DXF 파일 다운로드",
                            data=st.session_state.shp_convert_result,
                            file_name=st.session_state.shp_convert_name,
                            mime="application/dxf",
                            use_container_width=True
                        )
                else:
                    st.warning("⚠️ 필드 정보를 읽을 수 없습니다.")
            else:
                st.info("💡 SHP, SHX, DBF 파일 3개를 모두 업로드해 주세요.")

    if st.button("🖥️ [로컬] 기존 프로그램 실행", use_container_width=True):
        import subprocess
        import sys
        program_path = os.path.join(os.getcwd(), "tools", "shp_to_dxf.py")
        if os.path.exists(program_path):
            try:
                subprocess.Popen([sys.executable, program_path], 
                                 creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0)
            except Exception as e:
                st.error(f"❌ 실행 오류: {e}")

# ============================
# DXF 해석 파트
# ============================
if uploaded_file:
    with st.spinner("📐 도면 좌표를 분석하는 중..."):
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            dxf_result = parse_dxf(tmp_path, source_crs=selected_epsg)
            os.remove(tmp_path)
            
            if is_new_file or crs_changed:
                st.session_state.map_center = dxf_result["center"]
                st.session_state.map_zoom = 16
                st.session_state.map_force_center_id += 1
                
                # 새로운 파일이나 좌표계가 변경되면 이전 분석 결과를 초기화 및 PNU 자동 추출 시작
                st.session_state.do_pnu_extract = True
                st.session_state.do_status_analysis = False
                st.session_state.do_word_report = False
                st.session_state.do_qbs = False
                st.session_state.do_free_transfer = False
                st.session_state.pnu_list = None
                st.session_state.all_sheets = None
                if "excel_bytes" in st.session_state: del st.session_state["excel_bytes"]
                if "report_bytes" in st.session_state: del st.session_state["report_bytes"]
        except Exception as e:
            st.error(f"❌ DXF 파일 오류: {e}")
            st.stop()

# ★ 그리기 모드: DXF 대신 session_state의 drawn_dxf_result를 dxf_result로 주입
#   → 이후 모든 분석 흐름(WFS 다운로드, PNU 추출, 토지조서, 보고서 등)이 동일하게 동작
if not uploaded_file and st.session_state.get("drawn_dxf_result"):
    dxf_result = st.session_state.drawn_dxf_result

# ============================
# 다운로드 실행 처리부 (단방향 실행 및 상태 유지)
# ============================
if st.session_state.get("do_wfs_download") and dxf_result.get("gps_points"):
    st.session_state.do_wfs_download = False # 1회성 플래그 (리런 방지용)
    req_layers = st.session_state.map_layers
    
    # BBOX를 앱 내에서 직접 계산 (VWorld WFS 1.1.0은 BBOX로 minLat, minLon, maxLat, maxLon 순서를 요구함)
    lons = [p[1] for p in dxf_result["gps_points"]]
    lats = [p[0] for p in dxf_result["gps_points"]]
    dl_bbox = f"{min(lats)-0.003},{min(lons)-0.005},{max(lats)+0.003},{max(lons)+0.005}"
    
    with st.spinner(f"📥 선택된 {len(req_layers)}개 레이어의 공간 데이터를 추출하는 중입니다..."):
        dl_result_bytes_list = []
        total_count = 0
        try:
            for req_layer in req_layers:
                try:
                    result = fetch_wfs_data(req_layer, dl_bbox, VWORLD_KEY)
                    if not result: continue
                    geojson_data = result["geojson"]
                    feat_count = result["count"]
                    
                    if feat_count > 0:
                        total_count += feat_count
                        dl_target_epsg = st.session_state.dl_target_epsg
                        boundary_pts = dxf_result.get("lonlat_points", None)
                        
                        dl_result_bytes_list.append({
                            "layer": req_layer,
                            "count": feat_count,
                            "dxf": export_to_dxf(geojson_data, req_layer, dl_target_epsg, boundary_pts),
                            "shp": export_to_shp(geojson_data, req_layer, dl_target_epsg, boundary_pts)
                        })
                except Exception as ex:
                    # 개별 레이어 에러 시 패스 (VWorld 측에서 해당 레이어 WFS 미제공 등)
                    pass
            
            if total_count == 0:
                st.warning(f"⚠️ 현재 대상지 반경에 추출할 대상물이 존재하지 않습니다.")
                if "dl_result_bytes_list" in st.session_state:
                    del st.session_state["dl_result_bytes_list"]
            else:
                st.session_state.dl_result_bytes_list = dl_result_bytes_list
                st.session_state.dl_total_count = total_count
        except Exception as e:
            st.error(f"❌ 전체 추출 실패: {e}")




# ============================
# 메인 화면 레이아웃 분할 (지도 / 우측 패널)
# ============================
map_col, panel_col = st.columns([2.8, 1.2], gap="small")

with panel_col:
    # 우측 패널 전체를 시각적으로 감싸는 테두리 박스
    with st.container(border=True):
        st.markdown("<p class='kh-panel-title'>분석 결과</p>", unsafe_allow_html=True)
        
        panel_info_container = st.container()
        panel_status_container = st.container()
        panel_result_container = st.container()
        panel_download_container = st.container()
    
        with panel_info_container:
            if uploaded_file:
                st.success("✅ DXF 파일 업로드 완료")
                if dxf_result.get('num_vertices', 0) > 0:
                    st.success(f"✅ 구역계 {dxf_result['num_vertices']}개 꼭짓점 매핑됨")
            elif st.session_state.get("drawn_dxf_result"):
                drawn = st.session_state.drawn_dxf_result
                st.success("✅ 지도에서 그린 영역 적용됨")
                st.success(f"✅ 구역계 {drawn.get('num_vertices', 0)}개 꼭짓점 매핑됨")
            else:
                st.info("👈 왼쪽 사이드바에서 DXF 파일을 올리거나, '🖌️ 지도에서 직접 그리기'로 영역을 지정해주세요.")
            
            if st.session_state.get("dl_result_bytes_list"):
                dl_list = st.session_state.dl_result_bytes_list
                st.success(f"🎉 도면 데이터 병합 완료! ({st.session_state.get('dl_total_count', 0)}건)")
                
                import zipfile
                import io
    
                dxf_zip_buf = io.BytesIO()
                with zipfile.ZipFile(dxf_zip_buf, "w", zipfile.ZIP_DEFLATED) as master_zf:
                    for item in dl_list:
                        safe_layer = str(item['layer']).replace('/', '_').replace('\\', '')
                        master_zf.writestr(f"{safe_layer}.dxf", item['dxf'])
                        
                master_zip_buf = io.BytesIO()
                with zipfile.ZipFile(master_zip_buf, "w", zipfile.ZIP_DEFLATED) as master_zf:
                    for item in dl_list:
                        safe_layer = str(item['layer']).replace('/', '_').replace('\\', '')
                        master_zf.writestr(f"DXF/{safe_layer}.dxf", item['dxf'])
                        with zipfile.ZipFile(io.BytesIO(item['shp']), "r") as shp_zf:
                            for shp_filename in shp_zf.namelist():
                                master_zf.writestr(f"SHP/{shp_filename}", shp_zf.read(shp_filename))
                                
                st.download_button(f"💾 도면 일괄 다운로드 (.dxf)", dxf_zip_buf.getvalue(), f"도면추출_DXF.zip", "application/zip", use_container_width=True)
                st.download_button(f"💾 도면 풀패키지 (통합압축)", master_zip_buf.getvalue(), f"도면추출_통합팩.zip", "application/zip", type="primary", use_container_width=True)

with map_col:
    # 배경지도 선택을 작은 selectbox로 (라디오 5개 가로보다 컴팩트)
    base_map_options = list(VWORLD_TILE_URLS.keys())
    _bg_col, _spacer = st.columns([1, 4])
    with _bg_col:
        base_map = st.selectbox(
            "배경지도",
            options=base_map_options,
            label_visibility="collapsed",
            key="base_map_select",
        )
    
    if base_map != st.session_state.last_base_map:
        st.session_state.last_base_map = base_map
    
    # 지도 빌드 — 앱에서 관리하는 선택된 렌더링 레이어 배열 전달
    _draw_mode = (st.session_state.get("boundary_mode") == "🖌️ 지도에서 직접 그리기")
    _locate_auto = (not uploaded_file) and (not st.session_state.get("search_marker")) and (not _draw_mode)

    # ★ 그리기 모드 — 지도 바로 위에 [✅ 그린 영역 적용] [🗑️ 그린 영역 지움] 버튼 배치
    #   사이드바에 두는 것보다 지도와 가깝게 보여 사용성 ↑
    if _draw_mode:
        tb_col1, tb_col2, tb_col3 = st.columns([1.2, 1.2, 4])
        with tb_col1:
            apply_drawn = st.button(
                "✅ 그린 영역 적용",
                use_container_width=True, type="primary",
                key="apply_draw_map_top",
                help="지도에서 그린 도형을 분석 영역으로 적용",
            )
        with tb_col2:
            clear_drawn = st.button(
                "🗑️ 그린 영역 지움",
                use_container_width=True,
                key="clear_draw_map_top",
                help="그린 도형과 분석 결과 모두 초기화",
            )
        with tb_col3:
            n_vertices = (st.session_state.get("drawn_dxf_result") or {}).get("num_vertices", 0)
            # 적용된 그린 폴리곤의 측지 면적 계산 (WGS84 → 타원체 표면 면적, ㎡)
            area_text = ""
            applied_poly = (st.session_state.get("drawn_dxf_result") or {}).get("polygon") \
                           or st.session_state.get("drawn_polygon")
            if applied_poly is not None and not applied_poly.is_empty:
                try:
                    from pyproj import Geod
                    geod = Geod(ellps="WGS84")
                    area_m2, _ = geod.geometry_area_perimeter(applied_poly)
                    area_m2 = abs(area_m2)
                    pyeong = area_m2 / 3.305785  # 1평 = 400/121 ≒ 3.3058 ㎡
                    area_text = f"{area_m2:,.0f}㎡ ({pyeong:,.0f}평)"
                except Exception:
                    pass

            if n_vertices:
                area_html = (f" | 📐 면적 <b>{area_text}</b>" if area_text else "")
                st.markdown(
                    f"<p style='font-size:13px; color:#ff5722; margin: 0; padding-top: 6px;'>"
                    f"🖌️ 현재 그린 영역: <b>꼭짓점 {n_vertices}개</b>{area_html}"
                    f"</p>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<p style='font-size:13px; color:#888; margin: 0; padding-top: 6px;'>"
                    "🖌️ 지도 좌상단 도구로 영역을 그린 후 [적용] 클릭"
                    "</p>",
                    unsafe_allow_html=True,
                )

        if clear_drawn:
            st.session_state.drawn_polygon = None
            st.session_state.drawn_dxf_result = None
            st.session_state.pop("pnu_list", None)
            st.session_state.pop("all_sheets", None)
            if "excel_bytes" in st.session_state:
                del st.session_state["excel_bytes"]
            st.rerun()
        # apply_drawn 처리는 지도 렌더링 후 (그린 도형 캡처 후)
        st.session_state.apply_drawn_pending = apply_drawn

    # ★ 그리기 모드에서 이전에 그린 도형이 세션에 있으면 dxf_result에 주입
    #   → create_map이 빨간 폴리곤으로 다시 그려서 사용자가 확인 가능
    if _draw_mode and st.session_state.get("drawn_dxf_result"):
        dxf_result = st.session_state.drawn_dxf_result

    # ★ 명시적 이동 요청(DXF 업로드/장소 검색/좌표계 변경/그린영역 적용) 감지하여
    #   view_center를 map_center로 동기화 → 명시적 이동 시점에만 view_center 강제 갱신.
    if st.session_state.get("_applied_force_id") != st.session_state.get("map_force_center_id"):
        st.session_state.view_center = list(st.session_state.map_center)
        st.session_state.view_zoom = st.session_state.map_zoom
        st.session_state._applied_force_id = st.session_state.map_force_center_id

    # ★ 지도 초기 위치 결정 — view_center(사용자가 본 마지막 위치) 우선
    #   라디오/체크박스 클릭으로 페이지 재실행 시에도 사용자가 보던 위치 유지 (점프 방지)
    _map_render_center = st.session_state.get("view_center") or st.session_state.map_center
    _map_render_zoom = st.session_state.get("view_zoom") or st.session_state.map_zoom

    vworld_map = create_map(
        center=_map_render_center,
        gps_points=dxf_result["gps_points"],
        base_map=base_map if base_map else "일반지도",
        zoom_start=_map_render_zoom,
        locate_on_start=_locate_auto,
        visible_layers=st.session_state.map_layers,
        legend_layer_name=st.session_state.get("last_checked_layer"),
        force_center_id=st.session_state.map_force_center_id,
        enable_draw=_draw_mode,
    )

    # 검색 마커가 있다면 지도에 표시 (아이콘 핀)
    if st.session_state.get("search_marker"):
        marker_data = st.session_state.search_marker
        folium.Marker(
            location=[marker_data['lat'], marker_data['lon']],
            popup=f"<b>{marker_data['name']}</b>",
            tooltip=marker_data['name'],
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(vworld_map)

    # ★ 그리기 모드 안내 (드로잉 도구 사용법)
    if _draw_mode:
        st.markdown(
            "<p style='font-size:12px; color:#ff5722; margin: 4px 0;'>"
            "🖌️ <b>그리기 모드</b>: 지도 좌상단 도구로 다각형/사각형을 그린 후 사이드바의 "
            "<b>'✅ 그린 영역 적용'</b> 버튼을 누르세요."
            "</p>",
            unsafe_allow_html=True,
        )

    # ★ 모드별 returned_objects 분기 — 점프와 깜빡임 둘 다 최소화
    #   - DXF 모드: center/zoom 캡처 → 사용자가 본 마지막 위치를 Python에 저장 →
    #              라디오/체크박스 클릭 시에도 그 위치 유지 (그리기 모드 진입 시 점프 방지)
    #   - 그리기 모드: all_drawings만 → 도형 그리는 동안 페이지 재실행 X (깜빡임/점 손실 방지)
    if _draw_mode:
        _returned = ["all_drawings", "last_active_drawing"]
    else:
        _returned = ["center", "zoom"]

    map_data = st_folium(
        vworld_map,
        width=1200,
        height=750,
        returned_objects=_returned,
        key="main_map",
    )

    # DXF 모드에서만 사용자 위치 캡처 (그리기 모드는 깜빡임 방지를 위해 캡처 안 함)
    if not _draw_mode and map_data:
        new_center = map_data.get("center")
        new_zoom = map_data.get("zoom")
        if new_center:
            st.session_state.view_center = [new_center["lat"], new_center["lng"]]
        if new_zoom:
            st.session_state.view_zoom = int(new_zoom)

    # 그린 도형을 dxf_result 호환 형식으로 변환하여 캐싱 (그리기 모드만)
    if _draw_mode and map_data and map_data.get("all_drawings"):
        from shapely.geometry import shape as _shp_shape
        try:
            drawings = map_data["all_drawings"] or []
            if drawings:
                last_geom_dict = (map_data.get("last_active_drawing") or drawings[-1]).get("geometry")
                if last_geom_dict:
                    poly_wgs84 = _shp_shape(last_geom_dict)
                    if poly_wgs84.geom_type in ("Polygon", "MultiPolygon"):
                        if poly_wgs84.geom_type == "Polygon":
                            coords = list(poly_wgs84.exterior.coords)
                        else:
                            coords = list(list(poly_wgs84.geoms)[0].exterior.coords)
                        gps_pts = [(lat, lon) for lon, lat in coords]
                        lonlat_pts = [(lon, lat) for lon, lat in coords]
                        centroid = poly_wgs84.centroid
                        st.session_state.drawn_polygon = poly_wgs84
                        st.session_state.drawn_dxf_result = {
                            "polygon": poly_wgs84,
                            "gps_points": gps_pts,
                            "lonlat_points": lonlat_pts,
                            "center": (centroid.y, centroid.x),
                            "num_vertices": len(coords),
                        }
        except Exception as draw_err:
            st.warning(f"⚠️ 그린 도형 처리 오류: {draw_err}")

    # 사이드바에서 "그린 영역 적용" 버튼을 눌렀을 때 분석 트리거
    if _draw_mode and st.session_state.get("apply_drawn_pending") and st.session_state.get("drawn_dxf_result"):
        st.session_state.apply_drawn_pending = False
        st.session_state.do_pnu_extract = True
        dxf_result = st.session_state.drawn_dxf_result
        # 그린 폴리곤 중심으로 이동 (사용자가 명시적으로 "적용"한 경우만)
        st.session_state.view_center = list(dxf_result["center"])
        st.session_state.map_center = list(dxf_result["center"])
        st.success(f"✅ 그린 영역 적용됨 ({dxf_result['num_vertices']}꼭짓점). PNU 추출 시작...")

    # 기존 그린 결과가 있으면 dxf_result에 주입 (분석 파이프라인 호환)
    if _draw_mode and st.session_state.get("drawn_dxf_result"):
        dxf_result = st.session_state.drawn_dxf_result

# ============================
# 분석(편입 필지 및 속성 조서) 실행부
# ============================
# DXF 업로드 또는 지도에서 그린 영역 중 하나라도 있어야 분석 진행
_has_boundary = (uploaded_file is not None) or (st.session_state.get("drawn_dxf_result") is not None)
if not _has_boundary:
    st.stop()

# 1. PNU 자동 추출 (파일 업로드 시)
if st.session_state.get("do_pnu_extract"):
    st.session_state.do_pnu_extract = False
    
    with panel_status_container:
        with st.status("🔍 편입 필지 추출 중...", expanded=True) as status:
            try:
                pnu_list = extract_pnu_list(dxf_result["polygon"], VWORLD_KEY)
                st.session_state.pnu_list = pnu_list
                status.update(label=f"✅ PNU {len(pnu_list)}필지 추출 완료", state="complete", expanded=False)
            except Exception as e:
                status.update(label=f"❌ PNU 오류 발생", state="error", expanded=True)
                st.error(str(e))

# 2. 토지대장 현황 분석 (캐시 우선 로드 → 캐시 미스 시 API 분석 → 캐시 저장)
if st.session_state.get("do_status_analysis"):
    st.session_state.do_status_analysis = False 
    
    if not st.session_state.get("pnu_list"):
        st.warning("⚠️ 먼저 PNU 추출이 완료되어야 합니다.")
    else:
        pnu_list = st.session_state.pnu_list
        force = st.session_state.get("force_reanalyze", False)
        
        # 프로젝트 캐시 확인 (DXF 파일 해시 기반)
        fhash = _file_hash(uploaded_file) if uploaded_file else None
        cached_result = None
        if fhash and not force:
            cached_result = _load_project_cache(fhash)
        
        if cached_result:
            # ★ 캐시 히트! — API 호출 없이 즉시 로드 (1초 이내)
            with panel_status_container:
                st.session_state.all_sheets = cached_result
                st.session_state.excel_bytes = create_multi_sheet_excel(cached_result)
                st.success("⚡ 이전 분석 결과를 로컬 캐시에서 즉시 불러왔습니다! (API 미호출)")
        else:
            # 캐시 미스 — 실제 API 분석 수행
            with panel_status_container:
                with st.status("📊 현황 데이터 분석 중..." + (" (강제 재분석)" if force else ""), expanded=True) as status:
                    all_sheets = {}
                    for analyzer in selected_analyzers:
                        try:
                            results = analyzer.analyze(pnu_list, VWORLD_KEY)
                            all_sheets[analyzer.name] = results
                        except Exception as e:
                            st.error(f"❌ 실패: {e}")
                            traceback.print_exc()
                    
                    st.session_state.all_sheets = all_sheets
                    
                    # 분석 성공 시 엑셀 바이너리 생성 및 캐시 파일 저장
                    if all_sheets:
                        st.session_state.excel_bytes = create_multi_sheet_excel(all_sheets)
                        if fhash:
                            _save_project_cache(fhash, all_sheets)
                            st.info(f"💾 분석 결과가 로컬에 캐시 저장되었습니다. 다음 실행 시 즉시 로드됩니다.")
                    
                    status.update(label="✅ 분석 및 엑셀 생성 성공!", state="complete", expanded=False)

# 결과 렌더링 (패널 안쪽)
if st.session_state.get("pnu_list"):
    with panel_result_container:
        st.markdown("**📋 편입 필지 (Pnu)**")
        with st.expander(f"편입 필지 구조 ({len(st.session_state.pnu_list)}건)", expanded=False):
            display_df = [ {k: v for k, v in p.items() if k != "지적도형"} for p in st.session_state.pnu_list ]
            st.dataframe(display_df, use_container_width=True)

if st.session_state.get("all_sheets"):
    with panel_result_container:
        st.markdown("**📊 분석 결과**")
        for sheet_name, results in st.session_state.all_sheets.items():
            with st.expander(f"✅ {sheet_name}", expanded=False):
                st.dataframe(results, use_container_width=True)
    
    if "excel_bytes" in st.session_state:
        with panel_download_container:
            st.download_button(
                "📥 자동현황 분석결과(Excel)",
                data=st.session_state.excel_bytes,
                file_name="현황분석조서.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

# 3. 워드 보고서 생성 실행
if st.session_state.get("do_word_report"):
    st.session_state.do_word_report = False
    
    if not st.session_state.get("pnu_list") or not st.session_state.get("all_sheets"):
        st.warning("⚠️ 대상지 현황 분석결과 보고서를 생성하려면 먼저 '자동현황 분석결과' 버튼을 눌러 분석을 완료해주세요.")
    else:
        with panel_status_container:
            with st.status("📄 보고서 생성 중...", expanded=True) as status:
                st.info("🎨 테마 지도 및 표 데이터 병합 중...")
                try:
                    land_data = []
                    for p in st.session_state.pnu_list:
                        p_copy = p.copy()
                        if "토지조서 (편입면적/공시지가 등)" in st.session_state.all_sheets:
                            for row in st.session_state.all_sheets["토지조서 (편입면적/공시지가 등)"]:
                                if row["PNU"] == p["PNU"]:
                                    p_copy["analysis_attr"] = row
                                    break
                        land_data.append(p_copy)
                    
                    st.write("🗺️ 테마 지도 생성 중...")
                    owner_img, jimok_img = None, None
                    try:
                        from modules.map_builder import create_thematic_map
                        owner_img = create_thematic_map(dxf_result["polygon"], land_data, "소유자")
                        jimok_img = create_thematic_map(dxf_result["polygon"], land_data, "지목")
                    except Exception as me:
                        st.warning(f"테마 지도 건너뜀: {me}")
    
                    st.write("✍️ 문서 렌더링 중...")
                    report_gen = LandReportGenerator(
                        analysis_data=land_data,
                        boundary_polygon=dxf_result["polygon"],
                        owner_map_bytes=owner_img,
                        jimok_map_bytes=jimok_img
                    )
                    st.session_state.report_bytes = report_gen.generate()
                    status.update(label="✅ 보고서 생성 완료!", state="complete", expanded=False)
                except Exception as re:
                    status.update(label="❌ 오류 발생", state="error", expanded=True)
                    st.error(str(re))
                    st.session_state.report_bytes = None

if st.session_state.get("report_bytes"):
    with panel_download_container:
        # 파일 내용은 docx 그대로, 확장자만 .hwpx — 한글에서 자동으로 열림
        # (한글이 OOXML 호환으로 docx 콘텐츠 인식)
        st.download_button(
            "📥 대상지현황 분석결과 보고서(Hwp)",
            data=st.session_state.report_bytes,
            file_name="현황분석보고서.hwpx",
            mime="application/octet-stream",
            type="primary",
            use_container_width=True,
        )

# 3. QBS 위치도 삽도 실행
if st.session_state.get("do_qbs"):
    st.session_state.do_qbs = False
    
    with panel_status_container:
        with st.status("🗺️ QBS 위치도 생성 중...", expanded=True) as status:
            try:
                from report.qbs_generator import QBSGenerator
                st.write("🌍 배경지도 및 레이어 병합 중 (시간이 소요될 수 있습니다)...")
                
                # 사용자가 현재 켜놓은 레이어 목록
                visible_layers = st.session_state.get("map_layers", [])
                
                qbs_gen = QBSGenerator(dxf_result["polygon"], visible_layers)
                st.session_state.qbs_bytes = qbs_gen.generate()
                
                status.update(label="✅ QBS 위치도 생성 완료!", state="complete", expanded=False)
            except Exception as e:
                status.update(label="❌ 위치도 생성 실패", state="error", expanded=True)
                st.error(f"오류: {e}")

if st.session_state.get("qbs_bytes"):
    with panel_download_container:
        st.download_button(
            "📥 QBS 위치도 삽도(PPT)",
            data=st.session_state.qbs_bytes,
            file_name="qbs_위치도.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            type="primary",
            use_container_width=True,
        )

# 3-1. 편입산지조서 작성 실행
if st.session_state.get("do_mountain_report"):
    st.session_state.do_mountain_report = False

    if not st.session_state.get("pnu_list") or not st.session_state.get("all_sheets"):
        st.warning("⚠️ 편입산지조서를 작성하려면 먼저 '자동현황 분석결과' 버튼을 눌러 분석을 완료해주세요.")
    else:
        with panel_status_container:
            with st.status("🌲 편입산지조서 생성 중...", expanded=True) as status:
                try:
                    from modules.mountain_exporter import create_mountain_report

                    # 토지조서 분석 결과에서 데이터 사용
                    ledger_key = "토지조서 (편입면적/공시지가 등)"
                    if ledger_key not in st.session_state.all_sheets:
                        status.update(label="❌ 토지조서 데이터가 없습니다.", state="error", expanded=True)
                        st.error("토지조서 분석 결과가 필요합니다. 자동현황 분석을 먼저 실행하세요.")
                    else:
                        st.write("📂 산지 필지 필터링 (지목=임 또는 필지구분=산)...")
                        mountain_bytes = create_mountain_report(st.session_state.all_sheets[ledger_key])

                        if mountain_bytes is None:
                            status.update(label="⚠️ 산지 필지가 없습니다.", state="complete", expanded=True)
                            st.info("대상지에 산지(지목=임 또는 필지구분=산) 필지가 없어 조서가 생성되지 않았습니다.")
                        else:
                            st.session_state.mountain_bytes = mountain_bytes
                            status.update(label="✅ 편입산지조서 생성 완료!", state="complete", expanded=False)
                except Exception as e:
                    status.update(label="❌ 편입산지조서 생성 실패", state="error", expanded=True)
                    st.error(f"오류: {e}")

if st.session_state.get("mountain_bytes"):
    with panel_download_container:
        st.download_button(
            "📥 편입산지조서(Excel)",
            data=st.session_state.mountain_bytes,
            file_name="편입산지조서.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
            key="dl_mountain",
        )

# 4. 소유자 구분도 작성 실행 (DXF 패키지만)
if st.session_state.get("do_free_transfer"):
    st.session_state.do_free_transfer = False

    if not st.session_state.get("pnu_list") or not st.session_state.get("all_sheets"):
        st.warning("⚠️ 소유자 구분도를 작성하려면 먼저 '자동현황 분석결과' 버튼을 눌러 분석을 완료해주세요.")
    else:
        with panel_status_container:
            with st.status("🗺️ 소유자 구분도 (DXF) 생성 중...", expanded=True) as status:
                try:
                    st.write("📂 대상 필지 선별 및 분석 데이터 병합 중...")

                    # 분석 데이터(all_sheets)에서 소유자 정보를 land_data에 병합
                    land_data = []
                    for p in st.session_state.pnu_list:
                        p_copy = p.copy()
                        if "토지조서 (편입면적/공시지가 등)" in st.session_state.all_sheets:
                            for row in st.session_state.all_sheets["토지조서 (편입면적/공시지가 등)"]:
                                if row["PNU"] == p["PNU"]:
                                    p_copy["analysis_attr"] = row
                                    break
                        land_data.append(p_copy)

                    generator = FreeTransferGenerator(dxf_result["polygon"], land_data)

                    # DXF 패키지 (소유자별 파일 + solid 해치)
                    st.write("📐 DXF 패키지 생성 중 (사업지 clipping + solid 해치)...")
                    target_epsg = st.session_state.get("dl_target_epsg", "EPSG:5186")
                    zip_dxf = generator.generate_dxf(target_epsg=target_epsg)

                    if not zip_dxf:
                        status.update(label="⚠️ 분석 가능한 필지가 없습니다.", state="complete", expanded=True)
                    else:
                        st.session_state.free_transfer_zip_dxf = zip_dxf
                        st.session_state.free_transfer_ready = True
                        status.update(label="✅ 소유자 구분도 (DXF) 생성 완료!", state="complete", expanded=False)
                except Exception as e:
                    status.update(label="❌ 생성 실패", state="error", expanded=True)
                    st.error(f"오류: {e}")
                    import traceback; traceback.print_exc()

if st.session_state.get("free_transfer_ready") and st.session_state.get("free_transfer_zip_dxf"):
    with panel_download_container:
        st.download_button(
            "📥 소유자 구분도 (DXF 패키지)",
            data=st.session_state.free_transfer_zip_dxf,
            file_name="소유자_구분도_DXF.zip",
            mime="application/zip",
            use_container_width=True,
            key="dl_free_dxf",
        )

# 5. 무상귀속 협의요청서 (hwpx)
if st.session_state.get("do_agreement"):
    st.session_state.do_agreement = False
    if not st.session_state.get("pnu_list") or not st.session_state.get("all_sheets"):
        st.warning("⚠️ 협의요청서를 작성하려면 먼저 '분석 실행' 버튼을 눌러 분석을 완료해주세요.")
    else:
        with panel_status_container:
            with st.status("📋 무상귀속 협의요청서 생성 중...", expanded=True) as status:
                try:
                    from report.agreement_generator import generate_agreement_hwpx, is_public_owner

                    # 분석 데이터(all_sheets)를 land_data에 병합
                    land_data = []
                    for p in st.session_state.pnu_list:
                        p_copy = p.copy()
                        if "토지조서 (편입면적/공시지가 등)" in st.session_state.all_sheets:
                            for row in st.session_state.all_sheets["토지조서 (편입면적/공시지가 등)"]:
                                if row["PNU"] == p["PNU"]:
                                    p_copy["analysis_attr"] = row
                                    break
                        land_data.append(p_copy)

                    # 국공유지 개수 확인
                    n_public = sum(1 for p in land_data
                                   if is_public_owner((p.get("analysis_attr") or {}).get("소유자", "")))
                    st.write(f"📂 국공유지 필지: **{n_public}개** (각각 한 페이지)")

                    if n_public == 0:
                        status.update(label="⚠️ 국공유지 필지가 없어 협의요청서를 생성할 수 없습니다.",
                                      state="complete", expanded=True)
                    else:
                        st.write("📋 hwpx 페이지 복제 + data 불러오는 중...")
                        hwpx_bytes = generate_agreement_hwpx(
                            land_data,
                            boundary_polygon=dxf_result.get("polygon"),
                        )
                        if hwpx_bytes:
                            st.session_state.agreement_hwpx = hwpx_bytes
                            status.update(label=f"✅ 무상귀속 협의요청서 생성 완료 ({n_public}건)",
                                          state="complete", expanded=False)
                        else:
                            status.update(label="❌ 생성 실패", state="error", expanded=True)
                except Exception as e:
                    status.update(label="❌ 생성 실패", state="error", expanded=True)
                    st.error(f"오류: {e}")
                    import traceback; traceback.print_exc()

if st.session_state.get("agreement_hwpx"):
    with panel_download_container:
        st.download_button(
            "📥 무상귀속 협의요청서 (hwpx)",
            data=st.session_state.agreement_hwpx,
            file_name="무상귀속_협의요청서.hwpx",
            mime="application/octet-stream",
            use_container_width=True,
            key="dl_agreement",
        )
