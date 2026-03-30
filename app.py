"""
🗺️ Web-GIS 기반 현황분석 자동화 플랫폼
메인 Streamlit 애플리케이션

파이프라인:
  DXF 업로드 → 좌표변환 → VWorld 지도 표시 → PNU 추출 → 분석 실행 → 엑셀 다운로드
"""
import streamlit as st
from streamlit_folium import st_folium
import tempfile
import os

# === 프로젝트 모듈 임포트 ===
from config import VWORLD_KEY, VWORLD_TILE_URLS, VWORLD_WMS_LAYERS, VWORLD_WMS_CATEGORIES, VWORLD_LEGEND_URL, KOREA_CRS, KOREA_CRS_ORIGINS, VWORLD_WFS_LAYERS
from modules.dxf_parser import parse_dxf
from modules.pnu_extractor import extract_pnu_list
from modules.map_builder import create_map
from modules.excel_exporter import create_multi_sheet_excel
from modules.spatial_downloader import fetch_wfs_data, export_to_dxf, export_to_shp
from analyzers import get_all_analyzers
import requests

# ============================
# 1. 페이지 설정
# ============================
st.set_page_config(page_title="현황분석 자동화 시스템", layout="wide")
st.title("🗺️ Web-GIS 기반 현황분석 플랫폼")
st.caption("캐드 구역계(DXF) 파일을 업로드하면, 자동으로 토지/건축물 분석 후 엑셀을 생성합니다.")

# ============================
# 3. 데이터 및 상태 초기화 (사이드바 메뉴보다 먼저 실행되어야 함)
# ============================
DEFAULT_CENTER = [37.5665, 126.9780]  # 서울시청 중심

# 세션 상태 초기화
if 'map_center' not in st.session_state:
    st.session_state.map_center = DEFAULT_CENTER
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = 16
if 'last_uploaded_file' not in st.session_state:
    st.session_state.last_uploaded_file = None
if 'last_crs_origin' not in st.session_state:
    st.session_state.last_crs_origin = "중부"
if 'last_crs_cat' not in st.session_state:
    st.session_state.last_crs_cat = "GRS80(현행)"
if 'last_epsg' not in st.session_state:
    st.session_state.last_epsg = ""

# 렌더링용 고정 좌표 (HTML 재생성으로 인한 깜빡임 방지용)
if 'render_center' not in st.session_state:
    st.session_state.render_center = st.session_state.map_center
if 'render_zoom' not in st.session_state:
    st.session_state.render_zoom = st.session_state.map_zoom
if 'last_base_map' not in st.session_state:
    st.session_state.last_base_map = "일반지도"

# 초기 데이터 구조 정의 (사이드바 및 하위 로직에서 사용됨)
dxf_result = {
    "center": st.session_state.map_center,
    "gps_points": [],
    "num_vertices": 0,
    "polygon": None
}

