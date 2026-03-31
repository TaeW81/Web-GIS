import folium
from config import VWORLD_KEY, VWORLD_TILE_URLS, VWORLD_WMS_URL, VWORLD_WMS_CATEGORIES

def create_map(center, gps_points, base_map="일반지도", zoom_start=16):
    """
    VWorld 배경지도 위에 구역계 및 여러 레이어를 표시하는 네이티브 기반(JS문법 오류 원천차단)의 매우 견고한 지도를 만듭니다.
    
    Args:
        center (tuple): 지도 중심점 (lat, lon)
        gps_points (list): 구역계 좌표 리스트 [(lat, lon), ...]
        base_map (str): 배경지도 종류
        zoom_start (int): 초기 줌 레벨
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
    
    # 3. 파이썬 문법만을 사용한 안전한 브이월드 WMS 레이어 9종 추가
    for cat_name, layers in VWORLD_WMS_CATEGORIES.items():
        for layer_name, code in layers.items():
            # 사용자의 편의를 위해 '지적도' 하나만 기본으로 켜두고 나머지는 끈 상태로 로드합니다.
            is_show = (layer_name == "지적도")
            
            folium.WmsTileLayer(
                url=f"{VWORLD_WMS_URL}?key={VWORLD_KEY}&domain=http://localhost",
                layers=code.lower(),
                fmt='image/png',
                transparent=True,
                version='1.3.0',
                name=f"{layer_name}", # 지도 컨트롤러에 보일 예쁜 이름
                show=is_show,
                overlay=True,
                control=True
            ).add_to(m)
            
    # 4. 지도 우측 상단에 겹겹이 아이콘 (레이어 토글 메뉴 박스)을 평소에 접어둡니다 (collapsed=True)
    folium.LayerControl(position='topright', collapsed=True).add_to(m)
    
    return m
