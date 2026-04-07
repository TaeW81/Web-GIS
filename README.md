# KH-GIS LandScan: Web-GIS 기반 현황분석 자동화 플랫폼

건화(KH)의 공간정보 정밀 스캔 기술이 집약된 GIS 기반 토지·건축물 현황분석 자동화 솔루션입니다. 사용자가 대상지 구역계(DXF) 파일을 업로드하면, VWorld API 및 WMS/WFS를 활용하여 지적도 기반의 공간 데이터를 시각화하고 편입 토지의 조서와 체계적인 면적 분석 결과를 엑셀 형태로 추출해 줍니다.

---

## 📂 디렉토리 구조 (Directory Structure)

협업 시 참고할 주요 파일 및 폴더의 역할은 다음과 같습니다.

```text
📦 Web-GIS 기반 현황분석 자동화
 ┣ 📂 analyzers/        # 조서 분석 및 필지/건축물 등 아이템별 자동화 로직 모음
 ┃ ┣ 📜 base_analyzer.py      # 분석기 추상 베이스 클래스
 ┃ ┣ 📜 land_attribute.py     # 토지 속성 분석기
 ┃ ┗ 📜 zoning_region.py      # 구역(Zoning) 및 지역 분석기
 ┣ 📂 assets/           # UI 디자인, 브랜딩에 사용되는 정적 자원 (로고 등)
 ┣ 📂 data/             # 로컬 테스트용 등 샘플 데이터 및 결과물 저장소
 ┣ 📂 docs/             # 프로젝트 관련 참고 API 가이드 및 매뉴얼 파일 위치
 ┃ ┣ 📜 4.WMS_DATA_API조회.html
 ┃ ┗ 📂 reference/      # VWorld API 및 기타 지침서, 사용 매뉴얼
 ┣ 📂 modules/          # 데이터 처리 및 다운로드/시각화를 위한 핵심 백엔드 모듈
 ┃ ┣ 📜 dxf_exporter.py       # DXF 추출 모듈
 ┃ ┣ 📜 dxf_parser.py         # 업로드된 도면(DXF) 해석 및 좌표계 변환 프로세싱
 ┃ ┣ 📜 excel_exporter.py     # 산출된 조서 데이터를 엑셀(다중 시트)로 배포
 ┃ ┣ 📜 map_builder.py        # Folium을 활용하여 메인 위치도(VWorld 지도) 렌더링
 ┃ ┣ 📜 pnu_extractor.py      # 브이월드 API를 활용한 폴리곤 내 PNU 코드 추출기
 ┃ ┣ 📜 spatial_downloader.py # WFS 데이터 (SHP/DXF) 다운로드 로직 수행
 ┃ ┗ 📜 vworld_search.py      # 장소 검색 모듈
 ┣ 📂 archive/          # (백업) 기존의 구버전 스크립트 및 테스트 모듈 보관 (수정 X)
 ┣ 📂 tests/            # 단위 테스트, 디버깅 및 시각화 테스트 전용 스크립트 모음
 ┃ ┣ 📜 debug_*.py
 ┃ ┗ 📜 test_*.py
 ┣ 📜 app.py            # 🚀 [ENTRY POINT] Streamlit 메인 UI 애플리케이션 창구
 ┣ 📜 config.py         # API 키(VWorld) 및 전역 환경 설정, 좌표계 변환 세팅
 ┣ 📜 requirements.txt  # 프로젝트 실행에 필요한 Python 패키지 의존성 목록
 ┗ 📜 .env (ignored)    # 중요/보안이 필요한 환경변수 설정 파일 (Git 무시됨)
```

---

## 🚀 시작하기 (Getting Started)

### 1. 요구 사항 (Prerequisites)
- **Python 3.9+** 이상 권장
- Streamlit 및 공간 정보 분석 라이브러리 지원 (geopandas 등)

### 2. 패키지 설치
초기 구동 시 아래 명령어를 실행하여 필요 라이브러리(`requirements.txt`)를 설치합니다.
```bash
pip install -r requirements.txt
```

### 3. 환경 변수 설정
본 솔루션은 VWorld 공간 정보 오픈 플랫폼 API를 사용하고 있습니다. 
프로젝트 루트 경로에 `.env` 파일을 만들고 아래와 같이 키를 설정해 주세요.
```env
# .env 파일 예시
VWORLD_KEY=당신의_브이월드_인증키
```
*(참고: `.env` 파일은 `.gitignore`에 등록되어 있어 GitHub 저장소에 올라가지 않습니다.)*

### 4. 프로그램 실행!!
아래 Streamlit 커맨드로 로컬 웹 서버를 실행합니다.
```bash
streamlit run app.py
```
실행 시 터미널에서 제공되는 주소(예: `http://localhost:8501`)로 브라우저를 통해 접속할 수 있습니다.

---

## 🤝 협업 가이드라인 (Contributors Guide)

- **새로운 기능 추가:** 새로운 분석 모듈은 `analyzers/` 폴더에 `base_analyzer.py`를 상속하여 생성해 주세요.
- **맵 및 공간 데이터 핸들링:** 맵 렌더링이나 데이터 다운로드(SHP/DXF) 관련은 모두 `modules/` 폴더 내에 분산 구현되어 있습니다.
- **수정사항 발생:** 각 커밋 전에 테스트 코드(`tests/`내)를 사용하여 정상 동작 및 UI 컴포넌트 렌더링 오류가 없는지 확인해 주세요.
- **결과 파일 무시 (.gitignore):** 프로그램 구동 중 생성되는 `.xlsx` 이나 임시 `.dxf` 등은 로컬에 남게 하되 VCR(Git)에 올라가지 않아야 합니다.

## 📌 기능 소개
* **구역계 범위 업로드:** 사용자의 대상지 좌표가 담긴 DXF 파일을 분석하여 대상지 경계를 지도에 표시합니다.
* **배경도 선택 및 좌표 매칭:** 다양한 KOREA_CRS 체계에 맞게 도면 좌표를 자동 투영 변환합니다.
* **현황 조서 분석:** 대상지에 포함되는 편입 필지를 자동 스캔하여, 필지의 속성 및 통계 자료를 일괄 추출(Excel)합니다.
* **배경 데이터 추출:** VWorld WFS에서 도출된 다양한 레이어들을 로컬 DXF/SHP 형식으로 저장하여 2차/3차 설계 툴(AutoCAD, QGIS 등)과 병행 사용할 수 있도록 지원합니다.

---
**ⓒ KunHwa Engineering & Consulting**
