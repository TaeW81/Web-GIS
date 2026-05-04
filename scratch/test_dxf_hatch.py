import sys
import os
# Add current directory to path
sys.path.append(os.getcwd())

from modules.spatial_downloader import export_to_dxf
import json

# Dummy GeoJSON for Ecology Map
geojson_data = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"eczm_grad": "1"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[127.0, 37.0], [127.01, 37.0], [127.01, 37.01], [127.0, 37.01], [127.0, 37.0]]]
            }
        },
        {
            "type": "Feature",
            "properties": {"eczm_grad": "2"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[127.02, 37.02], [127.03, 37.02], [127.03, 37.03], [127.02, 37.03], [127.02, 37.02]]]
            }
        }
    ]
}

try:
    dxf_bytes = export_to_dxf(geojson_data, "생태자연도", target_epsg="EPSG:5186")
    with open("test_ecology.dxf", "wb") as f:
        f.write(dxf_bytes)
    print("Successfully generated test_ecology.dxf")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
