"""
표고 분석기 — boundary 안 grid sampling + 구간별 면적/구성비 계산

DEM source: OpenTopoData SRTM30m (https://api.opentopodata.org/)
  · 무료 (1일 1,000 calls / 1초당 1 call / 1 call당 최대 100개 좌표)
  · 한국 전역 약 30m 해상도

사용 예:
    from modules.elevation_analyzer import analyze_elevation
    result = analyze_elevation(boundary_polygon)
    # result = {
    #     "total_area_m2": 806767,
    #     "bins": [
    #         {"label": "5m 미만",  "area_m2": 57656,  "ratio": 7.1, "color": "#a8d8ff"},
    #         {"label": "5~10m",    "area_m2": 749111, "ratio": 92.9, "color": "#7ec0ff"},
    #         {"label": "10m 이상", "area_m2": 0,      "ratio": 0.0, "color": "#3b82d9"},
    #     ],
    #     "samples": [(lon, lat, elev), ...],  # 시각화용
    #     "grid_size_m": 30,
    # }
"""
from __future__ import annotations
import time
import math
from typing import Optional, List, Tuple
import requests
from pyproj import Geod, Transformer
from shapely.geometry import Polygon, Point


# 표고 구간 (sample 양식 기준)
ELEVATION_BINS = [
    {"label": "5m 미만",  "min": -1e9, "max": 5.0,   "color": "#a8d8ff"},
    {"label": "5~10m",    "min": 5.0,  "max": 10.0,  "color": "#5fa8ff"},
    {"label": "10m 이상", "min": 10.0, "max": 1e9,   "color": "#1f5fc7"},
]

# OpenTopoData
_OPEN_TOPO_URL = "https://api.opentopodata.org/v1/srtm30m"
_BATCH_SIZE = 100        # 한 call 최대 100개 좌표
_RATE_LIMIT_DELAY = 1.05  # 1 call/second 제한 (safety margin)


def _build_grid(boundary_polygon: Polygon, target_grid_count: int = 400) -> List[Tuple[float, float]]:
    """boundary 안 균등 grid 점들 (lon, lat) 생성.

    target_grid_count는 sample 점 목표 개수 (대략). 사업지구 면적에 따라 grid 간격 자동.
    """
    minx, miny, maxx, maxy = boundary_polygon.bounds
    w_deg = maxx - minx
    h_deg = maxy - miny
    aspect = w_deg / h_deg if h_deg > 0 else 1.0
    # n_x * n_y ≈ target_grid_count, n_x/n_y = aspect → n_y = sqrt(target/aspect)
    n_y = max(8, int(math.sqrt(target_grid_count / aspect)))
    n_x = max(8, int(n_y * aspect))
    dx = w_deg / n_x
    dy = h_deg / n_y
    pts = []
    for ix in range(n_x):
        for iy in range(n_y):
            lon = minx + (ix + 0.5) * dx
            lat = miny + (iy + 0.5) * dy
            if boundary_polygon.contains(Point(lon, lat)):
                pts.append((lon, lat))
    return pts


def _fetch_elevations(points: List[Tuple[float, float]]) -> List[Optional[float]]:
    """OpenTopoData SRTM30m으로 표고 batch 조회. 각 점에 대해 표고(m) 또는 None.
    points: [(lon, lat), ...]
    """
    elevs: List[Optional[float]] = [None] * len(points)
    for i in range(0, len(points), _BATCH_SIZE):
        chunk = points[i:i + _BATCH_SIZE]
        loc_str = "|".join(f"{lat},{lon}" for (lon, lat) in chunk)
        try:
            r = requests.get(_OPEN_TOPO_URL, params={"locations": loc_str},
                             timeout=20)
            data = r.json()
            if data.get("status") == "OK":
                for j, item in enumerate(data.get("results", [])):
                    e = item.get("elevation")
                    if e is not None:
                        try:
                            elevs[i + j] = float(e)
                        except Exception:
                            pass
        except Exception as ex:
            print(f"[elevation] batch {i//_BATCH_SIZE} 실패: {ex}")
        # rate limit
        if i + _BATCH_SIZE < len(points):
            time.sleep(_RATE_LIMIT_DELAY)
    return elevs


def _classify(elev: Optional[float]) -> Optional[int]:
    """표고값 → bin 인덱스. None이면 None 반환."""
    if elev is None:
        return None
    for i, b in enumerate(ELEVATION_BINS):
        if b["min"] <= elev < b["max"]:
            return i
    return None


