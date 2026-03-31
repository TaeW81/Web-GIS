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

from config import VWORLD_KEY, VWORLD_TILE_URLS, VWORLD_WMS_CATEGORIES, KOREA_CRS, KOREA_CRS_ORIGINS, VWORLD_WFS_LAYERS
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

# ============================
# 데이터 변수 및 상태 초기화
# ============================
DEFAULT_CENTER = [37.39293, 126.97286]  # 성지스타위드
for k, v in [('map_center', DEFAULT_CENTER), ('map_zoom', 16), ('last_uploaded_file', None), 
             ('last_crs_origin', "중부"), ('last_crs_cat', "GRS80(현행)"), ('last_epsg', ""),
             ('render_center', DEFAULT_CENTER), ('render_zoom', 16), ('last_base_map', "일반지도")]:
    if k not in st.session_state:
        st.session_state[k] = v

dxf_result = {"center": st.session_state.map_center, "gps_points": [], "num_vertices": 0, "polygon": None}

# ============================
# 사이드바 (모든 조작 기능 통합)
# ============================
with st.sidebar:
    # 📡 건화(KH) 공식 브랜딩 섹션
    st.image("assets/kunhwa_logo.png", use_container_width=True)
    st.markdown("#### 📡 KH-GIS LandScan")
    st.markdown("<p style='font-size: 0.8rem; color: gray; margin-bottom: 20px;'>Smart Analysis Platform</p>", unsafe_allow_html=True)
    
    st.divider() # 시각적 구분선 추가
    
    st.header("⚙️ 설정")
    
    st.subheader("🔍 지도 이동 (장소 검색)")
    col1, col2 = st.columns([3, 1])
    search_query = col1.text_input("검색어 입력", label_visibility="collapsed", placeholder="예: 평촌역")
    if col2.button("이동", use_container_width=True):
        if search_query:
            with st.spinner("검색 중..."):
                place_result = search_place(search_query, VWORLD_KEY)
                if place_result:
                    st.session_state.map_center = [place_result['lat'], place_result['lon']]
                    st.session_state.map_zoom = 15
                    st.session_state.render_center = [place_result['lat'], place_result['lon']]
                    st.session_state.render_zoom = 15
                    st.session_state.search_marker = place_result  # 마커 정보 저장
                    st.success(f"✅ '{place_result['name']}'(으)로 이동했습니다.")
                else:
                    st.error("❌ 검색 결과를 찾을 수 없습니다.")

    st.markdown("---")
    
    st.subheader("1️⃣ 구역계 범위 업로드")
    uploaded_file = st.file_uploader("구역계 파일(.dxf)을 올려주세요", type=["dxf"])
    is_new_file = False
    if uploaded_file and st.session_state.get('last_uploaded_file') != uploaded_file.name:
        is_new_file = True
        st.session_state.last_uploaded_file = uploaded_file.name
    
    st.subheader("🌐 도면 좌표계")
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
            st.session_state.render_center = [lat, lon]
            st.session_state.map_zoom = 10 
            st.session_state.render_zoom = 10
            dxf_result["center"] = [lat, lon]

    st.subheader("📊 현황 조서 분석 항목")
    all_analyzers = get_all_analyzers()
    selected_analyzers = [a for a in all_analyzers if st.checkbox(a.name, value=True, help=a.description)]

    st.markdown("---")
    st.subheader("📥 배경 공간정보(SHP/DXF) 추출")
    
    dl_crs_options = {
        "GRS80 중부 (EPSG:5186)": "EPSG:5186", "GRS80 서부 (EPSG:5185)": "EPSG:5185",
        "GRS80 동부 (EPSG:5187)": "EPSG:5187", "GRS80 동해 (EPSG:5188)": "EPSG:5188",
        "UTMK (EPSG:5179)": "EPSG:5179", "Bessel 중부 (EPSG:5174)": "EPSG:5174", "WGS84 (EPSG:4326)": "EPSG:4326",
    }
    dl_crs_label = st.selectbox("다운로드 좌표계", options=list(dl_crs_options.keys()), index=0)
    st.session_state.dl_target_epsg = dl_crs_options[dl_crs_label]
    
    dl_layer_name = st.selectbox("추출 대상 레이어 (WFS)", options=list(VWORLD_WFS_LAYERS.keys()), index=0)

    # 버튼 하나로 일괄 처리 (JS 개입 X)
    if st.button("🚀 선택 구역 도면 추출하기", type="primary", use_container_width=True):
        if not uploaded_file:
            st.warning("⚠️ 왼쪽 위에서 DXF 구역계를 먼저 업로드해야 해당 위치를 추출할 수 있습니다.")
        else:
            st.session_state.do_wfs_download = True
            st.session_state.dl_req_layer = dl_layer_name
            # 새로운 추출 시 기존 로드된 다운로드 버튼 클리어
            if "dl_result_bytes" in st.session_state:
                del st.session_state["dl_result_bytes"]

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
                st.session_state.render_center = dxf_result["center"]
                st.session_state.render_zoom = 16
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
    req_layer = st.session_state.dl_req_layer
    
    # BBOX를 앱 내에서 직접 계산 (VWorld WFS 1.1.0은 BBOX로 minLat, minLon, maxLat, maxLon 순서를 요구함)
    lons = [p[1] for p in dxf_result["gps_points"]]
    lats = [p[0] for p in dxf_result["gps_points"]]
    dl_bbox = f"{min(lats)-0.003},{min(lons)-0.005},{max(lats)+0.003},{max(lons)+0.005}"
    
    with st.spinner(f"📥 '{req_layer}' 대용량 데이터를 격자 분할 병합 방식으로 가져오는 중입니다. 다소 시간이 걸릴 수 있습니다..."):
        try:
            result = fetch_wfs_data(req_layer, dl_bbox, VWORLD_KEY)
            geojson_data = result["geojson"]
            feat_count = result["count"]
            
            if feat_count == 0:
                st.warning(f"⚠️ 현재 대상지 반경에 '{req_layer}' 대상물이 존재하지 않습니다.")
                if "dl_result_bytes" in st.session_state:
                    del st.session_state["dl_result_bytes"]
            else:
                dl_target_epsg = st.session_state.dl_target_epsg
                boundary_pts = dxf_result.get("lonlat_points", None)
                
                # 메모리에 산출물 생성 후 세션에 물리적으로 저장 (리런 시에도 유지되게 만듦)
                st.session_state.dl_result_bytes = {
                    "layer": req_layer,
                    "count": feat_count,
                    "dxf": export_to_dxf(geojson_data, req_layer, dl_target_epsg, boundary_pts),
                    "shp": export_to_shp(geojson_data, req_layer, dl_target_epsg, boundary_pts)
                }
        except Exception as e:
            st.error(f"❌ 추출 실패: {e}")

