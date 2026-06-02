"""
삽도 공통 장식 — 방위표(N) + 스케일바

matplotlib Axes에 추가하는 헬퍼.
표고 분석도 / 소유자별 현황도 등 보고서 삽도에 공통 사용.
좌표계: EPSG:4326 (lon/lat) 가정.
"""
from __future__ import annotations
import math


def add_north_arrow(ax, font_prop=None, loc=(0.06, 0.90), size=0.06):
    """좌상단 방위표(N 화살표) 추가. loc/size는 axes fraction(0~1).
    (범례는 보통 우상단이므로 방위표는 좌상단에 배치하여 겹침 방지)"""
    x, y = loc
    # 화살표 (아래→위)
    ax.annotate(
        "", xy=(x, y + size), xytext=(x, y - size * 0.4),
        xycoords="axes fraction",
        arrowprops=dict(facecolor="black", edgecolor="black",
                        width=2.5, headwidth=11, headlength=11),
        zorder=20,
    )
    # 'N' 글자
    ax.text(x, y + size + 0.025, "N", transform=ax.transAxes,
            ha="center", va="center", fontsize=14, fontweight="bold",
            color="black", zorder=21, fontproperties=font_prop)


def add_scale_bar(ax, boundary_polygon, font_prop=None,
                  loc=(0.05, 0.06), max_frac=0.28):
    """좌하단 스케일바 추가. 실제 거리(m/km)를 막대로 표시.

    Args:
        ax: matplotlib Axes (xlim/ylim이 lon/lat로 설정되어 있어야)
        boundary_polygon: 거리 계산 기준 (위도 추출용)
        loc: 스케일바 좌하단 시작점 (axes fraction)
        max_frac: 스케일바 최대 가로 길이 (axes 폭 대비 비율)
    """
    try:
        from pyproj import Geod
        geod = Geod(ellps="WGS84")

        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
        view_w_deg = xmax - xmin
        lat_mid = (ymin + ymax) / 2.0

        # view 폭의 max_frac 에 해당하는 실제 거리(m)
        # geod.inv 반환: (정방위각, 역방위각, 거리) → 세 번째가 거리
        _, _, full_dist_m = geod.inv(xmin, lat_mid, xmin + view_w_deg, lat_mid)
        full_dist_m = abs(full_dist_m)
        target_m = full_dist_m * max_frac

        # 깔끔한 눈금 거리 선택 (1,2,5 × 10^n)
        nice = _nice_round(target_m)
        # nice 거리에 해당하는 deg 폭
        bar_deg = view_w_deg * (nice / full_dist_m) if full_dist_m > 0 else 0
        if bar_deg <= 0:
            return

        # 막대 위치 (데이터 좌표로 변환)
        x0 = xmin + (xmax - xmin) * loc[0]
        y0 = ymin + (ymax - ymin) * loc[1]
        x1 = x0 + bar_deg
        bar_h = (ymax - ymin) * 0.012

        # 흑백 교대 막대 (2분할)
        mid = (x0 + x1) / 2
        ax.add_patch(_rect(x0, y0, mid - x0, bar_h, "black"))
        ax.add_patch(_rect(mid, y0, x1 - mid, bar_h, "white", edge="black"))
        # 외곽선
        ax.add_patch(_rect(x0, y0, x1 - x0, bar_h, "none", edge="black"))

        # 라벨 (0, 중간, 끝)
        label = _fmt_dist(nice)
        label_mid = _fmt_dist(nice / 2)
        ax.text(x0, y0 + bar_h * 1.6, "0", ha="center", va="bottom",
                fontsize=8.5, fontproperties=font_prop, zorder=21)
        ax.text(mid, y0 + bar_h * 1.6, label_mid, ha="center", va="bottom",
                fontsize=8.5, fontproperties=font_prop, zorder=21)
        ax.text(x1, y0 + bar_h * 1.6, label, ha="center", va="bottom",
                fontsize=8.5, fontproperties=font_prop, zorder=21)
    except Exception as e:
        try:
            print(f"[map_decorations] scale_bar 실패: {e}")
        except Exception:
            pass


def _nice_round(value):
    """1, 2, 5 × 10^n 중 value에 가장 가까운(작거나 같은) 깔끔한 수."""
    if value <= 0:
        return 1
    exp = math.floor(math.log10(value))
    base = 10 ** exp
    for mult in (5, 2, 1):
        if base * mult <= value:
            return base * mult
    return base


def _fmt_dist(m):
    """미터 → 'XXm' 또는 'X.Xkm'."""
    if m >= 1000:
        km = m / 1000
        return f"{km:g}km"
    return f"{int(round(m))}m"


def _rect(x, y, w, h, fc, edge="none"):
    from matplotlib.patches import Rectangle
    return Rectangle((x, y), w, h, facecolor=fc, edgecolor=edge,
                     linewidth=0.8, zorder=20)
