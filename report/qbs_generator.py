import io, os, math, requests
from pptx.util import Emu
from PIL import Image, ImageEnhance
import matplotlib.pyplot as plt
from pyproj import Transformer
from pptx import Presentation
from pptx.util import Inches, Pt, Cm
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from config import VWORLD_KEY, MAP_SOURCES, VWORLD_DOMAIN

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    return (int((lon_deg + 180.0) / 360.0 * n),
            int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n))

def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    return (math.degrees(lat_rad), lon_deg)

class QBSGenerator:
    def __init__(self, boundary_polygon, visible_layers):
        self.boundary_polygon = boundary_polygon
        self.visible_layers = visible_layers

    def fetch_pois(self, bbox_str, query):
        pois = []
        try:
            url = f"http://api.vworld.kr/req/search?service=search&request=search&version=2.0&crs=EPSG:4326&bbox={bbox_str}&type=PLACE&query={query}&key={VWORLD_KEY}&size=30&format=json"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if 'result' in data.get('response', {}):
                    pois = data['response']['result']['items']
        except Exception: pass
        return pois

    def _make_layer(self, ax, fig, exp_min_x, exp_max_x, exp_min_y, exp_max_y, SW, SH):
        """공통 레이어 마무리 → BytesIO 반환"""
        ax.set_xlim(exp_min_x, exp_max_x); ax.set_ylim(exp_min_y, exp_max_y); ax.axis('off')
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=200, pad_inches=0, transparent=True)
        plt.close(fig); buf.seek(0)
        return buf

    def _new_ax(self, SW, SH):
        """투명 배경의 새 matplotlib figure+axes 생성"""
        fig, ax = plt.subplots(figsize=(SW, SH), constrained_layout=True)
        fig.patch.set_alpha(0.0); ax.set_facecolor((1,1,1,0)); ax.set_position([0, 0, 1, 1])
        return fig, ax

    def generate(self):
        min_x, min_y, max_x, max_y = self.boundary_polygon.bounds
        cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2

        SW_CM, SH_CM = 11.5, 7.0
        SW, SH = SW_CM / 2.54, SH_CM / 2.54

        zoom = 13
        R_KM_Y = 6.0; R_KM_X = R_KM_Y * (SW_CM / SH_CM)
        lat_km = 111.32; lon_km = 111.32 * math.cos(math.radians(cy))
        dx, dy = R_KM_X / lon_km, R_KM_Y / lat_km
        eMinX, eMaxX, eMinY, eMaxY = cx - dx, cx + dx, cy - dy, cy + dy

        x0, y0 = deg2num(eMaxY, eMinX, zoom)
        x1, y1 = deg2num(eMinY, eMaxX, zoom)
        x0 -= 2; y0 -= 2; x1 += 2; y1 += 2
        nx, ny = x1 - x0 + 1, y1 - y0 + 1

        # ── 1. 배경지도 (Base → 그레이스케일 + 밝기보정) ──
        base = Image.new("RGBA", (nx*256, ny*256), (255,255,255,255))
        for i, x in enumerate(range(x0, x1+1)):
            for j, y in enumerate(range(y0, y1+1)):
                try:
                    r = requests.get(f"http://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/Base/{zoom}/{y}/{x}.png", timeout=5)
                    if r.status_code == 200:
                        base.paste(Image.open(io.BytesIO(r.content)).convert("RGBA"), (i*256, j*256))
                except Exception: pass
        iMaxLat, iMinLon = num2deg(x0, y0, zoom)
        iMinLat, iMaxLon = num2deg(x1+1, y1+1, zoom)
        ext = [iMinLon, iMaxLon, iMinLat, iMaxLat]

        plt.rcParams['font.family'] = 'Malgun Gothic'
        plt.rcParams['axes.unicode_minus'] = False
        layer_images = []

        # 배경지도 레이어 (원본 컬러 유지)
        fig, ax = self._new_ax(SW, SH)
        ax.imshow(base, extent=ext, origin='upper', aspect='auto')
        layer_images.append(("배경지도", self._make_layer(ax, fig, eMinX, eMaxX, eMinY, eMaxY, SW, SH)))

        # WMS 공통 파라미터
        wms_url = "http://api.vworld.kr/req/wms"
        bp = {"key": VWORLD_KEY, "domain": VWORLD_DOMAIN, "service": "WMS",
              "request": "GetMap", "version": "1.1.1", "srs": "EPSG:4326",
              "format": "image/png", "width": str(nx*256), "height": str(ny*256),
              "bbox": f"{iMinLon},{iMinLat},{iMaxLon},{iMaxLat}", "transparent": "true"}

        # 토지이용계획도 레이어 직접 추가 (항상 별도 객체로 포함)
        try:
            # 주요 후보 레이어 합치기 (토지이용계획 + 사업지구)
            target_layers = "LT_C_LHBLPN,LT_C_LHZONE"
            lup = bp.copy()
            lup.update({
                "layers": target_layers,
                "styles": target_layers,
                "transparent": "true",
                "bgcolor": "0xFFFFFF",
                "exceptions": "blank"
            })
            r_lup = requests.get(wms_url, params=lup, timeout=15)
            if r_lup.status_code == 200 and len(r_lup.content) > 1000: # 내용이 있는 경우만
                lup_img = Image.open(io.BytesIO(r_lup.content)).convert("RGBA")
                fig_lup, ax_lup = self._new_ax(SW, SH)
                # 시인성을 위해 투명도를 0.7로 약간 상향
                ax_lup.imshow(lup_img, extent=ext, origin='upper', alpha=0.7, aspect='auto')
                layer_images.append(("토지이용계획도", self._make_layer(ax_lup, fig_lup, eMinX, eMaxX, eMinY, eMaxY, SW, SH)))
        except Exception: pass

        # 기타 WMS 레이어 (토지이용계획도 제외 - 위에서 이미 처리)
        for sn, cats in MAP_SOURCES.items():
            if sn != "브이월드 (VWorld)": continue
            for cn, lyrs in cats.items():
                for nm, code in lyrs.items():
                    if (nm in self.visible_layers) and nm != "토지이용계획도" and "READY" not in str(code):
                        try:
                            a = 1.0
                            p = bp.copy(); p["layers"] = code.lower()
                            r = requests.get(wms_url, params=p, timeout=10)
                            if r.status_code == 200:
                                img = Image.open(io.BytesIO(r.content)).convert("RGBA")
                                fig2, ax2 = self._new_ax(SW, SH)
                                ax2.imshow(img, extent=ext, origin='upper', alpha=a, aspect='auto')
                                layer_images.append((nm, self._make_layer(ax2, fig2, eMinX, eMaxX, eMinY, eMaxY, SW, SH)))
                        except Exception: pass

        # ── 3. 인프라 레이어 (WFS) ──
        try:
            tp = Transformer.from_crs("EPSG:4326","EPSG:3857",always_xy=True)
            ti = Transformer.from_crs("EPSG:3857","EPSG:4326",always_xy=True)
            m0x, m0y = tp.transform(eMinX, eMinY)
            m1x, m1y = tp.transform(eMaxX, eMaxY)
            bb3857 = f"{m0x},{m0y},{m1x},{m1y}"

            def wfs_get(typename, maxf=2000):
                return requests.get("http://api.vworld.kr/req/wfs",
                    params={"key":VWORLD_KEY,"SERVICE":"WFS","version":"1.1.0",
                            "request":"GetFeature","TYPENAME":typename,
                            "BBOX":bb3857,"outputFormat":"application/json",
                            "maxFeatures":maxf}, timeout=15)

            def lines_from(feat):
                g = feat["geometry"]
                cs = g["coordinates"]
                return cs if g["type"] == "MultiLineString" else [cs]

            # 3-a) 고속도로 (별도 레이어)
            r = wfs_get("lt_l_highway", 1000)
            if r.status_code == 200:
                fig_h, ax_h = self._new_ax(SW, SH)
                for f in r.json().get("features",[]):
                    for ln in lines_from(f):
                        lons, lats = zip(*[ti.transform(p[0],p[1]) for p in ln])
                        ax_h.plot(lons, lats, color='white', lw=9, alpha=0.85, solid_capstyle='round')
                        ax_h.plot(lons, lats, color='#666666', lw=6, alpha=0.95, solid_capstyle='round')
                layer_images.append(("고속도로망", self._make_layer(ax_h, fig_h, eMinX, eMaxX, eMinY, eMaxY, SW, SH)))

            # 3-b) 국도/주요도로 (별도 레이어)
            fig_r, ax_r = self._new_ax(SW, SH)
            for tn in ["lt_l_natlroad","lt_l_moctlink"]:
                r = wfs_get(tn, 5000)
                if r.status_code == 200:
                    for f in r.json().get("features",[]):
                        rk = f.get("properties",{}).get("rd_rank_h","")
                        major = tn == "lt_l_natlroad" or "일반" in rk
                        c, w = ("#777777", 5.0) if major else ("#BBBBBB", 2.0)
                        for ln in lines_from(f):
                            lons, lats = zip(*[ti.transform(p[0],p[1]) for p in ln])
                            if major:
                                ax_r.plot(lons, lats, color='white', lw=w+3, alpha=0.7, solid_capstyle='round')
                            ax_r.plot(lons, lats, color=c, lw=w, alpha=0.85, solid_capstyle='round')
            layer_images.append(("국도/주요도로", self._make_layer(ax_r, fig_r, eMinX, eMaxX, eMinY, eMaxY, SW, SH)))

            # 3-c) 철도망 (별도 레이어)
            r = wfs_get("lt_l_frstrail", 1000)
            if r.status_code == 200:
                fig_t, ax_t = self._new_ax(SW, SH)
                for f in r.json().get("features",[]):
                    for ln in lines_from(f):
                        lons, lats = zip(*[ti.transform(p[0],p[1]) for p in ln])
                        ax_t.plot(lons, lats, color='white', lw=5, alpha=0.7, solid_capstyle='round')
                        ax_t.plot(lons, lats, color='#444444', lw=2.5, alpha=0.9, solid_capstyle='round', ls='--')
                layer_images.append(("철도망", self._make_layer(ax_t, fig_t, eMinX, eMaxX, eMinY, eMaxY, SW, SH)))

            # 3-d) 하천망 (별도 레이어)
            r = wfs_get("lt_c_wkmstrm", 1000)
            if r.status_code == 200:
                fig_w, ax_w = self._new_ax(SW, SH)
                for f in r.json().get("features",[]):
                    g = f["geometry"]
                    polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
                    for poly in polys:
                        ring = poly[0] if isinstance(poly[0][0], list) else poly
                        lons, lats = zip(*[ti.transform(p[0],p[1]) for p in ring])
                        ax_w.fill(lons, lats, color='#B0D4F1', alpha=0.5)
                        ax_w.plot(lons, lats, color='#7EB8DA', lw=0.8, alpha=0.7)
                layer_images.append(("하천망", self._make_layer(ax_w, fig_w, eMinX, eMaxX, eMinY, eMaxY, SW, SH)))
        except Exception: pass

        # ── 4. PPT 생성 ──
        prs = Presentation()
        prs.slide_width, prs.slide_height = Cm(SW_CM), Cm(SH_CM)
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        for nm, buf in layer_images:
            slide.shapes.add_picture(buf, 0, 0, width=Cm(SW_CM), height=Cm(SH_CM))

        # 사업구역계 (최상단)
        empty = Image.new("RGBA", (nx*256, ny*256), (255,255,255,0))
        fig_p, ax_p = self._new_ax(SW, SH)
        ax_p.imshow(empty, extent=ext, origin='upper', aspect='auto', alpha=0)
        for sp in ([self.boundary_polygon] if self.boundary_polygon.geom_type == 'Polygon' else self.boundary_polygon.geoms):
            bx, by = sp.exterior.xy
            ax_p.plot(bx, by, color='black', lw=1.5, zorder=10)
            ax_p.fill(bx, by, color='#888888', alpha=0.4, zorder=9)
        slide.shapes.add_picture(
            self._make_layer(ax_p, fig_p, eMinX, eMaxX, eMinY, eMaxY, SW, SH),
            0, 0, width=Cm(SW_CM), height=Cm(SH_CM))

        # ── 5. PPT 도형/텍스트 ──
        cpx, cpy = Cm(SW_CM)/2, Cm(SH_CM)/2
        from pptx.oxml import parse_xml
        def glow(run):
            # 텍스트에 실제 하얀색 테두리(Outline) 적용
            xml = """<a:ln w="25400" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
                <a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>
                <a:round/><a:headEnd/><a:tailEnd/>
            </a:ln>"""
            run._r.get_or_add_rPr().append(parse_xml(xml))
            # 가독성을 위해 그림자나 글로우도 살짝 보강
            run._r.get_or_add_rPr().append(parse_xml(
                '<a:effectLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                '<a:glow rad="30000"><a:srgbClr val="FFFFFF"/></a:glow></a:effectLst>'))

        # 반경원 + km 텍스트
        for r_km in [1,2,3,4,5]:
            rpx = Cm(SH_CM) * (r_km / (R_KM_Y * 2))
            sh = slide.shapes.add_shape(MSO_SHAPE.OVAL, cpx-rpx, cpy-rpx, rpx*2, rpx*2)
            sh.fill.background(); sh.line.color.rgb = RGBColor(120,120,120); sh.line.width = Pt(0.75)
            if r_km % 2 == 1: sh.line.dash_style = 4
            tb = slide.shapes.add_textbox(cpx-rpx-Cm(1.2), cpy-Cm(0.4), Cm(2.4), Cm(0.8))
            tb.text_frame.margin_left = Emu(0); tb.text_frame.margin_right = Emu(0)
            tb.text_frame.margin_top = Emu(0); tb.text_frame.margin_bottom = Emu(0)
            r = tb.text_frame.paragraphs[0].add_run()
            r.text = f"{r_km}km"; r.font.size = Pt(6); r.font.bold = True; r.font.color.rgb = RGBColor(0,0,0); r.font.name = '맑은 고딕'
            tb.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER; glow(r)

        # 사업대상지 라벨
        tb = slide.shapes.add_textbox(cpx-Cm(1.5), cpy-Cm(0.8), Cm(3.0), Cm(1.0))
        tb.text_frame.margin_left = Emu(0); tb.text_frame.margin_right = Emu(0)
        tb.text_frame.margin_top = Emu(0); tb.text_frame.margin_bottom = Emu(0)
        r = tb.text_frame.paragraphs[0].add_run()
        r.text = "사업대상지"; r.font.size = Pt(9); r.font.bold = True; r.font.color.rgb = RGBColor(0,0,0); r.font.name = '맑은 고딕'
        tb.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER; glow(r)

        # ── 6. 지도 내 텍스트를 PPT 텍스트로 ──
        bbox_str = f"{eMinX},{eMinY},{eMaxX},{eMaxY}"
        drawn = set()

        def add_poi_text(query, color, font_sz, strip_words=None, icon_type=None):
            pois = self.fetch_pois(bbox_str, query)
            for poi in pois:
                title = poi['title']
                if strip_words:
                    for w in strip_words: title = title.replace(w, "")
                title = title.strip()
                if not title or title in drawn or len(title) > 10: continue
                lon, lat = float(poi['point']['x']), float(poi['point']['y'])
                px = (lon - eMinX) / (eMaxX - eMinX) * SW
                py = (eMaxY - lat) / (eMaxY - eMinY) * SH
                if 0.3 < px < (SW-0.3) and 0.3 < py < (SH-0.3):
                    # 아이콘 (산 삼각형, IC/JC 사각형 등)
                    if icon_type == "mountain":
                        ic = slide.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE,
                            Inches(px)-Inches(0.04), Inches(py)-Inches(0.04), Inches(0.1), Inches(0.08))
                        ic.fill.solid(); ic.fill.fore_color.rgb = RGBColor(34,139,34)
                        ic.line.fill.background()
                    elif icon_type == "ic_jc":
                        tag = "IC" if "IC" in poi['title'] or "인터체인지" in poi['title'] else "JC"
                        ic = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                            Inches(px)-Inches(0.06), Inches(py)-Inches(0.04), Inches(0.12), Inches(0.08))
                        ic.fill.solid(); ic.fill.fore_color.rgb = RGBColor(255,140,0)
                        ic.line.fill.background()
                        # IC/JC 라벨 (여백 0)
                        ic.text_frame.margin_left = Emu(0); ic.text_frame.margin_right = Emu(0)
                        ic.text_frame.margin_top = Emu(0); ic.text_frame.margin_bottom = Emu(0)
                        ri = ic.text_frame.paragraphs[0].add_run()
                        ri.text = tag; ri.font.size = Pt(4); ri.font.bold = True
                        ri.font.color.rgb = RGBColor(255,255,255); ri.font.name = '맑은 고딕'
                        ic.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
                    elif icon_type == "station":
                        ic = slide.shapes.add_shape(MSO_SHAPE.OVAL,
                            Inches(px)-Inches(0.03), Inches(py)-Inches(0.03), Inches(0.06), Inches(0.06))
                        ic.fill.solid(); ic.fill.fore_color.rgb = RGBColor(255,255,255)
                        ic.line.color.rgb = RGBColor(80,80,80); ic.line.width = Pt(0.5)
                    # 텍스트 상자를 글자 길이에 맞춤 (불필요한 여백 제거)
                    char_w = Cm(0.35) if font_sz <= Pt(6.5) else Cm(0.4)
                    box_w = int(char_w * len(title) + Cm(0.15))
                    box_h = Cm(0.45)
                    tx = slide.shapes.add_textbox(Inches(px)+Inches(0.06), Inches(py)-Inches(0.04), box_w, box_h)
                    tx.text_frame.margin_left = Emu(0); tx.text_frame.margin_right = Emu(0)
                    tx.text_frame.margin_top = Emu(0); tx.text_frame.margin_bottom = Emu(0)
                    tx.text_frame.word_wrap = False
                    tx.text_frame.auto_size = MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT
                    rn = tx.text_frame.paragraphs[0].add_run()
                    rn.text = title; rn.font.size = font_sz; rn.font.bold = True
                    rn.font.color.rgb = color; rn.font.name = '맑은 고딕'; glow(rn)
                    drawn.add(title)

        # IC / JC
        add_poi_text("인터체인지", RGBColor(80,80,80), Pt(6), ["인터체인지","IC ","ic "], "ic_jc")
        add_poi_text("JC", RGBColor(80,80,80), Pt(6), None, "ic_jc")
        # 역 (지하철/기차)
        add_poi_text("역", RGBColor(60,60,60), Pt(6.5), ["지하철"], "station")
        # 산
        add_poi_text("산", RGBColor(34,139,34), Pt(7), None, "mountain")

        out = io.BytesIO(); prs.save(out); out.seek(0)
        return out.getvalue()