# ============================
# 2. 사이드바 설정
# ============================
with st.sidebar:
    st.header("⚙️ 설정")
    
    # --- 2-1. DXF 파일 업로드 ---
    st.subheader("1️⃣ 파일 업로드")
    uploaded_file = st.file_uploader("구역계 파일(.dxf)을 올려주세요", type=["dxf"])
    
    # 새로운 파일 업로드 여부 확인
    is_new_file = False
    if uploaded_file and st.session_state.get('last_uploaded_file') != uploaded_file.name:
        is_new_file = True
        st.session_state.last_uploaded_file = uploaded_file.name
    
    # --- 2-2. 도면 좌표계 선택 (사용자 요청 UI 반영) ---
    st.subheader("🌐 도면 좌표계")
    crs_cat = st.radio("분류", options=list(KOREA_CRS.keys()), horizontal=True, label_visibility="collapsed")
    crs_origin = st.radio("원점", options=list(KOREA_CRS[crs_cat].keys()), horizontal=True)
    
    # 기본 EPSG 코드 (분류/원점에 따라 자동 변경되지만 사용자가 수동 수정도 가능)
    default_epsg = KOREA_CRS[crs_cat][crs_origin]
    
    selected_epsg = st.text_input("EPSG 코드 (직접 입력 가능)", value=default_epsg)
    
    crs_changed = False
    
    if st.session_state.get('last_epsg') != selected_epsg:
        crs_changed = True
        st.session_state.last_epsg = selected_epsg
        
    # 원점이나 카테고리가 변경되었는지 확인
    if st.session_state.last_crs_origin != crs_origin or st.session_state.last_crs_cat != crs_cat:
        crs_changed = True
        st.session_state.last_crs_origin = crs_origin
        st.session_state.last_crs_cat = crs_cat
        
        # 업로드된 파일이 없을 때만 원점 위치로 지도 이동
        if not uploaded_file and crs_origin in KOREA_CRS_ORIGINS:
            lon, lat = KOREA_CRS_ORIGINS[crs_origin]
            st.session_state.map_center = [lat, lon]
            st.session_state.render_center = [lat, lon]
            st.session_state.map_zoom = 10 # 원점 확인을 위해 약간 줌 아웃
            st.session_state.render_zoom = 10
            dxf_result["center"] = [lat, lon]

    # --- 2-3. 분석 항목 선택 (이전 2-2) ---
    st.subheader("📊 분석 항목")
    all_analyzers = get_all_analyzers()
    selected_analyzers = []
    for analyzer in all_analyzers:
        if st.checkbox(analyzer.name, value=True, key=f"an_{analyzer.name}",
                       help=analyzer.description):
            selected_analyzers.append(analyzer)

    # --- 2-4. 다운로드 좌표계 선택 (별도) ---
    st.subheader("📥 다운로드 좌표계")
    dl_crs_options = {
        "GRS80 중부 (EPSG:5186)": "EPSG:5186",
        "GRS80 서부 (EPSG:5185)": "EPSG:5185",
        "GRS80 동부 (EPSG:5187)": "EPSG:5187",
        "GRS80 동해 (EPSG:5188)": "EPSG:5188",
        "UTMK (EPSG:5179)": "EPSG:5179",
        "Bessel 중부 (EPSG:5174)": "EPSG:5174",
        "WGS84 (EPSG:4326)": "EPSG:4326",
    }
    dl_crs_label = st.selectbox(
        "SHP/DXF 다운로드 시 좌표계",
        options=list(dl_crs_options.keys()),
        index=0,
        key="dl_crs_select",
    )
    st.session_state.dl_target_epsg = dl_crs_options[dl_crs_label]

    # --- 추가 WMS 레이어 선택 (삭제됨: 지도 위 오버레이로 이동) ---

# --- 3-1. DXF 파싱 및 좌표 변환 (파일 업로드 시에만 실행) ---
if uploaded_file:
    st.sidebar.success("✅ 파일 업로드 완료!")
    with st.spinner("📐 도면 좌표를 변환하는 중..."):
        try:
            # 업로드 파일을 임시 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            
            # DXF 파싱 실행 (선택된 좌표계 전달)
            dxf_result = parse_dxf(tmp_path, source_crs=selected_epsg)
            os.remove(tmp_path)  # 임시 파일 삭제

            # 새로운 파일이거나 좌표계가 변경된 경우 세션 상태를 파일의 중심점으로 초기화
            if is_new_file or crs_changed:
                st.session_state.map_center = dxf_result["center"]
                st.session_state.map_zoom = 16
                st.session_state.render_center = dxf_result["center"]
                st.session_state.render_zoom = 16
            
        except Exception as e:
            st.error(f"❌ DXF 파일 처리 오류: {e}")
            st.stop()
else:
    st.info("👈 왼쪽 사이드바에서 DXF 파일을 업로드해 주세요.")

# --- 3-2. VWorld 지도 표시 (항상 표시) ---
st.subheader("📍 대상지 위치도")

