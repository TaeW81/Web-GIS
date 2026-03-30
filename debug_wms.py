import folium
import os
from folium import plugins

VWORLD_KEY = "F9BD8BC9-6646-3DD4-AA3C-C80E6D45BFB1"
VWORLD_WMS_URL = "http://api.vworld.kr/req/wms"

m = folium.Map(location=[37.5665, 126.9780], zoom_start=13)

# Add standard WMS
folium.WmsTileLayer(
    url=f"{VWORLD_WMS_URL}",
    layers="lt_c_uq111", # 도시지역
    styles="lt_c_uq111",
    fmt="image/png",
    transparent=True,
    name="도시지역",
    key=VWORLD_KEY,
    domain="http://localhost",
).add_to(m)

folium.LayerControl().add_to(m)
m.save("map_test.html")
print("Saved to map_test.html")
