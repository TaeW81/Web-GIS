"""
소유자 구분도 생성기 — 두 가지 출력 포맷

1) PNG ZIP (기존): 소유자별 PNG 한 장 + ZIP 묶음
2) DXF ZIP (신규): 소유자별 DXF 한 파일 + ZIP 묶음
   - 해당 소유자 필지 → 색상 외곽 + HATCH 채움 (빗금 패턴)
   - 그 외 필지 → 회색 외곽선만
   - 구역계 → 빨간 굵은 외곽선
   - CAD/QGIS에서 바로 열어 편집 가능

API:
    gen = FreeTransferGenerator(boundary_polygon, land_data)
    zip_png = gen.generate()                    # 기존 PNG ZIP
    zip_dxf = gen.generate_dxf(target_epsg="EPSG:5186")  # 신규 DXF ZIP
"""
import io
import os
import re
import zipfile
import tempfile
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from PIL import Image
import requests
import ezdxf
from pyproj import Transformer
from config import VWORLD_KEY, VWORLD_DOMAIN


class FreeTransferGenerator:
    # 소유자 카테고리별 AutoCAD Color Index (ACI)
    #   ⚠️ BOUNDARY(1=빨강), OTHER_PARCEL(8=진회색), 라벨(7=흰/검)과 안 겹치게 선정
    #   첫 매칭 우선 (구체적 → 일반 순서)
    OWNER_COLOR_MAP = [
        ("국유지", 5),         # 파랑
        ("공유지", 6),         # 자홍
        ("군유지", 30),        # 주황 (공유지와 구분)
        ("시  도유지", 140),   # 진청 (공백 두 칸 포함, NED 원본)
        ("도유지", 140),
        ("시유지", 140),
        ("종중", 200),         # 분홍/자주
        ("기타단체", 4),       # 청록
        ("공공기관", 170),     # 보라
        ("법인", 3),           # 초록
        ("개인", 2),           # 노랑
    ]
    DEFAULT_OWNER_COLOR = 130  # 진청자 (매핑 안 되는 소유자)

    @classmethod
    def _get_owner_color(cls, owner_name):
        """소유자 이름 → ACI 색 번호 반환. BOUNDARY/OTHER_PARCEL 색은 피함."""
        if not owner_name:
            return cls.DEFAULT_OWNER_COLOR
        for keyword, color in cls.OWNER_COLOR_MAP:
            if keyword in owner_name:
                return color
        return cls.DEFAULT_OWNER_COLOR

    def __init__(self, boundary_polygon, land_data):
        self.boundary_polygon = boundary_polygon
        self.land_data = land_data
        try:
            self.font_prop = FontProperties(fname="C:/Windows/Fonts/malgun.ttf")
        except Exception:
            self.font_prop = None

    # ─────────────────────────────────────────────────────────────
    # 공통 — 소유자별 필지 그룹화
    # ─────────────────────────────────────────────────────────────
    def _group_by_owner(self):
        owners = {}
        for p in self.land_data:
            owner = p.get("analysis_attr", {}).get("소유자", "미확인")
            owners.setdefault(owner, []).append(p)
        return owners

    @staticmethod
    def _safe_filename(name):
        """Windows/Mac 안전 파일명."""
        name = re.sub(r'[<>:"/\\|?*\t\n\r ]+', "_", str(name)).strip("._")
        return name or "미확인"

    # ═════════════════════════════════════════════════════════════
    # [1] PNG ZIP 생성 (기존)
    # ═════════════════════════════════════════════════════════════
    def generate(self):
        owners_map = self._group_by_owner()
        if not owners_map:
            return None

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for owner_name, parcels in owners_map.items():
                img_data = self._create_owner_map(owner_name, parcels)
                if img_data:
                    safe_name = self._safe_filename(owner_name)
                    zf.writestr(f"소유자_구분도_{safe_name}.png", img_data.getvalue())

        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    def _create_owner_map(self, owner_name, owner_parcels):
        """특정 소유자의 필지들을 강조한 PNG 지도."""
        try:
            plt.rcParams["font.family"] = "Malgun Gothic"
            plt.rcParams["axes.unicode_minus"] = False

            min_x, min_y, max_x, max_y = self.boundary_polygon.bounds
            width = max_x - min_x; height = max_y - min_y
            exp_min_x = min_x - width * 0.1; exp_max_x = max_x + width * 0.1
            exp_min_y = min_y - height * 0.1; exp_max_y = max_y + height * 0.1

            wms_url = "http://api.vworld.kr/req/wms"
            params = {
                "key": VWORLD_KEY, "domain": VWORLD_DOMAIN,
                "service": "WMS", "request": "GetMap", "layers": "Satellite",
                "crs": "EPSG:4326", "format": "image/png", "width": "1200", "height": "1200",
                "bbox": f"{exp_min_x},{exp_min_y},{exp_max_x},{exp_max_y}",
            }
            res = requests.get(wms_url, params=params, timeout=15)
            bg_img = Image.open(io.BytesIO(res.content))

            fig, ax = plt.subplots(figsize=(12, 12))
            ax.imshow(bg_img, extent=[exp_min_x, exp_max_x, exp_min_y, exp_max_y], origin="upper")

            for p in self.land_data:
                poly = p.get("지적도형")
                if not poly: continue
                is_target = p in owner_parcels
                color = "#FFD700" if is_target else "#FFFFFF"
                alpha = 0.7 if is_target else 0.2
                zorder = 6 if is_target else 5
                lw = 1.5 if is_target else 0.5
                edge_color = "red" if is_target else "white"
                for sub_poly in ([poly] if poly.geom_type == "Polygon" else poly.geoms):
                    px, py = sub_poly.exterior.xy
                    ax.fill(px, py, color=color, alpha=alpha, edgecolor=edge_color, lw=lw, zorder=zorder)

            for sub_poly in ([self.boundary_polygon] if self.boundary_polygon.geom_type == "Polygon" else self.boundary_polygon.geoms):
                bx, by = sub_poly.exterior.xy
                ax.plot(bx, by, color="red", lw=2, zorder=10, linestyle="--")

            plt.title(f"소유자별 토지 구분도 [{owner_name}]",
                      fontproperties=self.font_prop, fontsize=20, pad=20)
            info_text = f"소유자: {owner_name}\n대상 필지수: {len(owner_parcels)}필지"
            plt.text(exp_min_x + width * 0.02, exp_min_y + height * 0.02, info_text,
                     fontproperties=self.font_prop, fontsize=12,
                     bbox=dict(facecolor="white", alpha=0.8, edgecolor="gray"))

            ax.set_xlim(exp_min_x, exp_max_x); ax.set_ylim(exp_min_y, exp_max_y)
            ax.set_aspect("equal"); ax.axis("off")
            buf = io.BytesIO()
            plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", pad_inches=0.1)
            plt.close(fig); buf.seek(0)
            return buf
        except Exception as e:
            print(f"PNG owner map error: {e}")
            return None

    # ═════════════════════════════════════════════════════════════
    # [2] DXF ZIP 생성 (신규) — 소유자별 파일 + 해치 구분
    # ═════════════════════════════════════════════════════════════
    def generate_dxf(self, target_epsg="EPSG:5186"):
        """소유자별 DXF 파일을 생성해 ZIP으로 묶어 반환.

        Args:
            target_epsg: DXF 출력 좌표계 (기본 EPSG:5186 GRS80 중부).
                         사용자 도면 좌표계와 맞춰야 호환됨.

        Returns:
            bytes: ZIP 바이너리 (각 소유자별 .dxf 파일 포함)
        """
        owners_map = self._group_by_owner()
        if not owners_map:
            return None

        # WGS84 → 사용자 좌표계 변환기
        try:
            transformer = Transformer.from_crs("EPSG:4326", target_epsg, always_xy=True)
        except Exception as e:
            raise ValueError(f"좌표계 변환 실패 {target_epsg}: {e}")

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # 소유자별로 DXF 생성
            for owner_name, target_parcels in owners_map.items():
                dxf_bytes = self._create_owner_dxf(owner_name, target_parcels, transformer)
                if dxf_bytes:
                    safe_name = self._safe_filename(owner_name)
                    zf.writestr(f"소유자_구분_{safe_name}.dxf", dxf_bytes)

            # README 추가 (사용 안내)
            zf.writestr("README.txt", self._dxf_readme(target_epsg, owners_map))

        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    def _create_owner_dxf(self, owner_name, target_parcels, transformer):
        """한 소유자의 DXF 생성.

        레이어 구조:
          BOUNDARY        : 구역계 외곽 (빨강, 굵은 선)
          TARGET_PARCEL   : 대상 소유자 필지 외곽 (밝은 노랑)
          TARGET_HATCH    : 대상 소유자 필지 해치 (ANSI31 빗금)
          OTHER_PARCEL    : 그 외 필지 외곽 (회색 가는 선)
          LABEL           : 텍스트 (소유자명, 지번 등)
        """
        try:
            doc = ezdxf.new(dxfversion="R2010", setup=True)
            msp = doc.modelspace()

            # ★ 소유자 카테고리별 ACI 색 (BOUNDARY=1, OTHER_PARCEL=8 회피)
            owner_color = self._get_owner_color(owner_name)

            # 레이어 설정 (AutoCAD 색번호)
            doc.layers.add(name="BOUNDARY", color=1, lineweight=50)                 # 빨강 굵게
            doc.layers.add(name="TARGET_PARCEL", color=owner_color, lineweight=25)  # 소유자별 색
            doc.layers.add(name="TARGET_HATCH", color=owner_color)                  # 소유자별 색 해치
            doc.layers.add(name="TARGET_LABEL", color=7)                            # 대상 지번 (흰/검정 강조)
            doc.layers.add(name="OTHER_PARCEL", color=8, lineweight=13)             # 진회색 얇게
            doc.layers.add(name="OTHER_LABEL", color=8)                             # 그 외 지번 (옅은 회색)

            # 텍스트 스타일
            if "맑은고딕" not in doc.styles:
                try:
                    doc.styles.add("맑은고딕", font="malgun.ttf")
                except Exception:
                    pass

            target_ids = {id(p) for p in target_parcels}

            # 1. 모든 필지 그리기 (사업지 내/외 무관 — 인근 지적도 함께 표시)
            for p in self.land_data:
                poly = p.get("지적도형")
                if not poly: continue
                is_target = id(p) in target_ids
                layer = "TARGET_PARCEL" if is_target else "OTHER_PARCEL"

                from shapely.geometry import Polygon as _Polygon, MultiPolygon as _MultiPolygon
                for sub_poly in ([poly] if poly.geom_type == "Polygon" else poly.geoms):
                    if sub_poly.is_empty or sub_poly.area <= 0:
                        continue
                    # 외곽선 (원본 필지 그대로 — 사업지 내/외 모두 표시)
                    pts = [transformer.transform(x, y) for x, y in sub_poly.exterior.coords]
                    if len(pts) < 3:
                        continue
                    msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})

                    # 대상 소유자 필지 — solid 해치는 사업지 경계 안쪽 부분에만 적용
                    if is_target:
                        try:
                            clipped = sub_poly.intersection(self.boundary_polygon)
                        except Exception:
                            clipped = None
                        if clipped is None or clipped.is_empty:
                            continue  # 사업지와 교차 없으면 해치 안 그림

                        # Polygon / MultiPolygon / GeometryCollection 처리 후 Polygon만 평탄화
                        if clipped.geom_type == "Polygon":
                            clip_parts = [clipped]
                        elif clipped.geom_type == "MultiPolygon":
                            clip_parts = list(clipped.geoms)
                        elif clipped.geom_type == "GeometryCollection":
                            clip_parts = []
                            for g in clipped.geoms:
                                if g.geom_type == "Polygon":
                                    clip_parts.append(g)
                                elif g.geom_type == "MultiPolygon":
                                    clip_parts.extend(list(g.geoms))
                        else:
                            clip_parts = []

                        for cp in clip_parts:
                            if cp.is_empty or cp.area <= 0:
                                continue
                            hatch_pts = [transformer.transform(x, y) for x, y in cp.exterior.coords]
                            if len(hatch_pts) < 3:
                                continue
                            try:
                                hatch = msp.add_hatch(color=owner_color, dxfattribs={"layer": "TARGET_HATCH"})
                                hatch.set_solid_fill(color=owner_color)
                                hatch.paths.add_polyline_path(hatch_pts, is_closed=True)
                                for interior in cp.interiors:
                                    hole_pts = [transformer.transform(x, y) for x, y in interior.coords]
                                    if len(hole_pts) >= 3:
                                        hatch.paths.add_polyline_path(hole_pts, is_closed=True, flags=0)
                            except Exception as he:
                                print(f"  해치 생성 실패 (PNU {p.get('PNU')}): {he}")

                    # 지번 지목 라벨 — TARGET/OTHER 둘 다 표시 (레이어로 구분)
                    #   토지조서의 본번/부번/필지구분 컬럼을 사용해 지번 직접 구성.
                    #   소재지(분석결과)는 clean_address로 끝의 지번이 제거된 행정구역만 남으므로 사용 불가.
                    attr = p.get("analysis_attr", {}) or {}
                    bonbun = str(attr.get("본번", "") or "0").strip()
                    bubun = str(attr.get("부번", "") or "0").strip()
                    pungu = str(attr.get("필지구분", "") or "").strip()  # "일반" or "산"
                    jimok = str(attr.get("지목", "") or "").strip()

                    if bonbun and bonbun != "0":
                        jibun = f"{bonbun}-{bubun}" if (bubun and bubun != "0") else bonbun
                        if pungu == "산":
                            jibun = f"산 {jibun}"
                    else:
                        jibun = ""

                    # 괄호 없이 "지번 지목" 형식 (예: "산 100 임", "100-2 전")
                    parts_lbl = [v for v in (jibun, jimok) if v]
                    label_text = " ".join(parts_lbl)

                    if label_text:
                        # 레이어와 높이를 TARGET/OTHER에 따라 다르게
                        if is_target:
                            label_layer = "TARGET_LABEL"
                            label_height = 2.5      # 강조 (큼)
                        else:
                            label_layer = "OTHER_LABEL"
                            label_height = 1.8      # 보조 (작음)

                        centroid = sub_poly.centroid
                        cx, cy = transformer.transform(centroid.x, centroid.y)
                        msp.add_text(
                            label_text,
                            dxfattribs={
                                "layer": label_layer,
                                "height": label_height,
                                "style": "맑은고딕" if "맑은고딕" in doc.styles else "Standard",
                            },
                        ).set_placement((cx, cy))

            # 2. 구역계 외곽
            polys_bd = ([self.boundary_polygon] if self.boundary_polygon.geom_type == "Polygon"
                        else list(self.boundary_polygon.geoms))
            for sub in polys_bd:
                pts = [transformer.transform(x, y) for x, y in sub.exterior.coords]
                msp.add_lwpolyline(pts, close=True, dxfattribs={"layer": "BOUNDARY"})

            # 3. 소유자 라벨 (구역계 좌상단 위)
            try:
                min_x, min_y, max_x, max_y = self.boundary_polygon.bounds
                lx, ly = transformer.transform(min_x, max_y)
                title_text = f"소유자: {owner_name} ({len(target_parcels)}필지)"
                msp.add_text(
                    title_text,
                    dxfattribs={
                        "layer": "TARGET_LABEL",
                        "height": 8.0,
                        "style": "맑은고딕" if "맑은고딕" in doc.styles else "Standard",
                    },
                ).set_placement((lx, ly + 30))
            except Exception:
                pass

            # 4. DXF를 바이트로 저장 (ezdxf는 텍스트 모드만 지원 → 임시파일 경유)
            with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tmp:
                tmp_path = tmp.name
            try:
                doc.saveas(tmp_path)
                with open(tmp_path, "rb") as f:
                    return f.read()
            finally:
                try: os.unlink(tmp_path)
                except Exception: pass

        except Exception as e:
            print(f"DXF owner map error ({owner_name}): {e}")
            import traceback; traceback.print_exc()
            return None

    @staticmethod
    def _extract_jibun(addr):
        """소재지 텍스트에서 지번 부분만 추출 (예: '경기도 광명시 가학동 산100-2' → '산100-2')."""
        if not addr: return ""
        parts = str(addr).strip().split()
        # 마지막 토큰이 보통 지번
        last = parts[-1] if parts else ""
        # 숫자나 '산' 포함 시 지번으로 간주
        if any(c.isdigit() for c in last) or last.startswith("산"):
            return last
        return ""

    @staticmethod
    def _dxf_readme(target_epsg, owners_map):
        lines = [
            "═══════════════════════════════════════════════════════",
            "  소유자 구분도 (DXF 패키지)",
            "═══════════════════════════════════════════════════════",
            "",
            f"좌표계: {target_epsg}",
            f"총 소유자 수: {len(owners_map)}명",
            f"총 필지 수: {sum(len(p) for p in owners_map.values())}개",
            "",
            "── 파일 구성 ──",
        ]
        for owner, parcels in sorted(owners_map.items(),
                                     key=lambda x: -len(x[1])):
            safe = re.sub(r'[<>:"/\\|?*]+', "_", owner)
            lines.append(f"  소유자_구분_{safe}.dxf  ({len(parcels)}필지)")
        lines += [
            "",
            "── DXF 레이어 구조 ──",
            "  BOUNDARY      : 구역계 (빨강, 굵게)",
            "  TARGET_PARCEL : 대상 소유자 필지 외곽 (소유자 카테고리별 색)",
            "  TARGET_HATCH  : 대상 소유자 필지 Solid 해치 (소유자 카테고리별 색)",
            "  TARGET_LABEL  : 대상 소유자 지번/지목 (강조 — 큰 글씨)",
            "  OTHER_PARCEL  : 그 외 필지 외곽 (회색)",
            "  OTHER_LABEL   : 그 외 지번/지목 (회색 — 작은 글씨)",
            "",
            "── 소유자별 해치 색상 (ACI 색번호) ──",
            "  개인         : 2  (노랑)",
            "  법인         : 3  (초록)",
            "  공공기관     : 170 (보라)",
            "  기타단체     : 4  (청록)",
            "  국유지       : 5  (파랑)",
            "  공유지       : 6  (자홍)",
            "  군유지       : 30  (주황)",
            "  시·도유지    : 140 (진청)",
            "  종중         : 200 (분홍)",
            "  기타         : 130 (진청자)",
            "  ※ 구역계(1=빨강), 지적 외곽(8=진회색)과 겹치지 않게 선정",
            "",
            "── 처리 규칙 ──",
            "  • 외곽선: 사업지 내부 + 인근 외부 필지까지 모두 표시 (clipping 없음)",
            "  • Solid 해치: 대상 소유자 필지의 사업지 경계 안쪽 부분에만 채움",
            "    (사업지 경계에 걸친 필지는 안쪽만 해치, 외곽선은 전체 표시)",
            "  • 라벨 형식: '지번 지목' (괄호 없음) — 예: '산 100 임'",
            "  • TARGET_LABEL(강조) / OTHER_LABEL(보조) 레이어로 라벨 토글 가능",
            "",
            "AutoCAD/CAD 시스템/QGIS 등에서 직접 열어 편집할 수 있습니다.",
        ]
        return "\n".join(lines)