# --- JS 다운로드 브리지 (사이드바에 숨김 배치) ---
with st.sidebar:
    st.text_input("download_bridge", key="download_data", placeholder="download_layer_bbox", label_visibility="collapsed")
    st.button("__dl_trigger__", key="download_trigger_btn")
    # 사이드바 내 브리지 컴포넌트 숨김
    st.markdown("""
<style>
div[data-testid="stTextInput"]:has(input[placeholder="download_layer_bbox"]) {
    height: 0px !important; min-height: 0px !important;
    overflow: hidden !important; margin: 0 !important; padding: 0 !important;
}
</style>
""", unsafe_allow_html=True)

# --- 다운로드 요청 처리 (범용) ---
if st.session_state.get("download_trigger_btn"):
    raw_data = st.session_state.get("download_data", "")
    parts = raw_data.split("|")
    if len(parts) >= 2:
        dl_layer_name, dl_bbox = parts[0], parts[1]
        
        # 이전 상태 초기화
        st.session_state.download_dxf_bytes = None
        st.session_state.download_shp_bytes = None
        st.session_state.download_msg = ""
        st.session_state.download_msg_type = ""
        st.session_state.download_layer_label = dl_layer_name
        
        # 다운로드 좌표계 선택 UI
        dl_target_epsg = st.session_state.get("dl_target_epsg", "EPSG:5186")
        
        # 구역계 좌표 (lonlat_points)
        boundary_pts = dxf_result.get("lonlat_points", None) if dxf_result.get("num_vertices", 0) > 0 else None
        
        with st.spinner(f"📥 '{dl_layer_name}' 레이어 데이터를 가져오는 중..."):
            try:
                # WFS 데이터 조회
                result = fetch_wfs_data(dl_layer_name, dl_bbox, VWORLD_KEY)
                geojson_data = result["geojson"]
                feat_count = result["count"]
                overflow = result["overflow"]
                
                if feat_count == 0:
                    st.session_state.download_msg = f"⚠️ 현재 표시된 영역에 '{dl_layer_name}' 데이터가 없습니다."
                    st.session_state.download_msg_type = "warning"
                else:
                    # DXF 변환
                    dxf_bytes = export_to_dxf(
                        geojson_data, dl_layer_name,
                        target_epsg=dl_target_epsg,
                        boundary_points=boundary_pts,
                    )
                    # SHP 변환
                    shp_bytes = export_to_shp(
                        geojson_data, dl_layer_name,
                        target_epsg=dl_target_epsg,
                        boundary_points=boundary_pts,
                    )
                    
                    st.session_state.download_dxf_bytes = dxf_bytes
                    st.session_state.download_shp_bytes = shp_bytes
                    
                    overflow_msg = " (⚠️ 1,000건 제한에 도달 — 영역을 좁혀 재시도해 주세요)" if overflow else ""
                    st.session_state.download_msg = (
                        f"🎉 '{dl_layer_name}' {feat_count}건 변환 완료! "
                        f"(좌표계: {dl_target_epsg}){overflow_msg}"
                    )
                    st.session_state.download_msg_type = "success"
                    
            except ValueError as ve:
                st.session_state.download_msg = f"⚠️ {ve}"
                st.session_state.download_msg_type = "warning"
            except Exception as e:
                st.session_state.download_msg = f"❌ 데이터 추출 실패: {e}"
                st.session_state.download_msg_type = "error"

# 메시지 출력 처리 (지속성 확보)
msg_type = st.session_state.get("download_msg_type", "")
if msg_type:
    if msg_type == "success":
        st.success(st.session_state.download_msg)
        dl_label = st.session_state.get("download_layer_label", "데이터")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label=f"💾 {dl_label} DXF 다운로드",
                data=st.session_state.get("download_dxf_bytes", b""),
                file_name=f"{dl_label}_추출.dxf",
                mime="application/dxf",
                type="primary",
                use_container_width=True,
            )
        with dl_col2:
            st.download_button(
                label=f"💾 {dl_label} SHP 다운로드 (ZIP)",
                data=st.session_state.get("download_shp_bytes", b""),
                file_name=f"{dl_label}_추출.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True,
            )
    elif msg_type == "warning":
        st.warning(st.session_state.download_msg)
    elif msg_type == "error":
        st.error(st.session_state.download_msg)

