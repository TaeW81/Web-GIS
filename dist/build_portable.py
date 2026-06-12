# -*- coding: utf-8 -*-
"""KH LandHub 이식형(Portable) ZIP 빌드.
내장 Python 3.11.9 + 패키지 설치 + 앱/템플릿 복사 + 런처 생성.
실행:  python dist/build_portable.py
"""
import os, sys, shutil, zipfile, subprocess, urllib.request

PYVER = "3.11.9"
DIST  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.dirname(DIST)
STAGE = os.path.join(DIST, "KH_LandHub_demo")
PY    = os.path.join(STAGE, "python")
CACHE = os.path.join(DIST, "_cache")
PYEXE = os.path.join(PY, "python.exe")

def log(m): print(f"[build] {m}", flush=True)

def download(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        log(f"캐시 사용: {os.path.basename(dest)}"); return
    log(f"다운로드: {url}")
    urllib.request.urlretrieve(url, dest)

def run(args):
    log("실행: " + " ".join(os.path.basename(a) if i==0 else a for i,a in enumerate(args)))
    r = subprocess.run(args)
    if r.returncode != 0:
        raise SystemExit(f"명령 실패(exit {r.returncode}): {args}")

# 1) 작업 폴더
log("[1/8] 작업 폴더 준비")
if os.path.exists(STAGE): shutil.rmtree(STAGE)
os.makedirs(PY, exist_ok=True); os.makedirs(CACHE, exist_ok=True)

# 2) 내장 Python
log("[2/8] 내장 Python")
embed = os.path.join(CACHE, f"python-{PYVER}-embed-amd64.zip")
download(f"https://www.python.org/ftp/python/{PYVER}/python-{PYVER}-embed-amd64.zip", embed)
with zipfile.ZipFile(embed) as z: z.extractall(PY)

# 3) site 활성화
log("[3/8] ._pth 설정")
for f in os.listdir(PY):
    if f.endswith("._pth"):
        p = os.path.join(PY, f)
        txt = open(p, encoding="ascii").read().replace("#import site", "import site")
        open(p, "w", encoding="ascii").write(txt)

# 4) pip 부트스트랩
log("[4/8] pip 부트스트랩")
getpip = os.path.join(CACHE, "get-pip.py")
download("https://bootstrap.pypa.io/get-pip.py", getpip)
run([PYEXE, getpip, "--no-warn-script-location"])

# 5) 패키지 설치
log("[5/8] 패키지 설치 (수 분 소요)")
run([PYEXE, "-m", "pip", "install", "--no-warn-script-location", "--no-cache-dir",
     "-r", os.path.join(DIST, "requirements_portable.txt")])

# 6) 앱 파일 복사
log("[6/8] 앱 파일 복사")
def ignore_pyc(d, names): return [n for n in names if n == "__pycache__"]
for it in ["modules", "report", "analyzers", "assets", "tools"]:
    s = os.path.join(ROOT, it)
    if os.path.isdir(s): shutil.copytree(s, os.path.join(STAGE, it), ignore=ignore_pyc)
for it in ["app.py", "config.py"]:
    s = os.path.join(ROOT, it)
    if os.path.isfile(s): shutil.copy2(s, STAGE)
# data (대용량 ngii_shp 제외)
for d in ["data/output", "data/project_cache", "data/sample"]:
    os.makedirs(os.path.join(STAGE, d), exist_ok=True)
cj = os.path.join(ROOT, "data", "compensation_ratio.json")
if os.path.isfile(cj): shutil.copy2(cj, os.path.join(STAGE, "data"))
sdir = os.path.join(ROOT, "data", "sample")
if os.path.isdir(sdir):
    for f in os.listdir(sdir):
        if os.path.isfile(os.path.join(sdir, f)):
            shutil.copy2(os.path.join(sdir, f), os.path.join(STAGE, "data", "sample"))
# 보고서 템플릿(연습용자료 sample 2~3종)
tdir = os.path.join(STAGE, "연습용자료"); os.makedirs(tdir, exist_ok=True)
for f in ["현황분석보고서(sample).hwpx", "01.무상귀속협의요청서(sample).hwpx", "편입산지조서(sample).xlsx"]:
    s = os.path.join(ROOT, "연습용자료", f)
    if os.path.isfile(s): shutil.copy2(s, tdir)

# 7) 설정/런처/안내문
log("[7/8] 런처/설정 생성")
os.makedirs(os.path.join(STAGE, ".streamlit"), exist_ok=True)
config_toml = (
    "[browser]\n"
    "gatherUsageStats = false\n\n"
    "[server]\n"
    "headless = false\n"
    "port = 8501\n\n"
    "[theme]\n"
    'base = "light"\n'
)
open(os.path.join(STAGE, ".streamlit", "config.toml"), "w", encoding="utf-8").write(config_toml)

bat = (
    "@echo off\r\n"
    "cd /d \"%~dp0\"\r\n"
    "echo ============================================\r\n"
    "echo   KH LandHub 데모 - 통합 토지 분석 플랫폼\r\n"
    "echo ============================================\r\n"
    "echo.\r\n"
    "echo  잠시 후 브라우저가 자동으로 열립니다.\r\n"
    "echo  안 열리면 브라우저에서 http://localhost:8501 접속\r\n"
    "echo  종료하려면 이 검은 창을 닫으세요.\r\n"
    "echo.\r\n"
    "\"%~dp0python\\python.exe\" -m streamlit run \"%~dp0app.py\" --server.headless=false --browser.gatherUsageStats=false\r\n"
    "pause\r\n"
)
# 한국어 Windows cmd 기본 코드페이지(cp949)로 저장 → chcp 없이 한글 표시
open(os.path.join(STAGE, "실행.bat"), "w", encoding="cp949", errors="replace", newline="").write(bat)

readme = (
    "KH LandHub 데모 - 사용법\n"
    "================================\n\n"
    "1) 이 폴더를 통째로 압축 해제한 뒤,\n"
    "2) [실행.bat] 파일을 더블클릭하세요.\n"
    "3) 잠시 후 웹브라우저가 열리며 프로그램이 실행됩니다.\n"
    "   (자동으로 안 열리면 주소창에 http://localhost:8501 입력)\n"
    "4) 종료하려면 함께 떠 있는 검은 명령창을 닫으세요.\n\n"
    "[필요 환경]\n"
    "- Windows 10/11 (64bit)\n"
    "- 인터넷 연결 필요 (지도/공공데이터 조회)\n"
    "- 별도 설치 불필요 (파이썬 내장)\n\n"
    "[샘플 데이터]\n"
    "- data\\sample\\ 폴더에 예시 DXF(구역계) 파일이 있습니다.\n"
    "  좌측 '구역계 범위 지정 > DXF 파일 업로드'에 올려 시험해 보세요.\n\n"
    "[참고]\n"
    "- 첫 실행은 다소 느릴 수 있습니다.\n"
    "- NGII 로컬 수치지도 레이어는 데모에 포함되지 않습니다.\n"
)
open(os.path.join(STAGE, "사용법.txt"), "w", encoding="utf-8").write(readme)

# 8) import 점검
log("[8/8] import 점검")
run([PYEXE, "-c", "import streamlit, folium, streamlit_folium, ezdxf, pyproj, shapely, "
     "pandas, numpy, matplotlib, PIL, openpyxl, shapefile, pptx, requests; "
     "print('OK: 핵심 패키지 import 성공')"])

total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(STAGE) for f in fs)
log(f"빌드 완료: {STAGE}  (총 {total/1024/1024:,.0f} MB)")
print("ZIP 생성: python dist/build_zip.py", flush=True)
