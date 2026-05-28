"""
무상귀속 협의요청서 생성기 (hwpx 직접 편집)

샘플: 연습용자료/01.무상귀속협의요청서(sample).hwpx
출력: 국공유지 필지 한 페이지씩 한 hwpx 파일에 자동 작성

작업 단계:
  1) 샘플 hwpx ZIP을 메모리에 로드
  2) Contents/section0.xml에서 첫 페이지(paragraph 0~인덱스 27)를 템플릿으로 추출
  3) 두 번째 페이지(빈 양식) 제거
  4) 국공유지 필지 N개에 대해 템플릿을 N번 복제하면서 빨간 글씨 자동 치환
     - 지번 전체 (예: "경기도 광명시 가학동 679-4")
     - 지목 (1글자)
     - 공부면적(편입면적) — "408(408)"
     - 공공시설 면적 (예: "도(169)" — 공공기타 지목인 경우)
     - 비공공시설 면적 (예: "잡(239)")
     - 소재지 (간단형: "가학동 679-4번지")
     - 지목 반복
     - 현황 (지목 기반)
     - 소유자 (예: "국(소유자)" — NED는 카테고리만 반환하므로 부서명은 자리표시자)
  5) 페이지 사이 page break 자동 삽입
  6) 새 hwpx ZIP으로 패키징하여 반환

향후 Phase 2:
  - 이미지 2장 (지적도+위성) 자동 생성 + BinData/imgRef 삽입
"""
import io
import re
import zipfile
import datetime
from copy import deepcopy
from typing import List, Dict, Any, Optional
import os


SAMPLE_HWPX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "연습용자료", "01.무상귀속협의요청서(sample).hwpx",
)


# 빨간 글씨에 사용된 charPrIDRef 값들 (분석 결과)
RED_CHAR_IDS = {"32", "42", "72", "73"}

# 지목 다중 글자 → 1글자 약어 매핑 (NED가 "도로", "구거", "유지" 등으로 반환할 때 대비)
JIMOK_SHORT = {
    "도로": "도", "구거": "구", "유지": "유", "임야": "임",
    "공원": "공", "공장용지": "장", "학교용지": "학", "철도용지": "철",
    "주차장": "주", "창고용지": "창", "수도용지": "수", "체육용지": "체",
    "유원지": "원", "종교용지": "종", "사적지": "사", "묘지": "묘", "잡종지": "잡",
    "과수원": "과", "목장용지": "목", "광천지": "광", "염전": "염", "제방": "제",
}


def _short_jimok(jimok_raw):
    """지목 1글자 약어로 변환. 이미 1글자면 그대로."""
    if not jimok_raw:
        return ""
    j = str(jimok_raw).strip()
    if j in JIMOK_SHORT:
        return JIMOK_SHORT[j]
    return j[0] if len(j) >= 1 else j


def _read_zip_bytes(zip_path: str) -> Dict[str, bytes]:
    """hwpx ZIP 안의 모든 파일을 메모리에 dict로 로드."""
    out = {}
    with zipfile.ZipFile(zip_path) as zf:
        for n in zf.namelist():
            out[n] = zf.read(n)
    return out


