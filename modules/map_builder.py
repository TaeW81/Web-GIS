import folium
from folium.plugins import GroupedLayerControl, LocateControl
from config import VWORLD_KEY, VWORLD_TILE_URLS, VWORLD_WMS_URL, VWORLD_WMS_CATEGORIES


def create_map(center, gps_points, base_map="일반지도", zoom_start=16, locate_on_start=False):
    """
    VWorld 배경지도 위에 구역계 및 여러 레이어를 표시하는 지도를 만듭니다.
    - 아코디언(접기/펴기) 그룹 메뉴
    - 전체 열기/닫기 버튼
    - 메뉴 조작 시 마우스 휠 줌 전파 차단
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

    # 3. 브이월드 WMS 주제도 레이어를 그룹별로 묶어서 추가
    grouped_overlays = {}

    for cat_name, layers in VWORLD_WMS_CATEGORIES.items():
        grouped_overlays[cat_name] = []
        for layer_name, code in layers.items():
            is_show = (layer_name == "연속지적도") or (layer_name == "지적도")

            wms_layer = folium.WmsTileLayer(
                url=f"{VWORLD_WMS_URL}?key={VWORLD_KEY}&domain=http://localhost",
                layers=code.lower(),
                fmt='image/png',
                transparent=True,
                version='1.3.0',
                name=f"{layer_name}",
                show=is_show,
                overlay=True,
                control=False
            )
            wms_layer.add_to(m)
            grouped_overlays[cat_name].append(wms_layer)

    # 4. 지도 우측 상단에 폴더형(Grouped) 레이어 컨트롤러 렌더링
    GroupedLayerControl(
        groups=grouped_overlays,
        exclusive_groups=False,
        collapsed=False,
        position='topright'
    ).add_to(m)

    # 5. CSS: 스크롤, 아코디언 스타일, 버튼 스타일
    custom_css = """
    <style>
    .leaflet-control-layers-expanded {
        max-height: 680px !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        min-width: 220px !important;
    }
    .leaflet-control-layers-group-label {
        cursor: pointer !important;
        user-select: none;
    }
    .leaflet-control-layers-group-name {
        font-weight: bold !important;
        font-size: 13px !important;
        color: #1e293b !important;
        padding: 4px 2px !important;
        display: inline-block !important;
    }
    .leaflet-control-layers-group-label:hover .leaflet-control-layers-group-name {
        background-color: #e2e8f0 !important;
        border-radius: 3px !important;
    }
    .accordion-layer-item {
        display: none !important;
    }
    .accordion-layer-item.open {
        display: block !important;
    }
    .btn-accordion-wrap {
        text-align: center;
        padding: 8px 4px 4px 4px;
        border-top: 1px solid #e2e8f0;
        margin-top: 8px;
    }
    .btn-accordion-wrap button {
        padding: 4px 14px;
        margin: 0 3px;
        cursor: pointer;
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 4px;
        font-size: 12px;
        color: #334155;
    }
    .btn-accordion-wrap button:hover {
        background: #e2e8f0;
    }
    </style>
    """
    m.get_root().header.add_child(folium.Element(custom_css))

    # 6. JS: 아코디언 + 전체 열기/닫기 버튼 + 마우스 휠 줌 전파 차단
    #    root.script 에 삽입 → Leaflet <script> 블록 끝에 추가되어 DOM 준비 후 실행됨
    #    <script> 태그 없이 순수 JS만 넣어야 한다
    js_lines = []
    js_lines.append("var _at=setInterval(function(){")
    js_lines.append("var gs=document.querySelectorAll('.leaflet-control-layers-group');")
    js_lines.append("var chks=document.querySelectorAll('.leaflet-control-layers-selector');")
    js_lines.append("if(gs.length===0 || chks.length<10) return;")
    js_lines.append("clearInterval(_at);")
    # 중복 실행 방지
    js_lines.append("if(document.querySelector('.btn-accordion-wrap')) return;")
    # 아코디언
    js_lines.append("gs.forEach(function(g){")
    js_lines.append("var tl=g.querySelector('.leaflet-control-layers-group-label');")
    js_lines.append("var ns=tl?tl.querySelector('.leaflet-control-layers-group-name'):null;")
    js_lines.append("if(!ns)return;")
    js_lines.append("ns.setAttribute('data-orig',ns.textContent);")
    js_lines.append("ns.textContent='\u25b6 '+ns.textContent;")
    js_lines.append("var cls=g.querySelectorAll('label:not(.leaflet-control-layers-group-label)');")
    js_lines.append("cls.forEach(function(c){c.classList.add('accordion-layer-item');});")
    js_lines.append("tl.addEventListener('click',function(e){")
    js_lines.append("if(e.target.tagName==='INPUT')return;")
    js_lines.append("var op=cls[0]&&cls[0].classList.contains('open');")
    js_lines.append("cls.forEach(function(c){op?c.classList.remove('open'):c.classList.add('open');});")
    js_lines.append("ns.textContent=(op?'\u25b6 ':'\u25bc ')+ns.getAttribute('data-orig');")
    js_lines.append("});")
    js_lines.append("});")
    # 전체 열기/닫기
    js_lines.append("var ol=document.querySelector('.leaflet-control-layers-overlays');")
    js_lines.append("if(!ol)ol=document.querySelector('.leaflet-control-layers-list');")
    js_lines.append("if(ol){")
    js_lines.append("var w=document.createElement('div');w.className='btn-accordion-wrap';")
    js_lines.append("var ob=document.createElement('button');ob.textContent='\uc804\uccb4 \uc5f4\uae30';")
    js_lines.append("ob.onclick=function(e){e.preventDefault();e.stopPropagation();")
    js_lines.append("document.querySelectorAll('.accordion-layer-item').forEach(function(x){x.classList.add('open');});")
    js_lines.append("document.querySelectorAll('.leaflet-control-layers-group-name').forEach(function(x){")
    js_lines.append("x.textContent=x.textContent.replace('\u25b6','\u25bc');});};")
    js_lines.append("var cb=document.createElement('button');cb.textContent='\uc804\uccb4 \ub2eb\uae30';")
    js_lines.append("cb.onclick=function(e){e.preventDefault();e.stopPropagation();")
    js_lines.append("document.querySelectorAll('.accordion-layer-item').forEach(function(x){x.classList.remove('open');});")
    js_lines.append("document.querySelectorAll('.leaflet-control-layers-group-name').forEach(function(x){")
    js_lines.append("x.textContent=x.textContent.replace('\u25bc','\u25b6');});};")
    js_lines.append("w.appendChild(ob);w.appendChild(cb);ol.appendChild(w);")
    js_lines.append("}")
    # 마우스 휠 줌 전파 차단
    js_lines.append("var p=document.querySelector('.leaflet-control-layers');")
    js_lines.append("if(p){L.DomEvent.disableScrollPropagation(p);}")
    js_lines.append("},150);")

    accordion_js_code = "\n".join(js_lines)
    m.get_root().script.add_child(folium.Element(accordion_js_code))

    # 기본 베이스맵(배경)용 컨트롤러
    folium.LayerControl(position='bottomright', collapsed=True).add_to(m)

    return m
