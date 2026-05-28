"""
NGII 1/5000 연속수치지형도 SHP 로컬 로더 + Folium 통합

V-World WMS의 한계(NGII 분류별 레이어 미등록)를 우회하기 위해
사용자가 NGII에서 직접 다운로드한 SHP 파일을 로컬에서 처리.

폴더 구조:
  data/ngii_shp/
    README.md                       다운로드 가이드
    <시군구코드>/                  예: 47230(영천), 41170(광명)
      N3A_A0010000.shp 등          NGII 표준 명명 SHP 파일들

주요 API:
  scan_available_regions()                  → 시군구 폴더 목록
  list_layers_in_region(code, category)     → 매칭 SHP 파일 목록
  load_layer_geojson(code, category, bbox)  → Folium용 GeoJSON dict
  get_layer_style(category)                 → 카테고리별 색상/굵기

NGII 코드 체계 (1/5000):
  N3 + 기하(A/L/P) + _ + 8자리 분류코드
  - A=면(Area), L=선(Line), P=점(Point)
  - 분류 첫글자: A=경계, B=교통, C=시설물, D=토양, E=수계, F=지형, G=식생, H=주기
"""
import os
import glob
from functools import lru_cache

NGII_SHP_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "ngii_shp",
)

# 시군구 코드 → 한글명 일부 (UI 표시용, 전체는 별도 마스터 필요)
SIDO_CODE_HINT = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천", "29": "광주",
    "30": "대전", "31": "울산", "36": "세종", "41": "경기", "42": "강원",
    "43": "충북", "44": "충남", "45": "전북", "46": "전남", "47": "경북",
    "48": "경남", "50": "제주",
}

# 사용자 카테고리 → SHP 파일명 prefix 매핑
# (정확한 NGII 코드는 데이터 설명서 Ver 5.1.1 기준 추정)
NGII_CATEGORY_FILE_PATTERNS = {
    "교통": ["N3A_B", "N3L_B"],          # 도로면 + 도로중심선 + 철도 (B 분류 전체)
    "건물": ["N3A_C001", "N3A_C002"],    # 건물 (C0010000, C0020000)
    "시설": ["N3A_C", "N3L_C"],          # 그 외 시설물 (C 분류, 건물 prefix는 제외)
    "식생": ["N3A_G", "N3L_G"],          # 식생 (G 분류)
    "수계": ["N3A_E", "N3L_E"],          # 수계 면+선 (E 분류)
    "지형": ["N3L_F001"],                # 등고선 (F0010000)
    "경계": ["N3A_A", "N3L_A"],          # 행정/경계 (A 분류)
    "주기": ["N3P_H", "N3A_H"],          # 주기/지명 (H 분류)
    "표고점": ["N3P_F002"],              # 표고점 (F0020000)
}

# 분류별 시각 스타일 (사용자 첫 이미지의 색감 참고)
NGII_CATEGORY_STYLES = {
    "교통": {"color": "#333333", "weight": 1.5, "fillColor": "#aaaaaa", "fillOpacity": 0.3},
    "건물": {"color": "#666666", "weight": 1, "fillColor": "#cccccc", "fillOpacity": 0.6},
    "시설": {"color": "#888888", "weight": 1, "fillColor": "#dddddd", "fillOpacity": 0.4},
    "식생": {"color": "#4caf50", "weight": 0.5, "fillColor": "#a5d6a7", "fillOpacity": 0.35},
    "수계": {"color": "#1565c0", "weight": 2, "fillColor": "#64b5f6", "fillOpacity": 0.45},
    "지형": {"color": "#8b5a2b", "weight": 0.5, "fillOpacity": 0},           # 등고선 갈색
    "경계": {"color": "#e91e63", "weight": 1.5, "fillOpacity": 0, "dashArray": "5,5"},
    "주기": {"color": "#ff6f00", "weight": 0, "fillColor": "#ff9800", "fillOpacity": 0.7},
    "표고점": {"color": "#555555", "weight": 0.5, "fillColor": "#888888", "fillOpacity": 0.6},
}


def _region_label(code):
    """시군구 코드 → '47230 (경북)' 형식 표시 라벨."""
    sido = SIDO_CODE_HINT.get(code[:2], "")
    return f"{code} ({sido})" if sido else code


@lru_cache(maxsize=8)
def scan_available_regions():
    """data/ngii_shp/<시군구>/ 폴더 중 SHP가 포함된 것만 반환.

    Returns:
        list of dict: [{"code": "47230", "label": "47230 (경북)", "path": "...", "shp_count": N}, ...]
    """
    if not os.path.isdir(NGII_SHP_ROOT):
        return []
    regions = []
    for entry in sorted(os.listdir(NGII_SHP_ROOT)):
        full = os.path.join(NGII_SHP_ROOT, entry)
        if not os.path.isdir(full):
            continue
        shps = glob.glob(os.path.join(full, "*.shp"))
        if shps:
            regions.append({
                "code": entry,
                "label": _region_label(entry),
                "path": full,
                "shp_count": len(shps),
            })
    return regions