def _write_zip_bytes(files: Dict[str, bytes]) -> bytes:
    """dict의 모든 파일을 hwpx 호환 ZIP으로 직렬화.
    mimetype은 압축 안 함(STORED)이 hwpx 규약."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype 먼저 (STORED)
        if "mimetype" in files:
            zinfo = zipfile.ZipInfo("mimetype")
            zinfo.compress_type = zipfile.ZIP_STORED
            zf.writestr(zinfo, files["mimetype"])
        for name, data in files.items():
            if name == "mimetype":
                continue
            zf.writestr(name, data)
    buf.seek(0)
    return buf.getvalue()


def _split_pages(sec_xml: str) -> List[str]:
    """section0.xml을 페이지 단위 XML 청크로 분리.

    페이지 시작: pageBreak="1" 속성을 가진 <hp:p> 또는 첫 paragraph.
    """
    # paragraph 단위로 분리하기 위해 모든 <hp:p> 시작 위치 수집
    starts = [m.start() for m in re.finditer(r'<hp:p\s', sec_xml)]
    # 페이지 시작 paragraph (pageBreak="1") 위치
    page_starts = [m.start() for m in re.finditer(r'<hp:p[^>]*pageBreak="1"', sec_xml)]

    # 페이지 경계 = 첫 paragraph(0) + pageBreak="1" 모두
    boundaries = sorted(set([starts[0]] + page_starts)) if starts else []

    pages = []
    for i, b in enumerate(boundaries):
        end = boundaries[i + 1] if i + 1 < len(boundaries) else None
        pages.append(sec_xml[b:end] if end else sec_xml[b:])
    return pages


def _replace_red_texts_in_page(page_xml: str, values: List[str]) -> str:
    """페이지 XML 안의 빨간 글씨 run을 순서대로 values로 치환.

    Args:
        page_xml: 한 페이지의 XML 문자열
        values: 빨간 글씨에 들어갈 텍스트 9개 순서대로
                [지번전체, 지목, 공부면적(편입), 공공시설, 비공공시설, 소재지간단, 지목2, 현황, 소유자]
    """
    # <hp:run charPrIDRef="32" ...><hp:t>OLD</hp:t></hp:run>
    # → <hp:run charPrIDRef="32" ...><hp:t>NEW</hp:t></hp:run>
    # 빨간 ID만 매칭
    pattern = re.compile(
        r'(<hp:run\s+charPrIDRef="(?:32|42|72|73)"[^>]*>\s*)'
        r'(<hp:t[^>]*>)(.*?)(</hp:t>\s*</hp:run>)',
        re.DOTALL,
    )

    idx = [0]
    def _sub(m):
        if idx[0] < len(values):
            v = values[idx[0]] or ""
            idx[0] += 1
        else:
            v = m.group(3)  # values 모자라면 원본 유지
        # XML 특수문자 이스케이프
        v = (str(v).replace("&", "&amp;")
                  .replace("<", "&lt;").replace(">", "&gt;"))
        return f"{m.group(1)}{m.group(2)}{v}{m.group(4)}"

    return pattern.sub(_sub, page_xml)


def _build_page_values(parcel: Dict[str, Any]) -> List[str]:
    """필지 데이터에서 빨간 글씨 9개 값 생성.

    빨간 글씨 순서:
      [0] 지번 전체 (예: '경기도 광명시 가학동 679-4')
      [1] 지목 (1글자)
      [2] 공부면적(편입면적) — '408(408)'
      [3] 공공시설 면적 — 지목이 공공이면 그 지목+면적, 아니면 빈
      [4] 비공공시설 면적 — 지목이 공공 아니면 그 지목+면적, 아니면 빈
      [5] 소재지 간단 (예: '가학동 679-4번지')
      [6] 지목 반복
      [7] 현황 (지목 기반)
      [8] 소유자 — 카테고리 자리표시자 (예: '국(소유자)') — 한글에서 부서명 수동 수정
    """
    attr = parcel.get("analysis_attr", {}) or {}
    # 토지조서 데이터에서
    addr_admin = attr.get("소재지", "")  # clean된 행정구역 (예: "경기도 광명시 가학동")
    bonbun = str(attr.get("본번", "") or "0").strip()
    bubun = str(attr.get("부번", "") or "0").strip()
    pungu = str(attr.get("필지구분", "") or "").strip()
    jimok = _short_jimok(attr.get("지목", ""))  # "도로" → "도" 등 1글자 변환
    daejang = attr.get("대장면적(㎡)", 0) or 0
    pyeon = attr.get("편입면적(㎡)", 0) or 0
    owner = attr.get("소유자", "")

    # 지번 (예: "산 50-2" 또는 "679-4")
    if bonbun and bonbun != "0":
        jibun = f"{bonbun}-{bubun}" if (bubun and bubun != "0") else bonbun
        if pungu == "산":
            jibun = f"산 {jibun}"
    else:
        jibun = ""

    # 지번 전체 = 행정구역 + 지번
    full_address = f"{addr_admin} {jibun}".strip() if jibun else addr_admin

    # 행정구역에서 동/리만 추출 → "가학동 679-4번지"
    parts_addr = addr_admin.split()
    dong_ri = ""
    for p in reversed(parts_addr):
        if any(p.endswith(suf) for suf in ("동", "리")):
            dong_ri = p
            break
    short_addr = f"{dong_ri} {jibun}번지" if (dong_ri and jibun) else (jibun or dong_ri)

    # 면적 (정수 처리)
    try:
        daejang_int = int(round(float(daejang)))
    except Exception:
        daejang_int = 0
    try:
        pyeon_int = int(round(float(pyeon)))
    except Exception:
        pyeon_int = 0
    area_text = f"{daejang_int}({pyeon_int})"

    # 공공/비공공 구분 — 지목이 도/구/하천/제방/공원/유지 등이면 공공
    PUBLIC_JIMOKS = {"도", "구", "유", "공", "철", "제", "수"}
    if jimok in PUBLIC_JIMOKS:
        public_area = f"{jimok}({pyeon_int})"
        nonpub_area = ""
    else:
        public_area = ""
        nonpub_area = f"{jimok}({pyeon_int})" if jimok else ""

    # 소유자 텍스트 — NED API는 카테고리만 반환하므로 부서명은 (소유자) 자리표시자로 두어 한글에서 수동 수정.
    OWNER_MAP = {
        "국유지": "국(소유자)",
        "공유지": "공(소유자)",
        "군유지": "군(소유자)",
        "시  도유지": "시도(소유자)",
        "도유지": "도(소유자)",
        "시유지": "시(소유자)",
    }
    owner_text = OWNER_MAP.get(owner, owner)

    return [
        full_address,   # [0]
        jimok,          # [1]
        area_text,      # [2]
        public_area,    # [3]
        nonpub_area,    # [4]
        short_addr,     # [5]
        jimok,          # [6]
        jimok,          # [7] 현황 = 지목으로 일단
        owner_text,     # [8]
    ]


def _ensure_page_break(page_xml: str) -> str:
    """페이지 XML의 첫 <hp:p>에 pageBreak="1"을 강제 설정."""
    return re.sub(
        r'(<hp:p[^>]*?)(\s+pageBreak="\d")?(\s|>)',
        lambda m: f'{m.group(1)} pageBreak="1"{m.group(3)}',
        page_xml,
        count=1,
    )


def _strip_page_break_first(page_xml: str) -> str:
    """첫 paragraph의 pageBreak="1"을 "0"으로 (문서 시작 페이지는 페이지 분리 불필요)."""
    return re.sub(
        r'(<hp:p[^>]*?)\s+pageBreak="1"',
        r'\1 pageBreak="0"',
        page_xml,
        count=1,
    )


# hwpx 샘플의 hp:pic 박스 종횡비 (width/height) — 약 0.867
# image3: 23663×27289, image4: 23527×27212 → 평균 0.866
_PIC_ASPECT = 23663 / 27289  # 가로/세로

# sample image3.jpg와 동일한 픽셀 dimension — 한글이 사이즈로 인한 잘못된 회전 처리 회피
_TARGET_IMG_WIDTH = 2304
_TARGET_IMG_HEIGHT = 2656


def _fetch_vworld_parcels(min_lon, min_lat, max_lon, max_lat, max_features=2000):
    """V-World Data API로 BBOX 안 모든 필지(LP_PA_CBND_BUBUN) polygon + 지번/지목 가져오기.

    Returns:
        list of dict: [{"polygon": shapely.Polygon, "jibun": "157-1", "jimok": "전", "pnu": "..."}]
    """
    try:
        import requests
        from shapely.geometry import Polygon as _Polygon
        from config import VWORLD_KEY, VWORLD_DOMAIN
        VWORLD_DATA_URL = "https://api.vworld.kr/req/data"
        bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"
        parcels = []
        page = 1
        while True:
            try:
                params = {
                    "service": "data", "request": "GetFeature",
                    "data": "LP_PA_CBND_BUBUN",
                    "key": VWORLD_KEY, "domain": VWORLD_DOMAIN,
                    "geomFilter": f"BOX({bbox})",
                    "size": "1000", "page": str(page),
                    "geometry": "true", "format": "json",
                    "crs": "EPSG:4326",
                }
                res = requests.get(VWORLD_DATA_URL, params=params, timeout=20)
                data = res.json()
                if data.get("response", {}).get("status") != "OK":
                    break
                features = data["response"]["result"]["featureCollection"]["features"]
                for feat in features:
                    geom = feat.get("geometry") or {}
                    coords = geom.get("coordinates")
                    if not coords:
                        continue
                    gtype = geom.get("type", "")
                    props = feat.get("properties", {}) or {}
                    polys_raw = []
                    if gtype == "Polygon":
                        polys_raw = [coords]
                    elif gtype == "MultiPolygon":
                        polys_raw = coords
                    for poly_raw in polys_raw:
                        try:
                            if not poly_raw or not poly_raw[0]:
                                continue
                            outer = poly_raw[0]
                            holes = poly_raw[1:] if len(poly_raw) > 1 else None
                            sp = _Polygon(outer, holes=holes)
                            if sp.is_empty:
                                continue
                            parcels.append({
                                "polygon": sp,
                                "jibun": props.get("jibun", "") or "",
                                "jimok": props.get("jimok", "") or "",
                                "pnu": props.get("pnu", "") or "",
                            })
                        except Exception:
                            pass
                if len(features) < 1000 or len(parcels) >= max_features:
                    break
                page += 1
            except Exception:
                break
        return parcels
    except Exception as e:
        print(f"[agreement] V-World 필지 조회 실패: {e}")
        return []


def _polygon_parts(geom):
    """Polygon/MultiPolygon에서 그릴 수 있는 part 리스트 반환."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    if hasattr(geom, "geoms"):
        return [g for g in geom.geoms if g.geom_type == "Polygon"]
    return []


