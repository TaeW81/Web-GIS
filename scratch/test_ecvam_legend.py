import requests

key = 'GGDM-AU7W-FRD0-UPSC'
layer = 'nem_ecvam'

# Variants to try
variants = [
    # Original
    f"https://ecvam.neins.go.kr/apicall.do?APIKEY={key}&SERVICE=WMS&REQUEST=GetLegendGraphic&FORMAT=image/png&LAYER={layer}&VERSION=1.1.0",
    # LAYERS instead of LAYER
    f"https://ecvam.neins.go.kr/apicall.do?APIKEY={key}&SERVICE=WMS&REQUEST=GetLegendGraphic&FORMAT=image/png&LAYERS={layer}&VERSION=1.1.0",
    # Without version
    f"https://ecvam.neins.go.kr/apicall.do?APIKEY={key}&SERVICE=WMS&REQUEST=GetLegendGraphic&FORMAT=image/png&LAYER={layer}",
    # Different request name case
    f"https://ecvam.neins.go.kr/apicall.do?APIKEY={key}&service=WMS&request=GetLegendGraphic&format=image/png&layer={layer}&version=1.1.0",
    # With style
    f"https://ecvam.neins.go.kr/apicall.do?APIKEY={key}&SERVICE=WMS&REQUEST=GetLegendGraphic&FORMAT=image/png&LAYER={layer}&STYLE=default",
]

for i, url in enumerate(variants):
    try:
        res = requests.get(url, timeout=5, verify=False)
        print(f"Variant {i}: Status {res.status_code}, Content-Type {res.headers.get('Content-Type')}, Length {len(res.content)}")
        if res.status_code == 200 and 'image' in res.headers.get('Content-Type', ''):
            print(f"  -> SUCCESS: {url}")
        else:
            print(f"  -> FAILED: {res.text[:100]}")
    except Exception as e:
        print(f"Variant {i}: Error {e}")