def analyze_elevation(boundary_polygon: Polygon,
                      target_grid_count: int = 400) -> dict:
    """사업지구 boundary 안 표고 분석.

    Returns:
        dict {
            "total_area_m2": float,
            "bins": [
                {"label": "...", "area_m2": float, "ratio": float, "color": "#..."},
                ...
            ],
            "samples": [(lon, lat, elev, bin_idx), ...],   # 유효 점만
            "grid_size_m": float,                          # 한 셀의 가로 변 길이 추정
            "min_elev": float, "max_elev": float, "mean_elev": float,
        }
    """
    if boundary_polygon is None or boundary_polygon.is_empty:
        return _empty_result()

    # 측지 면적
    geod = Geod(ellps="WGS84")
    try:
        total_area_m2, _ = geod.geometry_area_perimeter(boundary_polygon)
        total_area_m2 = abs(total_area_m2)
    except Exception:
        total_area_m2 = 0.0

    # grid 생성
    points = _build_grid(boundary_polygon, target_grid_count=target_grid_count)
    if not points:
        return _empty_result()

    # 표고 조회
    elevs = _fetch_elevations(points)

    # 유효 sample만
    samples: List[Tuple[float, float, float, int]] = []
    bin_counts = [0] * len(ELEVATION_BINS)
    elev_values = []
    for (lon, lat), e in zip(points, elevs):
        if e is None:
            continue
        bidx = _classify(e)
        if bidx is None:
            continue
        samples.append((lon, lat, e, bidx))
        bin_counts[bidx] += 1
        elev_values.append(e)

    n_valid = sum(bin_counts)
    if n_valid == 0:
        return _empty_result()

    # 각 구간 면적 = 총면적 × 구성비
    bins_out = []
    for i, b in enumerate(ELEVATION_BINS):
        ratio = bin_counts[i] / n_valid
        area = total_area_m2 * ratio
        bins_out.append({
            "label": b["label"],
            "area_m2": area,
            "ratio": ratio * 100.0,
            "color": b["color"],
            "count": bin_counts[i],
        })

    # grid_size 추정 (셀 한 변의 실제 거리)
    minx, miny, maxx, maxy = boundary_polygon.bounds
    geod_dx, _, _ = geod.inv(minx, (miny + maxy) / 2, maxx, (miny + maxy) / 2)
    # n_x 대략적으로 sqrt
    aspect = (maxx - minx) / max(maxy - miny, 1e-9)
    n_y = max(8, int(math.sqrt(target_grid_count / aspect)))
    n_x = max(8, int(n_y * aspect))
    grid_size_m = geod_dx / max(n_x, 1)

    return {
        "total_area_m2": total_area_m2,
        "bins": bins_out,
        "samples": samples,
        "grid_size_m": grid_size_m,
        "min_elev": min(elev_values),
        "max_elev": max(elev_values),
        "mean_elev": sum(elev_values) / len(elev_values),
        "n_valid": n_valid,
    }


def _empty_result() -> dict:
    return {
        "total_area_m2": 0.0,
        "bins": [{"label": b["label"], "area_m2": 0.0, "ratio": 0.0,
                  "color": b["color"], "count": 0} for b in ELEVATION_BINS],
        "samples": [],
        "grid_size_m": 0.0,
        "min_elev": 0.0, "max_elev": 0.0, "mean_elev": 0.0,
        "n_valid": 0,
    }


# ────────────────────────────────────────────────────────────────────────────
#  표고 분석 지도 이미지 (구간별 hex grid + 사업지구 경계)
# ────────────────────────────────────────────────────────────────────────────
def make_elevation_map_image(boundary_polygon: Polygon,
                              analysis_result: dict,
                              size_px: int = 1100) -> bytes:
    """boundary 안 sample 점들을 구간별 색상 hex grid로 표시한 PNG 생성.

    Args:
        boundary_polygon: 사업지구 (4326)
        analysis_result: analyze_elevation 결과
        size_px: 이미지 한 변 크기 (가로 기준; 종횡비 유지)

    Returns:
        bytes (PNG)
    """
    import io
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri
    from matplotlib.colors import BoundaryNorm, ListedColormap
    from matplotlib.patches import PathPatch, Patch
    from matplotlib.path import Path as MplPath
    from matplotlib.font_manager import FontProperties

    try:
        font_prop = FontProperties(fname="C:/Windows/Fonts/malgun.ttf")
    except Exception:
        font_prop = None

    samples = analysis_result.get("samples") or []
    bins = analysis_result.get("bins") or []
    if not samples:
        # 빈 placeholder
        fig = plt.figure(figsize=(size_px / 100, size_px / 100), dpi=100)
        ax = fig.add_axes([0.05, 0.05, 0.9, 0.9])
        ax.text(0.5, 0.5, "표고 자료 없음", fontsize=24,
                ha="center", va="center", transform=ax.transAxes,
                color="#888888", fontproperties=font_prop)
        ax.axis("off")
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        plt.close(fig); buf.seek(0)
        return buf.getvalue()

    minx, miny, maxx, maxy = boundary_polygon.bounds
    w = maxx - minx; h = maxy - miny
    pad = max(w, h) * 0.05
    ex_minx, ex_maxx = minx - pad, maxx + pad
    ex_miny, ex_maxy = miny - pad, maxy + pad

    aspect = (ex_maxx - ex_minx) / max(ex_maxy - ex_miny, 1e-9)
    fig_w = size_px / 100
    fig_h = fig_w / aspect
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("white")
    ax.set_xlim(ex_minx, ex_maxx)
    ax.set_ylim(ex_miny, ex_maxy)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)

    # ── 연속 표고 컬러맵 (tricontourf) — 실제 표고 그라데이션 ──
    # 표(5m/10m 구간)와 별개로, 이미지는 실제 표고를 terrain 컬러맵으로 표현
    # → 평지든 산지든 미세 표고 변화가 보임 (sample 표고도 스타일)
    lons = np.array([s[0] for s in samples])
    lats = np.array([s[1] for s in samples])
    elevs = np.array([s[2] for s in samples])

    e_min = float(elevs.min())
    e_max = float(elevs.max())
    if e_max - e_min < 1.0:
        e_max = e_min + 1.0  # 평탄지 — 최소 범위 확보

    # 저지대(녹색) → 중간(노랑) → 고지대(갈색) 표고 컬러맵
    elev_cmap = plt.cm.terrain

    drawn = False
    try:
        if len(samples) >= 4:
            triang = mtri.Triangulation(lons, lats)
            levels = np.linspace(e_min, e_max, 12)
            cf = ax.tricontourf(triang, elevs, levels=levels,
                                cmap=elev_cmap, alpha=0.85, zorder=2,
                                extend="both")
            # 사업지구 boundary로 clip
            for sp in ([boundary_polygon] if boundary_polygon.geom_type == "Polygon" else boundary_polygon.geoms):
                try:
                    verts = list(sp.exterior.coords)
                    clip_path = MplPath(verts)
                    patch = PathPatch(clip_path, transform=ax.transData,
                                      facecolor="none", edgecolor="none")
                    ax.add_patch(patch)
                    for coll in cf.collections:
                        coll.set_clip_path(patch)
                except Exception:
                    pass
            # 컬러바 (표고 범례)
            try:
                cbar = fig.colorbar(cf, ax=ax, fraction=0.04, pad=0.02,
                                    shrink=0.7)
                cbar.set_label("표고(m)", fontproperties=font_prop, fontsize=11)
                for t in cbar.ax.get_yticklabels():
                    if font_prop:
                        t.set_fontproperties(font_prop)
            except Exception:
                pass
            drawn = True
    except Exception as e:
        print(f"[elevation] tricontourf failed, scatter fallback: {e}")

    if not drawn:
        sc = ax.scatter(lons, lats, c=elevs, cmap=elev_cmap, s=30,
                        marker="s", edgecolors="none", alpha=0.85, zorder=2)

    # 사업지구 경계 (빨간 실선)
    for sp in ([boundary_polygon] if boundary_polygon.geom_type == "Polygon" else boundary_polygon.geoms):
        try:
            x, y = sp.exterior.xy
            ax.plot(x, y, color="red", lw=2.0, zorder=10)
        except Exception:
            pass

    # 표고 통계 텍스트 (좌상단)
    try:
        stat = f"최저 {e_min:.0f}m  최고 {e_max:.0f}m  평균 {analysis_result.get('mean_elev', 0):.0f}m"
        ax.text(0.02, 0.98, stat, transform=ax.transAxes,
                fontsize=10, va="top", ha="left",
                fontproperties=font_prop,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="gray", alpha=0.85))
    except Exception:
        pass

    # 방위표(N, 우상단 — 좌상단엔 표고통계) + 스케일바
    try:
        from modules.map_decorations import add_north_arrow, add_scale_bar
        add_north_arrow(ax, font_prop=font_prop, loc=(0.93, 0.90))
        add_scale_bar(ax, boundary_polygon, font_prop=font_prop)
    except Exception:
        pass

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=100, bbox_inches=None, pad_inches=0)
    plt.close(fig); buf.seek(0)

    # dpi=(72,72) 명시
    try:
        from PIL import Image
        img = Image.open(buf)
        out = io.BytesIO()
        img.save(out, format="PNG", dpi=(72, 72))
        out.seek(0)
        return out.getvalue()
    except Exception:
        buf.seek(0)
        return buf.getvalue()