# 캐시된 다운로드 파일이 세션에 존재하면, 리런 되어도 다운로드 버튼이 계속 떠 있도록 보장
if st.session_state.get("dl_result_bytes"):
    dl_data = st.session_state.dl_result_bytes
    st.success(f"🎉 성공적으로 모든 데이터({dl_data['count']}건)를 추출 및 병합 완료했습니다!")
    colA, colB = st.columns(2)
    colA.download_button(f"💾 {dl_data['layer']} (.dxf)", dl_data['dxf'], f"{dl_data['layer']}.dxf", "application/dxf")
    colB.download_button(f"💾 {dl_data['layer']} (.shp)", dl_data['shp'], f"{dl_data['layer']}.zip", "application/zip")


# ============================
# VWorld 지도 렌더링 
# ============================
st.subheader("📍 대상지 위치도")

base_map_options = list(VWORLD_TILE_URLS.keys())
base_map = st.radio("맵 레이아웃(배경)", options=base_map_options, horizontal=True, label_visibility="collapsed")

if base_map != st.session_state.last_base_map:
    st.session_state.last_base_map = base_map
    st.session_state.render_center = st.session_state.map_center
    st.session_state.render_zoom = st.session_state.map_zoom

# 지도 빌드 — DXF 미업로드 + 검색 미사용 상태에서만 현위치 자동 찾기
_locate_auto = (not uploaded_file) and (not st.session_state.get("search_marker"))
vworld_map = create_map(
    center=st.session_state.render_center,
    gps_points=dxf_result["gps_points"],
    base_map=base_map if base_map else "일반지도",
    zoom_start=st.session_state.render_zoom,
    locate_on_start=_locate_auto
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
# ⭐️ 해상도를 1200x750으로 유지하며 아코디언 메뉴 등 커스텀 자바스크립트가 작동하도록 순수 HTML 렌더링 ⭐️
components.html(vworld_map._repr_html_(), width=1200, height=750)

if dxf_result['num_vertices'] > 0:
    st.success(f"✅ 구역계 {dxf_result['num_vertices']}개의 꼭짓점이 지도 위에 빨간선으로 매핑되었습니다.")

# ============================
# 분석(편입 필지 및 속성 조서) 실행부
# ============================
if not uploaded_file:
    st.stop()

st.subheader("📋 대상지 조서/면적 분석 (Pnu 추출)")
with st.spinner("🔍 대상지 내 편입 필지를 찾는 중..."):
    try:
        pnu_list = extract_pnu_list(dxf_result["polygon"], VWORLD_KEY)
    except Exception as e:
        st.error(f"❌ PNU 오류: {e}")
        st.stop()

if not pnu_list:
    st.warning("⚠️ 편입되는 필지를 찾지 못했습니다.")
    st.stop()

with st.expander(f"편입 필지 구조 ({len(pnu_list)}건)", expanded=False):
    st.dataframe(pnu_list, use_container_width=True)

if not selected_analyzers:
    st.stop()

st.subheader("📊 자동 현황 분석 결과")
all_sheets = {}

for analyzer in selected_analyzers:
    with st.spinner(f"🔄 [{analyzer.name}] 통계/산출 중... ({len(pnu_list)}건)"):
        try:
            results = analyzer.analyze(pnu_list, VWORLD_KEY)
            all_sheets[analyzer.name] = results
            with st.expander(f"✅ {analyzer.name}", expanded=False):
                st.dataframe(results, use_container_width=True)
        except Exception as e:
            st.error(f"❌ [{analyzer.name}] 실패: {e}")

if all_sheets:
    st.divider()
    excel_bytes = create_multi_sheet_excel(all_sheets)
    st.download_button(
        "📥 [최종 산출물] 현황분석 엑셀 리포트 일괄 다운로드",
        data=excel_bytes,
        file_name="현황분석조서.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )