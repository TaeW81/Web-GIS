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

from config import VWORLD_KEY, VWORLD_TILE_URLS, VWORLD_WMS_CATEGORIES, MAP_SOURCES, KOREA_CRS, KOREA_CRS_ORIGINS, VWORLD_WFS_LAYERS
from modules.dxf_parser import parse_dxf
from modules.pnu_extractor import extract_pnu_list
from modules.map_builder import create_map
from modules.excel_exporter import create_multi_sheet_excel
from modules.spatial_downloader import fetch_wfs_data, export_to_dxf, export_to_shp
from modules.vworld_search import search_place
from analyzers import get_all_analyzers

# ============================
st.set_page_config(page_title="KH-GIS LandScan | 통합 현황분석 솔루션", layout="wide", page_icon="📡")
st.title("📡 KH-GIS LandScan: Smart Analysis Platform")
st.caption("건화(KH)의 공간정보 정밀 스캔 기술이 집약된 GIS 기반 토지·건축물 현황분석 자동화 솔루션")

# 사이드바 UI 콤팩트화를 위한 CSS 주입
st.markdown("""
    <style>
    /* 체크박스 줄간격 및 내부 여백 축소 */
    div[data-testid="stSidebar"] div[data-testid="stCheckbox"] {
        margin-bottom: -15px !important;
    }
    div[data-testid="stSidebar"] div[data-testid="stCheckbox"] label {
        font-size: 13px !important;
        padding-top: 1px !important;
        padding-bottom: 1px !important;
    }
    /* expander 헤더와 내용물 사이 여백 축소 */
    div[data-testid="stExpander"] div[data-testid="stVerticalBlock"] {
        gap: 0.1rem !important;
    }
    /* 박스(Expander) 사이의 외부 간격 축소 */
    div[data-testid="stExpander"] {
        margin-bottom: -10px !important;
    }
    /* 박스 내부(Details) 여백 축소 */
    div[data-testid="stExpanderDetails"] {
        padding-top: 0.5rem !important;
        padding-bottom: 0.5rem !important;
        padding-left: 0.7rem !important;
        padding-right: 0.7rem !important;
    }
    /* 박스 제목줄(Summary) 높이 축소 */
    div[data-testid="stExpanderSummary"] {
        padding-top: 0px !important;
        padding-bottom: 0px !important;
        min-height: 2.2rem !important;
    }
    /* 탭 간격 축소 */
    div[data-testid="stSidebar"] button[data-baseweb="tab"] {
        padding-left: 10px !important;
        padding-right: 10px !important;
        font-size: 12px !important;
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
            "<strong style='font-size: 1.1rem; color: #1e293b;'>📡 KH-GIS LandScan</strong><br>"
            "<span style='font-size: 0.8rem; color: gray;'>Smart Analysis Platform</span>"
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
    # 1. 구역계 범위 업로드
    # ----------------------------------------
    st.markdown("<p style='font-weight:bold; font-size:15px; margin: 10px 0 5px 0;'>1. 구역계 범위 업로드</p>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader("구역계 파일(.dxf)", type=["dxf"], label_visibility="collapsed")
    is_new_file = False
    if uploaded_file and st.session_state.get('last_uploaded_file') != uploaded_file.name:
        is_new_file = True
        st.session_state.last_uploaded_file = uploaded_file.name
    
    st.markdown("<p style='font-size:13px; font-weight:bold; margin: 0;'>도면 좌표계</p>", unsafe_allow_html=True)
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

    st.markdown("<p style='font-weight:bold; font-size:15px; margin: 15px 0 5px 0;'>2. 지도 및 기초데이터 설정</p>", unsafe_allow_html=True)
    
    
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
                with st.expander(f"📁 {cat_name}", expanded=(cat_name == "기본 및 지적")):
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
        if not uploaded_file:
            st.warning("⚠️ 구역계(DXF) 파일이 없어 추출할 수 없습니다. 상단에서 구역계를 업로드해주세요.")
        else:
            st.session_state.do_wfs_download = True
            if "dl_result_bytes_list" in st.session_state:
                del st.session_state["dl_result_bytes_list"]

    # ----------------------------------------
    # 3. 수치지도추출(추후개발)
    # ----------------------------------------
    st.markdown("<p style='font-weight:bold; font-size:15px; margin: 15px 0 5px 0;'>3. 수치지도추출 <span style='font-size:12px; color:gray;'>(추후개발)</span></p>", unsafe_allow_html=True)
    
    # ----------------------------------------
    # 4. 현황 조서 분석 항목
    # ----------------------------------------
    st.markdown("<p style='font-weight:bold; font-size:15px; margin: 15px 0 5px 0;'>4. 현황 조서 분석 항목</p>", unsafe_allow_html=True)
    all_analyzers = get_all_analyzers()
    selected_analyzers = [a for a in all_analyzers if st.checkbox(a.name, value=True, help=a.description)]
    
    # 추후 개발 시각적 표시
    st.checkbox("산지전용 조서 작성 (excel조서) (예정)", disabled=True, value=False)
    st.checkbox("농지전용 조서 작성 (excel조서) (예정)", disabled=True, value=False)

    start_analysis_btn = st.button("🚀 분석하기", type="primary", use_container_width=True)
    if start_analysis_btn:
        if not uploaded_file:
            st.warning("⚠️ 구역계(DXF) 파일이 없어 분석을 시작할 수 없습니다.")
        elif not selected_analyzers:
            st.warning("⚠️ 분석할 항목을 하나 이상 선택해주세요.")
        else:
            st.session_state.do_status_analysis = True
            # 기존 결과 초기화
            st.session_state.pnu_list = None
            st.session_state.all_sheets = None

    # ----------------------------------------
    # 5. 대상지 현황 분석_보고서(추후개발)
    # ----------------------------------------
    st.markdown("<p style='font-weight:bold; font-size:15px; margin: 15px 0 5px 0;'>5. 대상지 현황 분석 보고서 <span style='font-size:12px; color:gray;'>(추후개발)</span></p>", unsafe_allow_html=True)
    st.checkbox("위치도 작성 (예정)", disabled=True, value=False)

# ============================
# DXF 해석 파트
# ============================
if uploaded_file:
    st.sidebar.success("✅ 파일 업로드 장전 완료!")
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
        except Exception as e:
            st.error(f"❌ DXF 파일 오류: {e}")
            st.stop()
else:
    st.info("👈 왼쪽 사이드바에서 캐드선(DXF) 파일을 먼저 올려주세요.")

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

# 캐시된 다운로드 파일이 세션에 존재하면 일괄 다운로드 압축 파일 생성
if st.session_state.get("dl_result_bytes_list"):
    dl_list = st.session_state.dl_result_bytes_list
    st.success(f"🎉 성공적으로 선택된 도면 데이터(총 {st.session_state.get('dl_total_count', 0)}건)를 추출 병합 완료했습니다!")
    
    import zipfile
    import io

    # DXF 묶음 생성
    dxf_zip_buf = io.BytesIO()
    with zipfile.ZipFile(dxf_zip_buf, "w", zipfile.ZIP_DEFLATED) as master_zf:
        for item in dl_list:
            safe_layer = str(item['layer']).replace('/', '_').replace('\\', '')
            master_zf.writestr(f"{safe_layer}.dxf", item['dxf'])
            
    # 종합 통합 패키지 (DXF + SHP 폴더 구조)
    master_zip_buf = io.BytesIO()
    with zipfile.ZipFile(master_zip_buf, "w", zipfile.ZIP_DEFLATED) as master_zf:
        for item in dl_list:
            safe_layer = str(item['layer']).replace('/', '_').replace('\\', '')
            master_zf.writestr(f"DXF/{safe_layer}.dxf", item['dxf'])
            # SHP 압축해제 후 재압축
            with zipfile.ZipFile(io.BytesIO(item['shp']), "r") as shp_zf:
                for shp_filename in shp_zf.namelist():
                    master_zf.writestr(f"SHP/{shp_filename}", shp_zf.read(shp_filename))
                    
    colA, colB = st.columns(2)
    colA.download_button(f"💾 전체 도면 일괄 다운로드 (.dxf 압축)", dxf_zip_buf.getvalue(), f"도면추출_DXF.zip", "application/zip", use_container_width=True)
    colB.download_button(f"💾 전체 공간정보 풀패키지 (DXF+SHP 통합압축)", master_zip_buf.getvalue(), f"도면추출_통합팩.zip", "application/zip", type="primary", use_container_width=True)


# ============================
# VWorld 지도 렌더링 
# ============================
st.subheader("📍 대상지 위치도")

base_map_options = list(VWORLD_TILE_URLS.keys())
base_map = st.radio("맵 레이아웃(배경)", options=base_map_options, horizontal=True, label_visibility="collapsed")

if base_map != st.session_state.last_base_map:
    st.session_state.last_base_map = base_map

# 지도 빌드 — 앱에서 관리하는 선택된 렌더링 레이어 배열 전달
_locate_auto = (not uploaded_file) and (not st.session_state.get("search_marker"))
vworld_map = create_map(
    center=st.session_state.map_center,
    gps_points=dxf_result["gps_points"],
    base_map=base_map if base_map else "일반지도",
    zoom_start=st.session_state.map_zoom,
    locate_on_start=_locate_auto,
    visible_layers=st.session_state.map_layers,
    legend_layer_name=st.session_state.get("last_checked_layer"),
    force_center_id=st.session_state.map_force_center_id
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
# ⭐️ 브라우저 localStorage를 활용한 완벽한 상태유지 지도 렌더링 (깜빡임/튕김 원천차단) ⭐️
components.html(vworld_map._repr_html_(), width=1200, height=750)

if dxf_result['num_vertices'] > 0:
    st.success(f"✅ 구역계 {dxf_result['num_vertices']}개의 꼭짓점이 지도 위에 빨간선으로 매핑되었습니다.")

# ============================
# 분석(편입 필지 및 속성 조서) 실행부
# ============================
if not uploaded_file:
    st.stop()

if st.session_state.get("do_status_analysis"):
    st.session_state.do_status_analysis = False # 1회성 플래그 (리런 방지용)
    
    st.subheader("📋 대상지 조서/면적 분석 (Pnu 추출)")
    with st.spinner("🔍 대상지 내 편입 필지를 찾는 중..."):
        try:
            pnu_list = extract_pnu_list(dxf_result["polygon"], VWORLD_KEY)
            st.session_state.pnu_list = pnu_list
        except Exception as e:
            st.error(f"❌ PNU 오류: {e}")

    if pnu_list:
        st.subheader("📊 자동 현황 분석 결과")
        all_sheets = {}
        
        for analyzer in selected_analyzers:
            with st.spinner(f"🔄 [{analyzer.name}] 통계/산출 중... ({len(pnu_list)}건)"):
                try:
                    results = analyzer.analyze(pnu_list, VWORLD_KEY)
                    all_sheets[analyzer.name] = results
                except Exception as e:
                    st.error(f"❌ [{analyzer.name}] 실패: {e}")
        
        st.session_state.all_sheets = all_sheets

# 결과 렌더링
if st.session_state.get("pnu_list"):
    st.subheader("📋 대상지 조서/면적 분석 (Pnu 추출)")
    with st.expander(f"편입 필지 구조 ({len(st.session_state.pnu_list)}건)", expanded=False):
        st.dataframe(st.session_state.pnu_list, use_container_width=True)

if st.session_state.get("all_sheets"):
    st.subheader("📊 자동 현황 분석 결과")
    for sheet_name, results in st.session_state.all_sheets.items():
        with st.expander(f"✅ {sheet_name}", expanded=False):
            st.dataframe(results, use_container_width=True)

    st.divider()
    excel_bytes = create_multi_sheet_excel(st.session_state.all_sheets)
    st.download_button(
        "📥 [최종 산출물] 현황분석 엑셀 리포트 일괄 다운로드",
        data=excel_bytes,
        file_name="현황분석조서.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )