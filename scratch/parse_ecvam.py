import requests

key = 'GGDM-AU7W-FRD0-UPSC'
base_url = 'https://ecvam.neins.go.kr/apicall.do'

# 브라우저에서 실제로 사용하는 방식 시뮬레이션
# OL TileWMS는 url + params를 조합하여 아래 형식의 URL을 호출함:
# https://ecvam.neins.go.kr/apicall.do?LAYERS=nem_ecvam&VERSION=1.1.0&SERVICE=WMS&REQUEST=GetMap&...
# 그런데 APIKEY는 tileLoadFunction을 통해 다른 방식으로 전달

# 시도 1: Referer 헤더로 도메인 전달
print("=== Test: Referer + APIKEY param ===")
headers = {
    'Referer': f'https://ecvam.neins.go.kr/apiConfirm.do?APIKEY={key}',
    'Origin': 'https://ecvam.neins.go.kr',
}
r1 = requests.get(base_url, params={
    'SERVICE': 'WMS',
    'VERSION': '1.1.0',
    'REQUEST': 'GetMap',
    'LAYERS': 'nem_ecvam',
    'BBOX': '920000,1920000,960000,1960000',
    'SRS': 'EPSG:5179',
    'WIDTH': '256',
    'HEIGHT': '256',
    'FORMAT': 'image/png',
    'TRANSPARENT': 'TRUE',
    'APIKEY': key,
}, headers=headers, timeout=15, verify=False)
print(f'Status: {r1.status_code}, CT: {r1.headers.get("content-type","")}, Len: {len(r1.content)}')
if len(r1.content) > 100:
    with open('scratch/ecvam_test1.png', 'wb') as f:
        f.write(r1.content)
    print(f'-> 성공! {len(r1.content)} bytes, ecvam_test1.png 저장')
print()

# 시도 2: 세션으로 먼저 API 확인 페이지 방문 후 WMS 호출
print("=== Test: Session-based ===")
session = requests.Session()
session.verify = False
# 먼저 API 확인 페이지 방문하여 쿠키 획득
session.get(f'https://ecvam.neins.go.kr/apiConfirm.do?APIKEY={key}', timeout=15)
print(f'Cookies: {dict(session.cookies)}')

r2 = session.get(base_url, params={
    'SERVICE': 'WMS',
    'VERSION': '1.1.0',
    'REQUEST': 'GetMap',
    'LAYERS': 'nem_ecvam',
    'BBOX': '920000,1920000,960000,1960000',
    'SRS': 'EPSG:5179',
    'WIDTH': '256',
    'HEIGHT': '256',
    'FORMAT': 'image/png',
    'TRANSPARENT': 'TRUE',
}, timeout=15)
print(f'Status: {r2.status_code}, CT: {r2.headers.get("content-type","")}, Len: {len(r2.content)}')
if len(r2.content) > 100:
    with open('scratch/ecvam_test2.png', 'wb') as f:
        f.write(r2.content)
    print(f'-> 성공! {len(r2.content)} bytes, ecvam_test2.png 저장')
print()

# 시도 3: DOMAIN 파라미터와 함께
print("=== Test: With DOMAIN param ===")
r3 = requests.get(base_url, params={
    'SERVICE': 'WMS',
    'VERSION': '1.1.0',
    'REQUEST': 'GetMap',
    'LAYERS': 'nem_ecvam',
    'BBOX': '920000,1920000,960000,1960000',
    'SRS': 'EPSG:5179',
    'WIDTH': '256',
    'HEIGHT': '256',
    'FORMAT': 'image/png',
    'TRANSPARENT': 'TRUE',
    'APIKEY': key,
    'DOMAIN': 'http://localhost',
}, timeout=15, verify=False)
print(f'Status: {r3.status_code}, CT: {r3.headers.get("content-type","")}, Len: {len(r3.content)}')
if len(r3.content) > 100:
    with open('scratch/ecvam_test3.png', 'wb') as f:
        f.write(r3.content)
    print(f'-> 성공! {len(r3.content)} bytes, ecvam_test3.png 저장')
print()

# 시도 4: WFS 호출 - 세션 사용
print("=== Test: WFS via session ===")
r4 = session.get(base_url, params={
    'SERVICE': 'WFS',
    'VERSION': '1.1.0',
    'REQUEST': 'GetFeature',
    'TYPENAME': 'nem_ecvam',
    'BBOX': '920000,1920000,960000,1960000',
    'SRSNAME': 'EPSG:5179',
    'OUTPUTFORMAT': 'application/json',
    'MAXFEATURES': '3',
}, timeout=15)
print(f'Status: {r4.status_code}, CT: {r4.headers.get("content-type","")}, Len: {len(r4.content)}')
if r4.status_code == 200 and len(r4.text) > 50:
    print(r4.text[:500])