def _parse_vworld_jibun(jibun_str: str):
    """V-World jibun 필드를 (지번, 1글자 지목)로 분리.
    예: '157-1전' → ('157-1', '전'), '산 157' → ('산 157', '')
    """
    if not jibun_str:
        return "", ""
    s = str(jibun_str).strip()
    # 마지막 한 글자가 한글이고 그 앞이 숫자/공백/하이픈/산이면 → 지목으로 분리
    if len(s) >= 2:
        last = s[-1]
        if '가' <= last <= '힣':  # 한글 음절
            head = s[:-1].rstrip()
            # 앞 부분에 다른 한글이 있으면 안 분리 (예: 잘못된 케이스)
            head_no_san = head[2:] if head.startswith("산 ") else head
            if all(not ('가' <= c <= '힣') for c in head_no_san):
                return head, last
    return s, ""


def _fetch_vworld_satellite_tiles(min_lon, min_lat, max_lon, max_lat,
                                   target_width_px=900, max_zoom=18):
    """V-World WMTS 위성 타일을 다운로드/합성하여 PIL Image와 실제 extent(4326) 반환.

    Returns: (PIL.Image, (west, south, east, north)) or (None, None) on failure.
    """
    try:
        import math
        import requests
        from PIL import Image
        from config import VWORLD_KEY

        # 뷰 폭 기준 적절한 zoom 자동 결정
        view_w_deg = max_lon - min_lon
        # 이미지 폭이 target_width_px가 되도록: tile=256px, 픽셀 폭 = view_w_deg * 360 / (256 * 2^zoom)
        # zoom = log2(view_w_deg * 360 * target_width_px / (256 * 360)) → log2(view_w_deg * target_width_px / 256) — 잘못
        # 올바른 공식: world width at zoom z = 256 * 2^z px = 360 deg
        # so px_per_deg = 256*2^z/360. view_px = view_w_deg * px_per_deg = target_width_px
        # 2^z = target_width_px * 360 / (view_w_deg * 256) → z = log2(target_width_px * 360 / (256 * view_w_deg))
        if view_w_deg <= 0:
            return None, None
        zoom = int(round(math.log2(target_width_px * 360 / (256 * view_w_deg))))
        zoom = max(10, min(max_zoom, zoom))

        def deg2num(lat_deg, lon_deg, z):
            lat_rad = math.radians(lat_deg)
            n = 2.0 ** z
            xt = (lon_deg + 180.0) / 360.0 * n
            yt = (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n
            return xt, yt

        def num2deg(xt, yt, z):
            n = 2.0 ** z
            lon = xt / n * 360.0 - 180.0
            lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * yt / n))))
            return lat, lon

        # 코너 4점의 타일 인덱스
        x0f, y0f = deg2num(max_lat, min_lon, zoom)  # NW
        x1f, y1f = deg2num(min_lat, max_lon, zoom)  # SE
        x0, x1 = int(math.floor(x0f)), int(math.floor(x1f))
        y0, y1 = int(math.floor(y0f)), int(math.floor(y1f))

        if (x1 - x0 + 1) * (y1 - y0 + 1) > 100:  # 안전: 100타일 초과 시 zoom 줄이기 — 실패 처리
            return None, None

        # 타일 다운로드 — 적은 worker 수(3개)로 병렬 + 재시도 (V-World 부담 회피하며 속도 확보)
        import concurrent.futures
        tile_size = 256
        canvas = Image.new("RGB", ((x1 - x0 + 1) * tile_size, (y1 - y0 + 1) * tile_size), (200, 200, 200))

        def _fetch_tile(tx, ty):
            url = f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Satellite/{zoom}/{ty}/{tx}.jpeg"
            for attempt in range(2):
                try:
                    res = requests.get(url, timeout=12)
                    if res.status_code == 200 and len(res.content) > 100:
                        return tx, ty, Image.open(io.BytesIO(res.content)).convert("RGB")
                except Exception:
                    pass
            return tx, ty, None

        tile_coords = [(tx, ty) for tx in range(x0, x1 + 1) for ty in range(y0, y1 + 1)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
            futures = [ex.submit(_fetch_tile, tx, ty) for tx, ty in tile_coords]
            for fut in concurrent.futures.as_completed(futures):
                try:
                    tx, ty, tile_img = fut.result()
                    if tile_img is not None:
                        canvas.paste(tile_img, ((tx - x0) * tile_size, (ty - y0) * tile_size))
                except Exception:
                    pass

        # canvas의 실제 extent (4326)
        nw_lat, nw_lon = num2deg(x0, y0, zoom)
        se_lat, se_lon = num2deg(x1 + 1, y1 + 1, zoom)
        return canvas, (nw_lon, se_lat, se_lon, nw_lat)
    except Exception as e:
        try:
            print(f"[agreement] WMTS 타일 합성 실패: {e}")
        except Exception:
            pass
        return None, None


def _parcel_jibun_jimok(parcel: Dict[str, Any]) -> str:
    """라벨용 '지번\\n(지목)' 텍스트 생성. 정보 없으면 빈 문자열."""
    attr = parcel.get("analysis_attr", {}) or {}
    bonbun = str(attr.get("본번", "") or "0").strip()
    bubun = str(attr.get("부번", "") or "0").strip()
    pungu = str(attr.get("필지구분", "") or "").strip()
    if bonbun and bonbun != "0":
        jibun = f"{bonbun}-{bubun}" if (bubun and bubun != "0") else bonbun
        if pungu == "산":
            jibun = f"산 {jibun}"
    else:
        jibun = ""
    jimok = _short_jimok(attr.get("지목", ""))
    if jibun and jimok:
        return f"{jibun}\n({jimok})"
    return jibun or jimok


def _make_placeholder_png(text: str, height_px: int = 2650) -> bytes:
    """이미지 생성 실패시에도 빈 PNG를 반환 — sample의 image3/image4 ref가
    무조건 새 ID로 교체되도록 보장 (안 그러면 모든 페이지에 sample 원본 이미지 노출)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.font_manager import FontProperties
        try:
            font_prop = FontProperties(fname="C:/Windows/Fonts/malgun.ttf")
        except Exception:
            font_prop = None
        fig_dpi = 144
        fig_inches_w = _TARGET_IMG_WIDTH / fig_dpi
        fig_inches_h = _TARGET_IMG_HEIGHT / fig_dpi
        fig = plt.figure(figsize=(fig_inches_w, fig_inches_h), dpi=fig_dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_facecolor("#f5f5f5")
        ax.text(0.5, 0.5, text, fontsize=28, color="#888888",
                ha="center", va="center", transform=ax.transAxes,
                fontproperties=font_prop)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=fig_dpi, bbox_inches=None, pad_inches=0)
        plt.close(fig)
        buf.seek(0)
        # dpi=(72,72) 명시
        try:
            from PIL import Image as _Image
            img = _Image.open(buf)
            out_buf = io.BytesIO()
            img.save(out_buf, format="PNG", dpi=(72, 72))
            out_buf.seek(0)
            return out_buf.getvalue()
        except Exception:
            buf.seek(0)
            return buf.getvalue()
    except Exception:
        # 최후의 fallback — 1x1 흰 PNG
        return (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff"
                b"\xff?\x03\x00\x06\xfc\x02\xfe\xa7\xfc\xc8\xb6\x00\x00\x00\x00IEND\xaeB`\x82")


def _make_parcel_map_image(target_parcel: Dict[str, Any],
                            all_parcels: List[Dict[str, Any]],
                            kind: str = "satellite",
                            boundary_polygon=None,
                            height_px: int = 2650,
                            prefetched_vworld_parcels=None) -> bytes:
    """대상 필지가 강조된 지도 PNG 생성. 위쪽이 정북.

    hwpx 박스 종횡비(가로/세로 = 0.867)에 정확히 맞춤. sample image3와 비슷한
    픽셀 크기(~2300×2650)로 만들어 한글이 박스에 꽉 차게 표시하도록.

    Args:
        target_parcel: 강조할 필지 (지적도형 폴리곤 + analysis_attr 포함)
        all_parcels: 주변 모든 필지
        kind: "cadastral" — 흰 배경에 모든 필지 외곽선 + 모든 지번 표시 (대상만 빨간색)
              "satellite" — V-World 위성 배경 + 대상 필지만 빨간 강조
        boundary_polygon: 사업지구 경계 (shapely Polygon, 4326). 뷰에 걸치면 2점쇄선으로 표시.
        height_px: 출력 이미지 세로 픽셀 (가로는 종횡비로 자동)

    Returns:
        PNG bytes — 실패해도 placeholder 반환 (절대 None 아님).
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.font_manager import FontProperties
        from matplotlib.patheffects import withStroke
        from PIL import Image
        import requests

        target_poly = target_parcel.get("지적도형")
        label_txt = "지적도 없음" if kind == "cadastral" else "위성 없음"
        if target_poly is None or target_poly.is_empty:
            return _make_placeholder_png(label_txt, height_px)

        # view extent — 대상 필지 중심, view 한 변 = target 한 변 × 2
        # → 대상이 화면의 ~50% 차지, 사업지구는 view에 들어오는 부분만 자연스레 표시
        # 페이지마다 대상 필지 크기에 따라 스케일 다름 (각 필지가 적정 크기로 잘 보이게)
        minx, miny, maxx, maxy = target_poly.bounds
        w = maxx - minx
        h = maxy - miny
        if w <= 0 or h <= 0:
            return _make_placeholder_png(label_txt, height_px)

        cx = (minx + maxx) / 2
        cy = (miny + maxy) / 2
        # 외접 정사각형 반쪽 + pad(=같은 사이즈) → view 한 변 = target 큰 변 × 2
        half_target = max(w, h) / 2
        pad = max(w, h) * 0.5
        # 너무 작은 필지(예: 좁은 도로) 보정 — 최소 시야 ~120m
        min_view_deg = 0.0006
        side_half = max(half_target + pad, min_view_deg)
        ex_minx, ex_maxx = cx - side_half, cx + side_half
        ex_miny, ex_maxy = cy - side_half, cy + side_half

        try:
            plt.rcParams["font.family"] = "Malgun Gothic"
            plt.rcParams["axes.unicode_minus"] = False
            font_prop = FontProperties(fname="C:/Windows/Fonts/malgun.ttf")
        except Exception:
            font_prop = None

        # figure 종횡비 + 픽셀 dimension을 sample image3과 정확히 맞춤 (2304×2656)
        # 한글이 일부 케이스에서 작은 이미지를 90도/180도 회전하던 현상 회피
        fig_dpi = 144
        fig_inches_w = _TARGET_IMG_WIDTH / fig_dpi
        fig_inches_h = _TARGET_IMG_HEIGHT / fig_dpi
        width_px = _TARGET_IMG_WIDTH
        fig = plt.figure(figsize=(fig_inches_w, fig_inches_h), dpi=fig_dpi)
        ax = fig.add_axes([0, 0, 1, 1])  # 여백 0 — figure 전체를 axes로

        target_pnu = target_parcel.get("PNU")

        # === 배경 설정 ===
        if kind == "satellite":
            # V-World WMTS 위성 타일 합성 (WMS는 Satellite 레이어 미지원)
            sat_img, sat_extent = _fetch_vworld_satellite_tiles(
                ex_minx, ex_miny, ex_maxx, ex_maxy, target_width_px=width_px
            )
            if sat_img is not None and sat_extent is not None:
                w_lon, s_lat, e_lon, n_lat = sat_extent
                ax.imshow(sat_img,
                          extent=[w_lon, e_lon, s_lat, n_lat],
                          origin="upper", aspect="auto", zorder=0)
            else:
                ax.set_facecolor("#e6e6e6")
        else:  # cadastral
            ax.set_facecolor("white")
            # V-World Data API — 미리 받아둔 필지 리스트(prefetched)가 있으면 view에 맞게 필터링,
            # 없으면 직접 호출
            if prefetched_vworld_parcels is not None:
                from shapely.geometry import box as _box
                view_box = _box(ex_minx, ex_miny, ex_maxx, ex_maxy)
                vworld_parcels = [
                    vp for vp in prefetched_vworld_parcels
                    if vp.get("polygon") is not None and vp["polygon"].intersects(view_box)
                ]
            else:
                margin_x = (ex_maxx - ex_minx) * 0.05
                margin_y = (ex_maxy - ex_miny) * 0.05
                vworld_parcels = _fetch_vworld_parcels(
                    ex_minx - margin_x, ex_miny - margin_y,
                    ex_maxx + margin_x, ex_maxy + margin_y,
                )
            # land_data와 중복 회피용 PNU 집합
            user_pnus = set()
            for p in all_parcels:
                pn = p.get("PNU")
                if pn:
                    user_pnus.add(str(pn))
            # 각 V-World 필지: 검정 외곽선 + 큰 라벨 (land_data 라벨과 동일 사이즈)
            for vp in vworld_parcels:
                if vp.get("pnu") and str(vp["pnu"]) in user_pnus:
                    continue  # land_data에서 별도 처리
                vpoly = vp["polygon"]
                for sp in _polygon_parts(vpoly):
                    try:
                        x, y = sp.exterior.xy
                        ax.plot(x, y, color="black", lw=1.8, zorder=1)
                    except Exception:
                        pass
                # 라벨 — V-World jibun에서 지번/지목 분리
                jib, jim = _parse_vworld_jibun(vp.get("jibun", ""))
                if not jim:
                    jim = _short_jimok(vp.get("jimok", ""))
                lbl = f"{jib}\n({jim})" if (jib and jim) else (jib or jim)
                if lbl:
                    try:
                        ctr = vpoly.representative_point() if vpoly.geom_type == "Polygon" else vpoly.centroid
                        if ex_minx <= ctr.x <= ex_maxx and ex_miny <= ctr.y <= ex_maxy:
                            ax.text(ctr.x, ctr.y, lbl,
                                    fontsize=28, color="black",
                                    ha="center", va="center", zorder=4,
                                    fontproperties=font_prop,
                                    linespacing=0.95)
                    except Exception:
                        pass

        # 사업지구 안쪽 판별 + 국공유지 판별
        def _is_inside_site(poly):
            if boundary_polygon is None or boundary_polygon.is_empty:
                return True  # 사업지구 없으면 모든 필지를 안쪽으로
            try:
                return boundary_polygon.intersects(poly)
            except Exception:
                return False

        # 해치를 사업지구로 clipping — 외곽선은 원본 그대로, 해치만 boundary∩poly로 잘림
        def _clip_to_site(poly):
            """사업지구가 있으면 그 안쪽 영역으로 자른 폴리곤 반환. 없으면 원본."""
            if boundary_polygon is None or boundary_polygon.is_empty:
                return poly
            try:
                clipped = boundary_polygon.intersection(poly)
                return clipped if not clipped.is_empty else None
            except Exception:
                return None

        # === cadastral: 모든 필지의 외곽선 + 라벨 ===
        # ▶ 모든 필지 외곽선: 검정 얇은 선
        # ▶ 사이안(cyan) 해치는 오직 "이 페이지의 대상 필지"에만 적용 (사업지구 안쪽 영역만 clipping)
        # ▶ 나머지 국공유지: 외곽선 + 라벨만, 해치 없음
        CYAN_FILL = "#00BFFF"    # deep sky blue (참고 이미지의 하늘색)

        if kind == "cadastral":
            for p in all_parcels:
                if p.get("PNU") == target_pnu:
                    continue  # 대상 필지는 별도 처리
                poly = p.get("지적도형")
                if poly is None or poly.is_empty:
                    continue

                # 외곽선 — 모든 필지 검정 선
                for sp in _polygon_parts(poly):
                    try:
                        x, y = sp.exterior.xy
                        ax.plot(x, y, color="black", lw=1.8, zorder=2)
                    except Exception:
                        pass

                # 라벨 — 검정 글씨
                lbl = _parcel_jibun_jimok(p)
                if lbl:
                    try:
                        ctr = poly.representative_point() if poly.geom_type == "Polygon" else poly.centroid
                        if ex_minx <= ctr.x <= ex_maxx and ex_miny <= ctr.y <= ex_maxy:
                            ax.text(ctr.x, ctr.y, lbl,
                                    fontsize=28, color="black",
                                    ha="center", va="center", zorder=5,
                                    fontproperties=font_prop,
                                    linespacing=0.95)
                    except Exception:
                        pass

        # === 대상 필지 — 빨간 외곽선(얇음) + 하늘색 해치(사업지구 안쪽만) ===
        # 외곽선 — 원본 폴리곤 전체 (얇은 빨간 선)
        for sp in _polygon_parts(target_poly):
            try:
                x, y = sp.exterior.xy
                ax.plot(x, y, color="red", lw=2.0, zorder=9)
            except Exception:
                pass
        # 하늘색 해치 — 사업지구로 clip
        if kind == "cadastral":
            target_clipped = _clip_to_site(target_poly)
            for sp in _polygon_parts(target_clipped):
                try:
                    x, y = sp.exterior.xy
                    ax.fill(x, y, facecolor=CYAN_FILL, alpha=0.7, zorder=8)
                except Exception:
                    pass
        else:
            # satellite — 위성 위에는 기존처럼 빨간 해치 유지 (시인성)
            for sp in _polygon_parts(target_poly):
                try:
                    x, y = sp.exterior.xy
                    ax.fill(x, y, facecolor="red", alpha=0.45, zorder=8)
                except Exception:
                    pass

        # === 사업지구 경계 — 굵은 빨간 2점쇄선 — 뷰와 교차 시에만 ===
        if boundary_polygon is not None and not boundary_polygon.is_empty:
            try:
                from shapely.geometry import box as _box
                view_box = _box(ex_minx, ex_miny, ex_maxx, ex_maxy)
                if boundary_polygon.intersects(view_box):
                    # 2점쇄선: dash + dot + dot
                    dash_pattern = (0, (10, 4, 1, 4, 1, 4))
                    for bp in ([boundary_polygon] if boundary_polygon.geom_type == "Polygon" else boundary_polygon.geoms):
                        try:
                            bx, by = bp.exterior.xy
                            ax.plot(bx, by, color="red", lw=5.0,
                                    linestyle=dash_pattern, zorder=10,
                                    label="사업지구 경계")
                        except Exception:
                            pass
            except Exception:
                pass

        # === 대상 필지 라벨 — 빨간 글씨 (흰색 외곽 stroke로 가독성) ===
        target_lbl = _parcel_jibun_jimok(target_parcel)
        if target_lbl:
            try:
                ctr = target_poly.representative_point() if target_poly.geom_type == "Polygon" else target_poly.centroid
                ax.text(ctr.x, ctr.y, target_lbl,
                        fontsize=38, color="red", weight="bold",
                        ha="center", va="center", zorder=11,
                        fontproperties=font_prop,
                        linespacing=0.95,
                        path_effects=[withStroke(linewidth=5.0, foreground="white")])
            except Exception:
                pass

        ax.set_xlim(ex_minx, ex_maxx)
        ax.set_ylim(ex_miny, ex_maxy)
        ax.set_aspect("auto")
        # ★ set_aspect 후에도 ax position이 자동 조정되는 경우가 있어 강제로 figure 전체로
        ax.set_position([0, 0, 1, 1])
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)

        # 박스에 꽉 차도록 — bbox_inches=None, pad_inches=0, dpi는 figure와 동일
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=fig_dpi, bbox_inches=None, pad_inches=0)
        plt.close(fig)
        buf.seek(0)

        # PIL 후처리 — sample image3.jpg와 동일하게 dpi=(72,72) 명시 (한글이 박스에 맞춰 표시)
        # + cadastral은 180도 회전 (위성은 그대로)
        try:
            img = Image.open(buf)
            if kind == "cadastral":
                img = img.transpose(Image.ROTATE_180)
            out_buf = io.BytesIO()
            img.save(out_buf, format="PNG", dpi=(72, 72))
            out_buf.seek(0)
            return out_buf.getvalue()
        except Exception:
            buf.seek(0)
            return buf.getvalue()
    except Exception as e:
        try:
            import traceback
            print(f"[agreement] 이미지 생성 실패 ({kind}): {e}")
            traceback.print_exc()
        except Exception:
            pass
        return _make_placeholder_png(f"{kind} 생성 실패", height_px)