# 배경지도 및 레이어 선택 (지도 바로 위에 버튼식으로 배치)
col1, col2 = st.columns([1, 1])

with col1:
    base_map = st.segmented_control(
        "🗺️ 배경지도 선택",
        options=list(VWORLD_TILE_URLS.keys()),
        default="일반지도",
        selection_mode="single",
    )

# 배경지도가 변경되었을 때만 렌더링 좌표를 갱신
if base_map != st.session_state.last_base_map:
    st.session_state.last_base_map = base_map
    st.session_state.render_center = st.session_state.map_center
    st.session_state.render_zoom = st.session_state.map_zoom

# 지도 생성
vworld_map = create_map(
    center=st.session_state.render_center,
    gps_points=dxf_result["gps_points"],
    base_map=base_map if base_map else "일반지도",
    zoom_start=st.session_state.render_zoom
)

# st_folium 실행 및 결과 캡처
map_data = st_folium(
    vworld_map,
    height=700,
    returned_objects=["center", "zoom"],
    use_container_width=True,
    key="vworld_map_main"
)

# 사용자가 지도를 움직였을 경우 세션 상태 업데이트
if map_data:
    if "center" in map_data and map_data["center"]:
        new_center = [map_data["center"]["lat"], map_data["center"]["lng"]]
        if round(new_center[0], 5) != round(st.session_state.map_center[0], 5):
            st.session_state.map_center = new_center
    if "zoom" in map_data and map_data["zoom"] != st.session_state.map_zoom:
        st.session_state.map_zoom = map_data["zoom"]
    if "bounds" in map_data and map_data["bounds"]:
        st.session_state.map_bounds = map_data["bounds"]

if dxf_result['num_vertices'] > 0:
    st.success(f"✅ 총 {dxf_result['num_vertices']}개의 꼭짓점이 좌표 변환되었습니다.")

# --- 3-3. PNU 추출 (파일이 업로드된 경우에만 실행) ---
if not uploaded_file:
    st.stop()

st.subheader("📋 편입 필지 추출")

with st.spinner("🔍 브이월드에서 편입 필지를 추출하는 중..."):
    try:
        pnu_list = extract_pnu_list(dxf_result["polygon"], VWORLD_KEY)
    except Exception as e:
        st.error(f"❌ PNU 추출 오류: {e}")
        st.stop()

if not pnu_list:
    st.warning("⚠️ 편입되는 필지를 찾지 못했습니다. 구역계를 확인해 주세요.")
    st.stop()

st.success(f"✅ 총 **{len(pnu_list)}**개 필지가 구역계에 편입됩니다.")

# PNU 목록 미리보기 (접기)
with st.expander(f"편입 필지 목록 ({len(pnu_list)}건)", expanded=False):
    st.dataframe(pnu_list, use_container_width=True)

# --- 3-4. 선택된 분석기 실행 ---
if not selected_analyzers:
    st.info("👈 사이드바에서 분석 항목을 하나 이상 선택해 주세요.")
    st.stop()

st.subheader("📊 분석 결과")

# 전체 시트 데이터를 모을 딕셔너리 (엑셀용)
all_sheets = {}

# 각 분석기 실행
for analyzer in selected_analyzers:
    with st.spinner(f"🔄 [{analyzer.name}] 분석 중... ({len(pnu_list)}건)"):
        try:
            results = analyzer.analyze(pnu_list, VWORLD_KEY)
            all_sheets[analyzer.name] = results
            
            # 결과를 탭 형태로 표시
            with st.expander(f"✅ {analyzer.name} ({len(results)}건)", expanded=True):
                st.dataframe(results, use_container_width=True)
        except Exception as e:
            st.error(f"❌ [{analyzer.name}] 분석 오류: {e}")

# --- 3-5. 엑셀 다운로드 ---
if all_sheets:
    st.divider()
    st.subheader("📥 결과 다운로드")
    
    excel_bytes = create_multi_sheet_excel(all_sheets)
    
    st.download_button(
        label="📥 분석 결과 엑셀 다운로드",
        data=excel_bytes,
        file_name="현황분석_자동화결과.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )