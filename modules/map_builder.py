import folium
from folium.plugins import GroupedLayerControl, LocateControl
from config import (VWORLD_KEY, VWORLD_TILE_URLS, VWORLD_WMS_URL, VWORLD_WMS_CATEGORIES, VWORLD_LEGEND_URL,
                     MAP_SOURCES, NIE_KEY, NIE_WMS_URL, NIE_LEGEND_URL,
                     ECVAM_KEY, ECVAM_WMS_URL, ECVAM_LEGEND_URL)


def create_map(center, gps_points, base_map="일반지도", zoom_start=16, locate_on_start=False, visible_layers=None, legend_layer_name=None, force_center_id=1):
    """
    VWorld 배경지도 위에 구역계 및 여러 레이어를 표시하는 지도를 만듭니다.
    - 사이드바 설정값에 동기화되어 필요한 WMS 항목만 렌더링
    - 사용자 현위치 자동 탐색(locate_on_start=True 일 때만)
    """
    # 1. 최하단 기본 베이스 지도
    tile_url = VWORLD_TILE_URLS.get(base_map, VWORLD_TILE_URLS["일반지도"])
    m = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles=tile_url,
        attr="브이월드",
    )

    # 2. 구역계 범위 폴리곤 그리기
    if gps_points:
        folium.Polygon(
            locations=gps_points,
            color="red",
            weight=3,
            fill=True,
            fill_color="red",
            fill_opacity=0.15,
            popup="선택 대상지",
            name="📍 내 구역계 (Polygon)"
        ).add_to(m)

    # [현위치 찾기] 사용자 현재 위치 탐색 위젯
    LocateControl(
        position="topleft",
        strings={"title": "내 위치로 이동"},
        auto_start=locate_on_start,
        locateOptions={"enableHighAccuracy": True, "maxZoom": 16}
    ).add_to(m)

    # 3. 기관별 WMS 주제도 레이어 추가 (선택된 것만 보이도록 처리)
    for source_name, categories in MAP_SOURCES.items():
        # 소스별 WMS 기본 설정
        if source_name == "국립생태원 (NIE)":
            base_url = NIE_WMS_URL
            # srs/crs는 Folium(Leaflet)이 지도의 좌표계에 맞춰 자동으로 추가하므로 생략합니다.
            extra_params = f"?ServiceKey={NIE_KEY}"
            wms_version = '1.1.1'
        elif source_name == "국토환경성평가 (ECVAM)":
            base_url = ECVAM_WMS_URL
            extra_params = f"?APIKEY={ECVAM_KEY}"
            wms_version = '1.1.0'
        elif source_name == "추후 추가 예정":
            continue  # "READY" 레이어만 있으므로 스킵
        else: # 브이월드 기본 (국토정보플랫폼 포함)
            base_url = VWORLD_WMS_URL
            extra_params = f"?key={VWORLD_KEY}&domain=http://localhost"
            wms_version = '1.3.0'

        for cat_name, layers in categories.items():
            for layer_name, code in layers.items():
                if visible_layers is not None:
                    is_show = layer_name in visible_layers
                else:
                    is_show = (layer_name == "연속지적도") or (layer_name == "지적도")

                # "READY" 가 포함된 준비중인 레이어는 스킵
                if "READY" in str(code):
                    continue

                # 레이어 코드: ECVAM은 원본 유지, NIE도 원본 유지, VWorld는 소문자
                if source_name in ("국립생태원 (NIE)", "국토환경성평가 (ECVAM)"):
                    layer_code = code
                else:
                    layer_code = code.lower()

                wms_layer = folium.WmsTileLayer(
                    url=f"{base_url}{extra_params}",
                    layers=layer_code,
                    fmt='image/png',
                    transparent=True,
                    version=wms_version,
                    name=f"{layer_name}",
                    show=is_show,
                    overlay=True,
                    control=False
                )
                wms_layer.add_to(m)

    # 선택된 모든 레이어에 대해 범례 수집 (중복 제거 및 유효성 검사)
    legend_items = []
    if visible_layers:
        for layer_name in visible_layers:
            legend_code = None
            source_found = None
            
            # MAP_SOURCES에서 해당 레이어의 출처와 코드 찾기
            for s_name, categories in MAP_SOURCES.items():
                for cat_name, layers in categories.items():
                    if layer_name in layers:
                        legend_code = layers[layer_name]
                        source_found = s_name
                        break
                if source_found: break
            
            if legend_code and not "READY" in str(legend_code):
                # 지적도와 같이 너무 뻔한 기본 레이어는 범례 목록에서 제외 (UI 깔끔하게 유지)
                if layer_name in ["지적도", "연속지적도", "광역시도", "시군구", "읍면동", "리"]:
                    continue
                
                # 콤마로 구분된 여러 코드가 있을 경우 첫 번째 코드 사용
                primary_code = str(legend_code).split(',')[0].strip()
                
                if source_found == "국립생태원 (NIE)":
                    url = NIE_LEGEND_URL.format(base_url=NIE_WMS_URL, key=NIE_KEY, layer=primary_code)
                    legend_items.append({"name": layer_name, "url": url, "type": "image"})
                elif source_found == "국토환경성평가 (ECVAM)":
                    # ECVAM은 WMS GetLegendGraphic을 지원하지 않는 경우가 많아 직접 HTML로 구현
                    if primary_code.startswith("nem_"):
                        legend_items.append({"name": layer_name, "type": "ecvam_grade"})
                    else:
                        url = ECVAM_LEGEND_URL.format(key=ECVAM_KEY, layer=primary_code)
                        legend_items.append({"name": layer_name, "url": url, "type": "image"})
                else:
                    url = VWORLD_LEGEND_URL.format(key=VWORLD_KEY, layer=primary_code.lower())
                    legend_items.append({"name": layer_name, "url": url, "type": "image"})

    # 범례 UI 생성
    if legend_items:
        items_html = ""
        for item in legend_items:
            items_html += f"""
            <div style="margin-bottom: 12px; border-bottom: 1px solid #edf2f7; padding-bottom: 8px;">
                <p style="margin: 0 0 6px 0; font-weight: 600; font-size: 12px; color: #4a5568;">● {item['name']}</p>
            """
            
            if item["type"] == "ecvam_grade":
                # ECVAM 1-5등급 커스텀 범례 UI
                grades = [
                    ("1등급", "#348821"), ("2등급", "#B0D133"), ("3등급", "#F9EF1B"),
                    ("4등급", "#F29422"), ("5등급", "#E31E24"), ("평가외", "#A5A5A5")
                ]
                items_html += '<div style="display: flex; flex-wrap: wrap; gap: 4px; padding: 4px;">'
                for g_name, g_color in grades:
                    items_html += f"""
                    <div style="display: flex; align-items: center; margin-right: 8px; margin-bottom: 2px;">
                        <div style="width: 12px; height: 12px; background-color: {g_color}; border: 1px solid #999; margin-right: 4px;"></div>
                        <span style="font-size: 11px; color: #666;">{g_name}</span>
                    </div>
                    """
                items_html += '</div>'
            else:
                items_html += f'<img src="{item["url"]}" alt="{item["name"]} 범례" style="max-width: 240px; display: block; border-radius: 4px;" onerror="this.style.display=\'none\';">'
            
            items_html += "</div>"
        
        legend_html = f"""
        <div id="map-legend-container" style="
            position: absolute; 
            bottom: 30px; 
            right: 10px; 
            z-index: 9999; 
            background: rgba(255, 255, 255, 0.92); 
            padding: 12px; 
            border-radius: 12px; 
            box-shadow: 0 10px 25px rgba(0,0,0,0.1); 
            max-height: 500px; 
            width: 270px;
            overflow-y: auto;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.4);
            font-family: 'Pretendard', 'Malgun Gothic', sans-serif;
            scrollbar-width: thin;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 2px solid #3182ce; padding-bottom: 6px;">
                <span style="font-weight: 700; font-size: 14px; color: #2d3748;">📋 선택 레이어 범례</span>
                <button onclick="document.getElementById('map-legend-container').style.display='none'" style="border:none; background:none; cursor:pointer; font-size:18px; color:#a0aec0;">&times;</button>
            </div>
            {items_html}
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

    # 기본 베이스맵(배경)용 컨트롤러
    folium.LayerControl(position='bottomright', collapsed=True).add_to(m)

    # ⭐️ 브라우저 localStorage를 활용한 완벽한 상태유지 스크립트 ⭐️
    sync_js = f"""
    <script>
    window.addEventListener('load', function() {{
        setTimeout(function() {{
            var mapId = Object.keys(window).find(key => key.startsWith('map_') && window[key] instanceof L.Map);
            if(mapId) {{
                var map = window[mapId];
                var move_id = "{force_center_id}";
                var last_move_id = localStorage.getItem('khgis_move_id');
                
                if (move_id !== last_move_id) {{
                    // 파이썬 측에서 새 위치(검색, 파일업로드)로 갱신 명령을 내림
                    localStorage.setItem('khgis_move_id', move_id);
                    localStorage.removeItem('khgis_center');
                    localStorage.removeItem('khgis_zoom');
                }} else {{
                    // 사용자의 이전 위치 복원 (단순 레이어 변경 등으로 iframe 리로드 시)
                    var sc = localStorage.getItem('khgis_center');
                    var sz = localStorage.getItem('khgis_zoom');
                    if (sc && sz) {{
                        map.setView(JSON.parse(sc), parseInt(sz), {{animate: false}});
                    }}
                }}

                // 지도가 움직일 때마다 백그라운드 저장
                map.on('moveend', function() {{
                    localStorage.setItem('khgis_center', JSON.stringify(map.getCenter()));
                    localStorage.setItem('khgis_zoom', map.getZoom());
                }});
            }}
        }}, 50); // 안전하게 L.Map 인스턴스가 윈도우에 바인딩 될 시간 확보
    }});
    </script>
    """
    m.get_root().html.add_child(folium.Element(sync_js))

    return m

def create_thematic_map(boundary_polygon, land_data, category="소유자"):
    """보고서 삽입용 테마 지도 생성 (WMS 위성배경 + 필지 테마)"""
    import matplotlib.pyplot as plt
    import io
    import requests
    from PIL import Image
    from matplotlib.font_manager import FontProperties
    from matplotlib.patches import Patch
    from config import VWORLD_KEY, VWORLD_DOMAIN
    
    try:
        plt.rcParams['font.family'] = 'Malgun Gothic'
        plt.rcParams['axes.unicode_minus'] = False
        font_prop = FontProperties(fname="C:/Windows/Fonts/malgun.ttf")
        
        # 1. 지도 영역 계산 (WGS84)
        min_x, min_y, max_x, max_y = boundary_polygon.bounds
        width = max_x - min_x
        height = max_y - min_y
        # 여백 추가 (15%)
        exp_min_x = min_x - width * 0.15
        exp_max_x = max_x + width * 0.15
        exp_min_y = min_y - height * 0.15
        exp_max_y = max_y + height * 0.15
        
        # 2. WMS 위성배경지도 가져오기 (정밀도 보장)
        wms_url = "http://api.vworld.kr/req/wms"
        params = {
            "key": VWORLD_KEY, "domain": VWORLD_DOMAIN,
            "service": "WMS", "request": "GetMap", "layers": "Satellite",
            "crs": "EPSG:4326", "format": "image/png", "width": "1000", "height": "1000",
            "bbox": f"{exp_min_x},{exp_min_y},{exp_max_x},{exp_max_y}"
        }
        res = requests.get(wms_url, params=params, timeout=15)
        bg_img = Image.open(io.BytesIO(res.content))
        
        # 3. 플롯 설정
        fig, ax = plt.subplots(figsize=(10, 10))
        
        # 배경 이미지 표시
        ax.imshow(bg_img, extent=[exp_min_x, exp_max_x, exp_min_y, exp_max_y], origin='upper')
        
        # 4. 색상 맵 설정
        unique_cats = sorted(list(set([str(p.get("analysis_attr", {}).get(category, "기타")) for p in land_data])))
        colors = plt.cm.get_cmap('Set3' if len(unique_cats) <= 12 else 'tab20').colors
        cat_color_map = {cat: colors[i % len(colors)] for i, cat in enumerate(unique_cats)}

        # 5. 필지 그리기 (WGS84 기준 그대로 사용)
        for p in land_data:
            poly = p.get("지적도형")
            if not poly: continue
            cat_val = str(p.get("analysis_attr", {}).get(category, "기타"))
            color = cat_color_map.get(cat_val, "gray")
            
            for sub_poly in ([poly] if poly.geom_type == 'Polygon' else poly.geoms):
                x, y = sub_poly.exterior.xy
                ax.fill(x, y, color=color, alpha=0.5, edgecolor='white', lw=0.5, zorder=5)

        # 6. 구역계 강조
        for sub_poly in ([boundary_polygon] if boundary_polygon.geom_type == 'Polygon' else boundary_polygon.geoms):
            bx, by = sub_poly.exterior.xy
            ax.plot(bx, by, color='red', lw=2.5, zorder=10)

        # 7. 범례 (디자인 개선)
        legend_elements = [Patch(facecolor=cat_color_map[cat], label=cat, alpha=0.8) for cat in unique_cats]
        leg = ax.legend(handles=legend_elements, loc='lower right', prop=font_prop, fontsize=10, 
                        frameon=True, facecolor='white', framealpha=0.9, edgecolor='gray')
        leg.set_title(f"[{category}별 현황]", prop=font_prop)
        
        ax.set_xlim(exp_min_x, exp_max_x)
        ax.set_ylim(exp_min_y, exp_max_y)
        ax.set_aspect('equal')
        ax.axis('off')
        
        # 8. 최종 결과 반환
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', pad_inches=0.05)
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"테마 지도 생성 오류: {e}")
        return None