def _renumber_page_ids(page_xml: str, page_idx: int) -> str:
    """페이지 안 모든 id/instid를 페이지별 unique 작은 숫자로 재할당.

    기존 sample의 id 일부가 2^31 부근이라 단순 offset은 32-bit overflow를 일으켜
    한글이 페이지를 빈 채로 렌더링하는 문제를 fix.
    zOrder는 건드리지 않음 — hp:pic 내부의 레이어 순서이므로 페이지간 충돌 없음.
    """
    counter = [page_idx * 100000 + 1]
    def _new(m):
        attr = m.group(1)
        val = counter[0]
        counter[0] += 1
        return f'{attr}="{val}"'
    return re.sub(r'\b(id|instid)="\d+"', _new, page_xml)


def _recolor_red_charprs_to_black(hdr_xml: str, target_ids: set) -> str:
    """header.xml에서 지정된 charPr id들의 textColor를 #FF0000 → #000000으로 변경.

    각 <hh:charPr id="X" ... textColor="#FF0000" ...> 블록을 찾아 텍스트 색만 검정으로.
    """
    def _patch(m):
        opening = m.group(0)
        cid = re.search(r'id="(\d+)"', opening)
        if cid and cid.group(1) in target_ids:
            return re.sub(r'textColor="#[Ff][Ff]0000"',
                          'textColor="#000000"', opening, count=1)
        return opening

    # <hh:charPr ...> 태그 (자식 요소 포함 가능하므로 opening tag만 매칭)
    return re.sub(r'<hh:charPr\s[^>]*>', _patch, hdr_xml)