def list_layers_in_region(region_code, category):
    """카테고리 매칭 SHP 파일 경로 목록."""
    region_path = os.path.join(NGII_SHP_ROOT, region_code)
    if not os.path.isdir(region_path):
        return []
    patterns = NGII_CATEGORY_FILE_PATTERNS.get(category, [])
    if not patterns:
        return []
    files = []
    for fname in os.listdir(region_path):
        if not fname.lower().endswith(".shp"):
            continue
        # 시설 카테고리는 건물(C001/C002) 파일 제외
        if category == "시설" and (fname.startswith("N3A_C001") or fname.startswith("N3A_C002")):
            continue
        if any(fname.startswith(pat) for pat in patterns):
            files.append(os.path.join(region_path, fname))
    return files


def load_layer_geojson(region_code, category, bbox_4326=None, max_features=5000):
    """주어진 시군구 + 카테고리의 SHP를 합쳐 GeoJSON dict로 반환.

    Args:
        region_code: 시군구 코드 폴더명 (예: "47230")
        category:    사용자 카테고리 ("교통"/"건물"/...)
        bbox_4326:   (minx, miny, maxx, maxy) — EPSG:4326. 이 영역과 교차하는 피처만.
                      None이면 전체 (시군구 전체는 클 수 있으므로 BBOX 권장)
        max_features: 안전장치 — 피처가 너무 많으면 잘림

    Returns:
        GeoJSON dict (Folium에 그대로 넣을 수 있음) 또는 None (데이터 없음)
    """
    shp_files = list_layers_in_region(region_code, category)
    if not shp_files:
        return None

    # geopandas는 import 비용이 있어 함수 안에서 import (모듈 로드시 지연)
    import geopandas as gpd
    from shapely.geometry import box, mapping

    features = []
    bbox_geom = box(*bbox_4326) if bbox_4326 else None

    for shp in shp_files:
        try:
            gdf = gpd.read_file(shp)
            if gdf.empty:
                continue
            # 좌표계 → EPSG:4326 (Folium 표준)
            if gdf.crs is None:
                # NGII SHP는 보통 EPSG:5186 (중부원점 GRS80) — 추정
                gdf = gdf.set_crs(epsg=5186, allow_override=True)
            try:
                if gdf.crs.to_epsg() != 4326:
                    gdf = gdf.to_crs(epsg=4326)
            except Exception:
                gdf = gdf.to_crs(epsg=4326)

            # BBOX 필터링
            if bbox_geom is not None:
                gdf = gdf[gdf.intersects(bbox_geom)]
            if gdf.empty:
                continue

            for _, row in gdf.iterrows():
                if row.geometry is None or row.geometry.is_empty:
                    continue
                # attribute에서 None/NaN 제거, 직렬화 가능한 값만
                props = {}
                for k, v in row.items():
                    if k == "geometry":
                        continue
                    try:
                        if v is None or (hasattr(v, "__class__") and v.__class__.__name__ == "Timestamp"):
                            continue
                        # NaN 체크
                        if isinstance(v, float) and v != v:
                            continue
                        props[str(k)] = v
                    except Exception:
                        continue
                features.append({
                    "type": "Feature",
                    "geometry": mapping(row.geometry),
                    "properties": props,
                })
                if len(features) >= max_features:
                    break
            if len(features) >= max_features:
                break
        except Exception as e:
            print(f"[NGII SHP 로드 실패] {os.path.basename(shp)}: {e}")
            continue

    if not features:
        return None
    return {"type": "FeatureCollection", "features": features}


def get_layer_style(category):
    """Folium GeoJson style_function 용 dict 반환."""
    return NGII_CATEGORY_STYLES.get(category, {"color": "#999", "weight": 1, "fillOpacity": 0.3})


def find_region_for_bbox(bbox_4326):
    """주어진 BBOX(EPSG:4326)에 해당하는 시군구 폴더를 자동 추론.

    각 시군구 폴더의 행정경계 SHP(N3A_A*)와 BBOX 교차 여부로 판단.
    없으면 None (사용자가 직접 SHP 다운로드 필요).

    안전한 fallback: 그냥 첫 번째 사용 가능한 시군구 반환 (BBOX 분석 안 함).
    """
    regions = scan_available_regions()
    if not regions:
        return None
    # 1차: 단순히 첫 번째 (대부분의 사용 사례에서 사용자는 한 지역만 다운로드)
    # TODO: 정확한 BBOX 교차 검증은 향후 추가
    return regions[0]["code"]
