# KH LandHub 이식형(Portable) ZIP 빌드 스크립트
# 내장 Python 3.11.9 + 패키지 설치 + 앱/템플릿 복사 + 런처 생성
$ErrorActionPreference = "Stop"
chcp 65001 | Out-Null
$OutputEncoding = [System.Text.Encoding]::UTF8

$PyVer = "3.11.9"
$Root  = Split-Path -Parent $PSScriptRoot          # 저장소 루트
$Dist  = $PSScriptRoot                              # ...\dist
$Stage = Join-Path $Dist "KH_LandHub_demo"
$Py    = Join-Path $Stage "python"
$Cache = Join-Path $Dist "_cache"

Write-Host "[1/8] 작업 폴더 준비..." -ForegroundColor Cyan
if (Test-Path $Stage) { Remove-Item $Stage -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Stage, $Py, $Cache | Out-Null

# ---- 2. 내장 Python 다운로드/전개 ----
$embedZip = Join-Path $Cache "python-$PyVer-embed-amd64.zip"
if (-not (Test-Path $embedZip)) {
    Write-Host "[2/8] 내장 Python $PyVer 다운로드..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" -OutFile $embedZip
} else { Write-Host "[2/8] 내장 Python 캐시 사용" -ForegroundColor Cyan }
Expand-Archive -Path $embedZip -DestinationPath $Py -Force

# ---- 3. site 활성화 (pip 설치 패키지 인식) ----
Write-Host "[3/8] python._pth 설정..." -ForegroundColor Cyan
$pth = Get-ChildItem $Py -Filter "python*._pth" | Select-Object -First 1
(Get-Content $pth.FullName) -replace '^\s*#\s*import site', 'import site' | Set-Content $pth.FullName -Encoding ascii

# ---- 4. pip 부트스트랩 ----
$getpip = Join-Path $Cache "get-pip.py"
if (-not (Test-Path $getpip)) {
    Write-Host "[4/8] get-pip.py 다운로드..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip
}
& "$Py\python.exe" $getpip --no-warn-script-location
if ($LASTEXITCODE -ne 0) { throw "pip 부트스트랩 실패" }

# ---- 5. 패키지 설치 ----
Write-Host "[5/8] 패키지 설치 (수 분 소요)..." -ForegroundColor Cyan
& "$Py\python.exe" -m pip install --no-warn-script-location --no-cache-dir -r "$Dist\requirements_portable.txt"
if ($LASTEXITCODE -ne 0) { throw "패키지 설치 실패" }

# ---- 6. 앱 소스/자료 복사 ----
Write-Host "[6/8] 앱 파일 복사..." -ForegroundColor Cyan
$copyItems = @("app.py","config.py","modules","report","analyzers","assets","tools")
foreach ($it in $copyItems) {
    $src = Join-Path $Root $it
    if (Test-Path $src) { Copy-Item $src -Destination $Stage -Recurse -Force }
}
# data: 필요한 것만 (대용량 ngii_shp 제외)
New-Item -ItemType Directory -Force -Path "$Stage\data\output","$Stage\data\project_cache","$Stage\data\sample" | Out-Null
if (Test-Path "$Root\data\compensation_ratio.json") { Copy-Item "$Root\data\compensation_ratio.json" "$Stage\data\" -Force }
if (Test-Path "$Root\data\sample") { Copy-Item "$Root\data\sample\*" "$Stage\data\sample\" -Recurse -Force }
# 보고서 템플릿(연습용자료의 sample hwpx 2종)
New-Item -ItemType Directory -Force -Path "$Stage\연습용자료" | Out-Null
foreach ($f in @("현황분석보고서(sample).hwpx","01.무상귀속협의요청서(sample).hwpx","편입산지조서(sample).xlsx")) {
    if (Test-Path "$Root\연습용자료\$f") { Copy-Item "$Root\연습용자료\$f" "$Stage\연습용자료\" -Force }
}
# __pycache__ 정리
Get-ChildItem $Stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

# ---- 7. .streamlit 설정 + 런처 + 안내문 ----
Write-Host "[7/8] 런처/설정 생성..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "$Stage\.streamlit" | Out-Null
@"
[browser]
gatherUsageStats = false
[server]
headless = false
port = 8501
[theme]
base = "light"
"@ | Set-Content "$Stage\.streamlit\config.toml" -Encoding utf8

$bat = @"
@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   KH LandHub 데모 - 통합 토지 분석 플랫폼
echo ============================================
echo.
echo  잠시 후 브라우저가 자동으로 열립니다.
echo  (열리지 않으면 브라우저에서 http://localhost:8501 로 접속)
echo.
echo  * 종료하려면 이 검은 창을 닫으세요.
echo.
"%~dp0python\python.exe" -m streamlit run "%~dp0app.py" --server.headless=false --browser.gatherUsageStats=false
pause
"@
Set-Content "$Stage\실행.bat" -Value $bat -Encoding oem

$readme = @"
KH LandHub 데모 - 사용법
================================

1) 이 폴더를 통째로 압축 해제한 뒤,
2) [실행.bat] 파일을 더블클릭하세요.
3) 잠시 후 웹브라우저가 열리며 프로그램이 실행됩니다.
   (자동으로 안 열리면 브라우저 주소창에 http://localhost:8501 입력)
4) 종료하려면 함께 떠 있는 검은 명령창을 닫으세요.

[필요 환경]
- Windows 10/11 (64bit)
- 인터넷 연결 필요 (지도/공공데이터 조회)
- 별도 설치 불필요 (파이썬 내장)

[샘플 데이터]
- data\sample\ 폴더에 예시 DXF(구역계) 파일이 있습니다.
  좌측 '구역계 범위 지정 > DXF 파일 업로드'에 올려 시험해 보세요.

[참고]
- 첫 실행은 다소 느릴 수 있습니다.
- NGII 로컬 수치지도 레이어는 데모에 포함되지 않습니다.
"@
Set-Content "$Stage\사용법.txt" -Value $readme -Encoding utf8

# ---- 8. 동작 점검 ----
Write-Host "[8/8] import 점검..." -ForegroundColor Cyan
& "$Py\python.exe" -c "import streamlit, folium, streamlit_folium, ezdxf, pyproj, shapely, pandas, numpy, matplotlib, PIL, openpyxl, shapefile, pptx, requests; print('OK: 핵심 패키지 import 성공')"
if ($LASTEXITCODE -ne 0) { throw "import 점검 실패" }

$size = "{0:N0} MB" -f ((Get-ChildItem $Stage -Recurse | Measure-Object Length -Sum).Sum / 1MB)
Write-Host ""
Write-Host "빌드 완료: $Stage  (총 $size)" -ForegroundColor Green
Write-Host "ZIP 생성은 build_zip.ps1 실행" -ForegroundColor Green