def _add_manifest_items(hpf_xml: str, items_xml: List[str]) -> str:
    """content.hpf의 manifest에 새 item들을 추가.

    items_xml 예: ['<opf:item id="agcad1" href="BinData/..." media-type="image/png" isEmbeded="1"/>', ...]
    """
    if not items_xml:
        return hpf_xml
    # </opf:manifest> 직전에 삽입
    insertion = "\n    " + "\n    ".join(items_xml) + "\n  "
    return hpf_xml.replace("</opf:manifest>", insertion + "</opf:manifest>", 1)


def is_public_owner(owner: str) -> bool:
    """소유자가 국/공/군/도/시 유지인지 판별."""
    if not owner:
        return False
    s = str(owner)
    return any(k in s for k in ["국유", "공유", "군유", "도유", "시유"])


def generate_agreement_hwpx(land_data: List[Dict[str, Any]],
                             boundary_polygon=None) -> bytes:
    """국공유지 필지별 한 페이지씩 무상귀속 협의요청서 hwpx 생성.

    Args:
        land_data: 분석 결과가 병합된 land_data 리스트.
                   각 항목은 {"analysis_attr": {...}, "지적도형": ...} 형태.
        boundary_polygon: 사업지구 경계 (shapely Polygon, WGS84). 이미지에 2점쇄선으로
                          교차 영역만 표시. None이면 표시 안 함.

    Returns:
        bytes: 새 hwpx 파일 바이너리. 국공유지 필지 0개면 None.
    """
    public_parcels = [p for p in land_data
                      if is_public_owner((p.get("analysis_attr") or {}).get("소유자", ""))]
    if not public_parcels:
        return None

    # 1) 샘플 hwpx 메모리에 로드
    files = _read_zip_bytes(SAMPLE_HWPX_PATH)
    sec_xml = files["Contents/section0.xml"].decode("utf-8")
    hpf_xml = files["Contents/content.hpf"].decode("utf-8")
    hdr_xml = files["Contents/header.xml"].decode("utf-8")

    # 빨간 글씨용 charPr(id=32,42,72,73)의 textColor를 검정으로 변경
    # → 자동 치환된 값(지번/지목/면적/소유자 등)이 검정 글씨로 출력됨
    hdr_xml = _recolor_red_charprs_to_black(hdr_xml, {"32", "42", "72", "73"})
    files["Contents/header.xml"] = hdr_xml.encode("utf-8")

    # 2) 페이지 분리 (샘플은 2페이지)
    pages = _split_pages(sec_xml)
    if not pages:
        raise RuntimeError("샘플에서 페이지를 찾을 수 없습니다.")

    template_page = pages[0]  # 빨간 글씨 + 이미지 2개가 있는 첫 페이지를 템플릿으로

    # section의 시작 prefix (XML 선언 + <hs:sec ...>) 추출
    sec_match = re.search(r'^(.*?<hs:sec[^>]*>)', sec_xml, re.DOTALL)
    sec_prefix = sec_match.group(1) if sec_match else ""
    sec_suffix = "</hs:sec>"

    # 3-a) 성능 최적화: 모든 페이지의 view extent를 union해서 V-World 필지 한 번에 일괄 조회
    #      (페이지마다 API 호출 → 1회로 단축, 국공유지 N개 → API 호출 N → 1)
    prefetched_parcels = None
    try:
        u_minx = u_miny = float("inf")
        u_maxx = u_maxy = float("-inf")
        for p in public_parcels:
            poly = p.get("지적도형")
            if poly is None or poly.is_empty:
                continue
            mn = poly.bounds
            u_minx = min(u_minx, mn[0]); u_miny = min(u_miny, mn[1])
            u_maxx = max(u_maxx, mn[2]); u_maxy = max(u_maxy, mn[3])
        if boundary_polygon is not None and not boundary_polygon.is_empty:
            bb = boundary_polygon.bounds
            u_minx = min(u_minx, bb[0]); u_miny = min(u_miny, bb[1])
            u_maxx = max(u_maxx, bb[2]); u_maxy = max(u_maxy, bb[3])
        if u_minx < float("inf"):
            # 페이지별 pad(target × 0.5)도 union하므로 약간 더 넓게
            uw = u_maxx - u_minx
            uh = u_maxy - u_miny
            u_minx -= uw * 0.1; u_maxx += uw * 0.1
            u_miny -= uh * 0.1; u_maxy += uh * 0.1
            prefetched_parcels = _fetch_vworld_parcels(u_minx, u_miny, u_maxx, u_maxy,
                                                       max_features=5000)
    except Exception as e:
        print(f"[agreement] V-World 일괄 조회 실패, 페이지별 개별 호출로 fallback: {e}")
        prefetched_parcels = None

    # 3-b) 페이지별 이미지 생성 — 순차 처리 (matplotlib thread-safe 아님)
    #      페이지 병렬화 대신 페이지 내부의 위성 타일 병렬화 + V-World 일괄 조회로 속도 확보
    image_pairs = []
    for parcel in public_parcels:
        try:
            cad = _make_parcel_map_image(parcel, land_data, kind="cadastral",
                                          boundary_polygon=boundary_polygon,
                                          prefetched_vworld_parcels=prefetched_parcels)
            sat = _make_parcel_map_image(parcel, land_data, kind="satellite",
                                          boundary_polygon=boundary_polygon)
            image_pairs.append((cad, sat))
        except Exception as e:
            print(f"[agreement] 페이지 이미지 생성 실패: {e}")
            image_pairs.append((None, None))

    # 3-c) 페이지 빌드 — 텍스트 치환 + 이미지 삽입
    new_pages = []
    new_manifest_items = []
    for i, parcel in enumerate(public_parcels):
        values = _build_page_values(parcel)
        page = _replace_red_texts_in_page(template_page, values)

        cad_bytes, sat_bytes = image_pairs[i]
        if cad_bytes is None:
            cad_bytes = _make_placeholder_png("지적도 없음")
        if sat_bytes is None:
            sat_bytes = _make_placeholder_png("위성 없음")

        cad_id = f"agcad{i+1}"
        cad_path = f"BinData/agreement_cad_{i+1}.png"
        files[cad_path] = cad_bytes
        new_manifest_items.append(
            f'<opf:item id="{cad_id}" href="{cad_path}" media-type="image/png" isEmbeded="1"/>'
        )
        page = page.replace('binaryItemIDRef="image3"', f'binaryItemIDRef="{cad_id}"')

        sat_id = f"agsat{i+1}"
        sat_path = f"BinData/agreement_sat_{i+1}.png"
        files[sat_path] = sat_bytes
        new_manifest_items.append(
            f'<opf:item id="{sat_id}" href="{sat_path}" media-type="image/png" isEmbeded="1"/>'
        )
        page = page.replace('binaryItemIDRef="image4"', f'binaryItemIDRef="{sat_id}"')

        page = _renumber_page_ids(page, i)

        if i == 0:
            page = _strip_page_break_first(page)
        else:
            page = _ensure_page_break(page)

        new_pages.append(page)

    # 4) 새 section0.xml 조립
    new_sec = sec_prefix + "".join(new_pages) + sec_suffix
    files["Contents/section0.xml"] = new_sec.encode("utf-8")

    # 5) content.hpf manifest 갱신 — 새 이미지 item 추가
    if new_manifest_items:
        hpf_xml = _add_manifest_items(hpf_xml, new_manifest_items)
        files["Contents/content.hpf"] = hpf_xml.encode("utf-8")

    # 6) PrvText.txt도 간단히 갱신 (미리보기용)
    preview_lines = [f"무상귀속 협의요청서 — {len(public_parcels)}건 국공유지"]
    for p in public_parcels[:5]:
        v = _build_page_values(p)
        preview_lines.append(f"  • {v[0]} ({v[1]}, {v[2]}) — {v[8]}")
    files["Preview/PrvText.txt"] = "\n".join(preview_lines).encode("utf-8")

    return _write_zip_bytes(files)
