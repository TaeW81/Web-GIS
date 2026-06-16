# KH LandHub 웹 배포 가이드 (로그인 보호)

로컬 실행은 그대로 두고, **웹에서 로그인한 사용자만** 쓰도록 배포하는 방법입니다.
코드는 `KH_WEB_MODE` 플래그로 동작이 갈립니다.

- **로컬**(플래그 없음): 데스크톱 기능 사용 가능, 로그인 없음 — 지금까지와 동일
- **웹**(`KH_WEB_MODE=1`): 데스크톱 전용 기능 숨김 + 로그인 보호 ON

---

## 1. 추천 호스팅 — Streamlit Community Cloud (무료)

1. 코드가 GitHub(`TaeW81/Web-GIS`)에 올라가 있어야 합니다. (이미 연결됨)
2. https://share.streamlit.io 에 GitHub 계정으로 로그인
3. **New app** → 저장소 `TaeW81/Web-GIS`, 브랜치 `main`, 메인 파일 `app.py` 선택
4. **Advanced settings → Secrets** 칸에 아래 `secrets.toml` 내용을 붙여넣기 (다음 단계 참고)
5. Deploy → 잠시 후 공개 URL 생성

> 성능/리소스가 부족하면 Render·Fly.io 등 Docker 호스팅으로 이전 가능(같은 코드 사용).

---

## 2. Secrets 설정 (가장 중요)

`.streamlit/secrets.toml.example` 을 복사해 값을 채웁니다.
- **로컬 테스트**: 프로젝트에 `.streamlit/secrets.toml` 로 저장 (이 파일은 `.gitignore`로 깃 제외됨)
- **웹 배포**: 호스팅의 Secrets 칸에 같은 내용 붙여넣기

### 2-1. API 키
실제 발급키로 교체:
```
KH_WEB_MODE = "1"
VWORLD_KEY = "..."
NIE_KEY    = "..."
NGII_KEY   = "..."
ECVAM_KEY  = "..."
```

### 2-2. 로그인 사용자 (비밀번호는 반드시 해시)
평문 비밀번호를 해시로 바꿔서 넣습니다:
```bash
python -c "import streamlit_authenticator as s; print(s.Hasher(['실제비밀번호']).generate())"
```
출력된 `$2b$12$....` 해시를 `password =` 에 넣습니다. (사용자 여러 명 추가 가능)

---

## 3. ⚠️ 배포 전 반드시 처리할 것

1. **V-World 도메인 등록**
   현재 키는 `localhost` 전용입니다. V-World 포털(개발자센터 → 인증키 관리)에서
   **배포된 도메인**(예: `https://your-app.streamlit.app`)을 등록해야 지도/데이터가 뜹니다.

2. **HWP '현황분석 보고서' 템플릿 (별도 조치 필요)**
   - `report/status_report_generator.py` 가 `연습용자료/현황분석보고서(sample).hwpx`(**약 83MB**)를 읽습니다.
   - 이 파일은 용량이 커서 GitHub에 올리기 부적합 → **현재 웹 배포본에는 미포함**.
   - 무상귀속 협의요청서(3.3MB)·편입산지조서(20KB) 템플릿은 포함 가능.
   - **해결 방안(택1)**: ① sample hwpx 내부 이미지를 제거해 경량화 후 `templates/`로 포함,
     ② 외부 저장소(사내 서버)에서 런타임에 내려받기. → 추후 작업 항목.

3. **개인정보 주의**
   소유자 정보(토지대장)를 다루므로, 로그인으로 사용자를 **신뢰 범위로 한정**하세요.
   완전 공개(로그인 없음)는 권장하지 않습니다.

---

## 4. 로컬은 그대로

웹 배포와 무관하게, 내 PC에서는 평소처럼 실행됩니다 (로그인·기능 제한 없음):
```
streamlit run app.py
```
`KH_WEB_MODE` 를 설정하지 않으면 항상 로컬 모드입니다.
