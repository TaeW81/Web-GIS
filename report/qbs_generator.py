import io
import os
import math
import copy
import requests
from PIL import Image
import matplotlib.pyplot as plt
from pyproj import Transformer
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from config import VWORLD_KEY, MAP_SOURCES, VWORLD_DOMAIN

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)

class QBSGenerator:
    def __init__(self, boundary_polygon, visible_layers):
        self.boundary_polygon = boundary_polygon
        self.visible_layers = visible_layers

    def fetch_pois(self, bbox_str, query):
        """VWorld Search API를 사용하여 POI 정보를 가져옵니다."""
        pois = []
        try:
            url = f"https://api.vworld.kr/req/search?service=search&request=search&version=2.0&crs=EPSG:4326&bbox={bbox_str}&type=PLACE&query={query}&key={VWORLD_KEY}&size=20&format=json"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if 'result' in data.get('response', {}):
                    pois = data['response']['result']['items']
        except Exception as e:
            print(f"POI 검색 실패 ({query}):", e)
        return pois

    def generate(self):
        min_x, min_y, max_x, max_y = self.boundary_polygon.bounds
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        
        # 반경 y축은 6km, x축은 16:9 비율에 맞춰 약 10.66km 커버하도록 설정
        zoom = 13
        radius_km_y = 6.0
        radius_km_x = 6.0 * (13.333 / 7.5)
        
        lat_km = 111.32
        lon_km = 111.32 * math.cos(math.radians(center_y))
        dx = radius_km_x / lon_km
        dy = radius_km_y / lat_km
        
        exp_min_x = center_x - dx
        exp_max_x = center_x + dx
        exp_min_y = center_y - dy
        exp_max_y = center_y + dy
        
        # 타일 인덱스 계산
        x_min_tile, y_max_tile = deg2num(exp_min_y, exp_min_x, zoom)
        x_max_tile, y_min_tile = deg2num(exp_max_y, exp_max_x, zoom)
        
        num_x = x_max_tile - x_min_tile + 1
        num_y = y_max_tile - y_min_tile + 1
        
        # 1. 배경지도 타일 병합 (백지도)
        bg_img = Image.new("RGBA", (num_x * 256, num_y * 256), (255, 255, 255, 0)) # 투명하게 시작
        base_tiles = Image.new("RGBA", (num_x * 256, num_y * 256), (255, 255, 255, 255))
        for i, x in enumerate(range(x_min_tile, x_max_tile + 1)):
            for j, y in enumerate(range(y_min_tile, y_max_tile + 1)):
                url = f"https://api.vworld.kr/req/wmts/1.0.0/{VWORLD_KEY}/white/{zoom}/{y}/{x}.png"
                try:
                    res = requests.get(url, timeout=5)
                    if res.status_code == 200:
                        tile = Image.open(io.BytesIO(res.content)).convert("RGBA")
                        base_tiles.paste(tile, (i * 256, j * 256))
                except Exception: pass
                    
        img_max_lat, img_min_lon = num2deg(x_min_tile, y_min_tile, zoom)
        img_min_lat, img_max_lon = num2deg(x_max_tile + 1, y_max_tile + 1, zoom)
        
        # PPT에 담을 레이어 이미지 리스트
        layer_images = []
        
        plt.rcParams['font.family'] = 'Malgun Gothic'
        plt.rcParams['axes.unicode_minus'] = False
        
        def pil_to_buf(img, draw_polygon=False):
            fig, ax = plt.subplots(figsize=(13.333, 7.5))
            # 모든 레이어의 배경을 투명하게 설정
            fig.patch.set_alpha(0.0)
            ax.set_facecolor((1,1,1,0))
            
            ax.imshow(img, extent=[img_min_lon, img_max_lon, img_min_lat, img_max_lat], origin='upper')
            if draw_polygon:
                for sub_poly in ([self.boundary_polygon] if self.boundary_polygon.geom_type == 'Polygon' else self.boundary_polygon.geoms):
                    bx, by = sub_poly.exterior.xy
                    ax.plot(bx, by, color='black', lw=3.0, zorder=10)
            ax.set_xlim(exp_min_x, exp_max_x)
            ax.set_ylim(exp_min_y, exp_max_y)
            ax.axis('off')
            buf = io.BytesIO()
            # 무조건 투명하게 저장 (배경은 PPT 슬라이드 색상인 흰색이 보임)
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', pad_inches=0, transparent=True)
            plt.close(fig)
            buf.seek(0)
            return buf

        # 1) 베이스 레이어 (별도 객체) - 이제 투명 배경 사용
        layer_images.append(("배경지도", pil_to_buf(base_tiles)))
        
        # 2) 구역계 레이어 (별도 객체)
        empty_img = Image.new("RGBA", (num_x * 256, num_y * 256), (255, 255, 255, 0))
        layer_images.append(("사업구역계", pil_to_buf(empty_img, draw_polygon=True)))
        
        # 3) 개별 WMS 레이어
        wms_url = "http://api.vworld.kr/req/wms"
        base_params = {
            "key": VWORLD_KEY, "domain": VWORLD_DOMAIN, "service": "WMS", "request": "GetMap",
            "crs": "EPSG:4326", "format": "image/png", "width": str(num_x * 256), "height": str(num_y * 256),
            "bbox": f"{img_min_lon},{img_min_lat},{img_max_lon},{img_max_lat}", "transparent": "true"
        }
        
        for source_name, categories in MAP_SOURCES.items():
            if source_name != "브이월드 (VWorld)": continue
            for cat_name, layers in categories.items():
                for name, code in layers.items():
                    if name in self.visible_layers and not "READY" in str(code):
                        try:
                            ol_params = base_params.copy()
                            ol_params["layers"] = code.lower()
                            res_ol = requests.get(wms_url, params=ol_params, timeout=10)
                            if res_ol.status_code == 200:
                                ol_img = Image.open(io.BytesIO(res_ol.content)).convert("RGBA")
                                layer_images.append((name, pil_to_buf(ol_img)))
                        except Exception: pass

        # 4) 도로 선형 레이어 (고속도로 / 국도 전용 레이어 사용)
        try:
            t_proj = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
            min_3857_x, min_3857_y = t_proj.transform(exp_min_x, exp_min_y)
            max_3857_x, max_3857_y = t_proj.transform(exp_max_x, exp_max_y)
            t_inv = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
            
            # (1) 고속도로망 전용 추출 (lt_l_highway)
            res_hw = requests.get("https://api.vworld.kr/req/wfs", params={"key": VWORLD_KEY, "SERVICE": "WFS", "version": "1.1.0", "request": "GetFeature", "TYPENAME": "lt_l_highway", "BBOX": f"{min_3857_x},{min_3857_y},{max_3857_x},{max_3857_y}", "outputFormat": "application/json", "maxFeatures": 1000}, timeout=10)
            if res_hw.status_code == 200:
                fig_hw, ax_hw = plt.subplots(figsize=(13.333, 7.5))
                fig_hw.patch.set_alpha(0.0); ax_hw.set_facecolor((1,1,1,0))
                data = res_hw.json()
                for f in data.get("features", []):
                    coords = f["geometry"]["coordinates"]
                    lines = coords if f["geometry"]["type"] == "MultiLineString" else [coords]
                    for line in lines:
                        lons, lats = zip(*[t_inv.transform(p[0], p[1]) for p in line])
                        ax_hw.plot(lons, lats, color='#FF0000', lw=5.0, alpha=0.9)
                ax_hw.set_xlim(exp_min_x, exp_max_x); ax_hw.set_ylim(exp_min_y, exp_max_y); ax_hw.axis('off')
                hw_buf = io.BytesIO()
                plt.savefig(hw_buf, format='png', dpi=150, bbox_inches='tight', pad_inches=0, transparent=True)
                plt.close(fig_hw); hw_buf.seek(0)
                layer_images.append(("고속도로망", hw_buf))

            # (2) 일반도로망 추출 (국도 lt_l_natlroad + 주요도로 lt_l_moctlink)
            fig_rd, ax_rd = plt.subplots(figsize=(13.333, 7.5))
            fig_rd.patch.set_alpha(0.0); ax_rd.set_facecolor((1,1,1,0))
            for layer in ["lt_l_natlroad", "lt_l_moctlink"]:
                max_f = 5000 if layer == "lt_l_moctlink" else 1000
                res_rd = requests.get("https://api.vworld.kr/req/wfs", params={"key": VWORLD_KEY, "SERVICE": "WFS", "version": "1.1.0", "request": "GetFeature", "TYPENAME": layer, "BBOX": f"{min_3857_x},{min_3857_y},{max_3857_x},{max_3857_y}", "outputFormat": "application/json", "maxFeatures": max_f}, timeout=10)
                if res_rd.status_code == 200:
                    data = res_rd.json()
                    for f in data.get("features", []):
                        rank = f.get("properties", {}).get("rd_rank_h", "")
                        if "고속" in rank: continue # 고속도로는 위에서 이미 처리함
                        color = "#FFD700" if (layer == "lt_l_natlroad" or "일반" in rank) else "#CCCCCC"
                        lw = 3.0 if (layer == "lt_l_natlroad" or "일반" in rank) else 1.5
                        coords = f["geometry"]["coordinates"]
                        lines = coords if f["geometry"]["type"] == "MultiLineString" else [coords]
                        for line in lines:
                            lons, lats = zip(*[t_inv.transform(p[0], p[1]) for p in line])
                            ax_rd.plot(lons, lats, color=color, lw=lw, alpha=0.8)
            ax_rd.set_xlim(exp_min_x, exp_max_x); ax_rd.set_ylim(exp_min_y, exp_max_y); ax_rd.axis('off')
            rd_buf = io.BytesIO()
            plt.savefig(rd_buf, format='png', dpi=150, bbox_inches='tight', pad_inches=0, transparent=True)
            plt.close(fig_rd); rd_buf.seek(0)
            layer_images.append(("일반도로망", rd_buf))
        except Exception: pass

        # 5) 철도/지하철망 선형 레이어 (WFS 기반)
        try:
            rl_layers = ["lt_l_railroad", "lt_l_subwayline"]
            fig_rl, ax_rl = plt.subplots(figsize=(13.333, 7.5))
            fig_rl.patch.set_alpha(0.0); ax_rl.set_facecolor((1,1,1,0))
            t_inv = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
            
            for layer in rl_layers:
                res_rl = requests.get("https://api.vworld.kr/req/wfs", params={"key": VWORLD_KEY, "SERVICE": "WFS", "version": "1.1.0", "request": "GetFeature", "TYPENAME": layer, "BBOX": f"{min_3857_x},{min_3857_y},{max_3857_x},{max_3857_y}", "outputFormat": "application/json", "maxFeatures": 2000}, timeout=10)
                if res_rl.status_code == 200:
                    data = res_rl.json()
                    for f in data.get("features", []):
                        coords = f["geometry"]["coordinates"]
                        lines = coords if f["geometry"]["type"] == "MultiLineString" else [coords]
                        for line in lines:
                            lons, lats = zip(*[t_inv.transform(p[0], p[1]) for p in line])
                            if layer == "lt_l_subwayline":
                                # 지하철은 눈에 띄는 주황색 계열로 표시
                                ax_rl.plot(lons, lats, color='#FF8C00', lw=3.0)
                            else:
                                ax_rl.plot(lons, lats, color='black', lw=2.5, solid_capstyle='round')
                                ax_rl.plot(lons, lats, color='white', lw=1.2, ls='--', dashes=(5, 5))
            
            ax_rl.set_xlim(exp_min_x, exp_max_x); ax_rl.set_ylim(exp_min_y, exp_max_y); ax_rl.axis('off')
            rl_buf = io.BytesIO()
            plt.savefig(rl_buf, format='png', dpi=150, bbox_inches='tight', pad_inches=0, transparent=True)
            plt.close(fig_rl); rl_buf.seek(0)
            layer_images.append(("철도지하철망", rl_buf))
        except Exception: pass

        # 6) 하천망 레이어 (WFS 기반 별도 이미지)
        try:
            res_rv = requests.get("https://api.vworld.kr/req/wfs", params={"key": VWORLD_KEY, "SERVICE": "WFS", "version": "1.1.0", "request": "GetFeature", "TYPENAME": "lt_c_wkmstrm", "BBOX": f"{min_3857_x},{min_3857_y},{max_3857_x},{max_3857_y}", "outputFormat": "application/json", "maxFeatures": 1000}, timeout=10)
            if res_rv.status_code == 200:
                data = res_rv.json()
                fig_rv, ax_rv = plt.subplots(figsize=(13.333, 7.5))
                fig_rv.patch.set_alpha(0.0); ax_rv.set_facecolor((1,1,1,0))
                t_inv = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
                for f in data.get("features", []):
                    geom = f["geometry"]
                    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
                    for poly in polys:
                        # 하천망은 보통 Polygon(List of LinearRings)
                        for ring in poly:
                            if isinstance(ring[0], list): # MultiPolygon or Polygon with holes
                                lons, lats = zip(*[t_inv.transform(p[0], p[1]) for p in ring])
                                ax_rv.fill(lons, lats, color='#AADDFF', alpha=0.8, edgecolor='#88CCFF', lw=0.5)
                            else: # Single LinearRing coords
                                lons, lats = zip(*[t_inv.transform(p[0], p[1]) for p in poly])
                                ax_rv.fill(lons, lats, color='#AADDFF', alpha=0.8, edgecolor='#88CCFF', lw=0.5)
                                break
                ax_rv.set_xlim(exp_min_x, exp_max_x); ax_rv.set_ylim(exp_min_y, exp_max_y); ax_rv.axis('off')
                rv_buf = io.BytesIO()
                plt.savefig(rv_buf, format='png', dpi=150, bbox_inches='tight', pad_inches=0, transparent=True)
                plt.close(fig_rv); rv_buf.seek(0)
                layer_images.append(("하천망", rv_buf))
        except Exception: pass

        # PPT 생성 및 레이어 배치
        template_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '자료', 'qbs_위치도.pptx'))
        if os.path.exists(template_path):
            prs = Presentation(template_path)
            slide = prs.slides[0]
            for sp in list(slide.shapes): sp.element.getparent().remove(sp.element)
        else:
            prs = Presentation()
            prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
            slide = prs.slides.add_slide(prs.slide_layouts[6]) # 빈 슬라이드 추가
        
        for name, img_buf in layer_images:
            slide.shapes.add_picture(img_buf, 0, 0, width=Inches(13.333), height=Inches(7.5))
        
        # 반원, 라벨 등 추가 (기존 로직 동일)
        center_px, center_py = Inches(13.333) / 2, Inches(7.5) / 2
        from pptx.oxml import parse_xml
        def add_white_glow(run): run._r.get_or_add_rPr().append(parse_xml("""<a:effectLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:glow rad="50800"><a:srgbClr val="FFFFFF"/></a:glow></a:effectLst>"""))
        def add_shape_shadow(shape): shape.element.spPr.append(parse_xml("""<a:effectLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:outerShdw blurRad="63500" dist="38100" dir="2700000" algn="tl" rotWithShape="0"><a:srgbClr val="000000"><a:alpha val="40000"/></a:srgbClr></a:outerShdw></a:effectLst>"""))

        for r_km in [1, 2, 3, 4, 5]:
            r_inch = Inches(7.5) * (r_km / (radius_km_y * 2))
            shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, center_px - r_inch, center_py - r_inch, r_inch * 2, r_inch * 2)
            shape.fill.background(); shape.line.color.rgb = RGBColor(120, 120, 120); shape.line.width = Pt(1.5)
            if r_km % 2 == 1: shape.line.dash_style = 4
            add_shape_shadow(shape)
            txBox = slide.shapes.add_textbox(center_px - r_inch - Inches(0.5), center_py - Inches(0.15), Inches(1.0), Inches(0.3))
            run = txBox.text_frame.paragraphs[0].add_run()
            run.text = f"{r_km}km"; run.font.size = Pt(12); run.font.bold = True; run.font.color.rgb = RGBColor(0, 0, 0)
            txBox.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER; add_white_glow(run)

        target_box = slide.shapes.add_textbox(center_px - Inches(0.7), center_py - Inches(0.4), Inches(1.4), Inches(0.4))
        run = target_box.text_frame.paragraphs[0].add_run()
        run.text = "사업대상지"; run.font.size = Pt(14); run.font.bold = True; run.font.color.rgb = RGBColor(0, 0, 0)
        target_box.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER; add_white_glow(run)

        # 1) 도로 아이콘 및 2) 산/역/IC/JC 명칭 (기존 로직 동일)
        bbox_str = f"{exp_min_x},{exp_min_y},{exp_max_x},{exp_max_y}"
        hw_tpl, nr_tpl, na_tpl = None, None, None
        if len(prs.slides) > 1:
            for sp in prs.slides[1].shapes:
                if sp.shape_type == 6:
                    text = "".join([t.text for t in sp.element.findall('.//a:t', namespaces={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'})])
                    if "30" in text: hw_tpl = sp
                    elif "45" in text: nr_tpl = sp
                elif sp.shape_type == 13: na_tpl = sp
        if na_tpl:
            new_na = copy.deepcopy(na_tpl.element)
            new_na.spPr.xfrm.off.x, new_na.spPr.xfrm.off.y = int(Inches(12.5)), int(Inches(0.5)); slide.shapes._spTree.append(new_na)

        try:
            res_wfs = requests.get("https://api.vworld.kr/req/wfs", params={"key": VWORLD_KEY, "SERVICE": "WFS", "version": "1.1.0", "request": "GetFeature", "TYPENAME": "lt_l_moctlink", "BBOX": f"{min_3857_x},{min_3857_y},{max_3857_x},{max_3857_y}", "outputFormat": "application/json", "maxFeatures": 5000}, timeout=10)
            if res_wfs.status_code == 200:
                data = res_wfs.json(); drawn_roads = set(); drawn_names = set(); t_inv = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
                for f in data.get("features", []):
                    props = f.get("properties", {})
                    rank, no, road_name = props.get("rd_rank_h", ""), props.get("road_no", "-"), props.get("road_name", "")
                    if no != "-" and no != "0" and no not in drawn_roads:
                        target_tpl = hw_tpl if "고속" in rank else (nr_tpl if "일반" in rank else None)
                        if target_tpl:
                            coords = f["geometry"]["coordinates"]; coords = coords[0] if f["geometry"]["type"] == "MultiLineString" else coords
                            mx, my = coords[len(coords)//2]; lon, lat = t_inv.transform(mx, my)
                            px, py = (lon - exp_min_x) / (exp_max_x - exp_min_x) * 13.333, (exp_max_y - lat) / (exp_max_y - exp_min_y) * 7.5
                            if 0 < px < 13.333 and 0 < py < 7.5:
                                new_icon = copy.deepcopy(target_tpl.element)
                                new_icon.grpSpPr.xfrm.off.x, new_icon.grpSpPr.xfrm.off.y = int(Inches(px) - Inches(0.2)), int(Inches(py) - Inches(0.2))
                                for t_el in new_icon.findall('.//a:t', namespaces={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}):
                                    if t_el.text and t_el.text.isdigit(): t_el.text = str(no)
                                slide.shapes._spTree.append(new_icon); drawn_roads.add(no)
                    if road_name and len(road_name) > 2 and road_name not in drawn_names and any(x in rank for x in ["주간선", "보조간선"]):
                        coords = f["geometry"]["coordinates"]; coords = coords[0] if f["geometry"]["type"] == "MultiLineString" else coords
                        mx, my = coords[len(coords)//2]; lon, lat = t_inv.transform(mx, my)
                        px, py = (lon - exp_min_x) / (exp_max_x - exp_min_x) * 13.333, (exp_max_y - lat) / (exp_max_y - exp_min_y) * 7.5
                        if 1.0 < px < 12.3 and 1.0 < py < 6.5:
                            tx = slide.shapes.add_textbox(Inches(px), Inches(py), Inches(1.5), Inches(0.3))
                            run = tx.text_frame.paragraphs[0].add_run()
                            run.text = road_name; run.font.size = Pt(9); run.font.bold = True; run.font.color.rgb = RGBColor(80, 80, 80); add_white_glow(run)
                            drawn_names.add(road_name)
        except Exception: pass

        poi_queries = {"산": RGBColor(34, 139, 34)}
        for query, color in poi_queries.items():
            pois = self.fetch_pois(bbox_str, query)
            for poi in pois:
                lon, lat = float(poi['point']['x']), float(poi['point']['y'])
                px, py = (lon - exp_min_x) / (exp_max_x - exp_min_x) * 13.333, (exp_max_y - lat) / (exp_max_y - exp_min_y) * 7.5
                if 0.5 < px < 12.8 and 0.5 < py < 7.0:
                    if query == "산":
                        icon = slide.shapes.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE, Inches(px)-Inches(0.06), Inches(py)-Inches(0.06), Inches(0.14), Inches(0.12))
                        icon.fill.solid(); icon.fill.fore_color.rgb = RGBColor(34, 139, 34); icon.line.color.rgb = RGBColor(255, 255, 255)
                    tx = slide.shapes.add_textbox(Inches(px) + Inches(0.08), Inches(py) - Inches(0.1), Inches(1.8), Inches(0.4))
                    run = tx.text_frame.paragraphs[0].add_run()
                    run.text = poi['title']; run.font.size = Pt(11); run.font.bold = True; run.font.color.rgb = color; add_white_glow(run)

        try:
            adm_pois = self.fetch_pois(bbox_str, "주민센터")
            drawn_adms = set()
            for poi in adm_pois:
                title = poi['title'].replace("주민센터", "").replace("행정복지센터", "").strip()
                if title in drawn_adms or len(title) > 10: continue
                lon, lat = float(poi['point']['x']), float(poi['point']['y'])
                px, py = (lon - exp_min_x) / (exp_max_x - exp_min_x) * 13.333, (exp_max_y - lat) / (exp_max_y - exp_min_y) * 7.5
                if 1.0 < px < 12.3 and 1.0 < py < 6.5:
                    tx = slide.shapes.add_textbox(Inches(px), Inches(py), Inches(1.0), Inches(0.3))
                    run = tx.text_frame.paragraphs[0].add_run()
                    run.text = title; run.font.size = Pt(12); run.font.bold = True; run.font.color.rgb = RGBColor(150, 150, 150); add_white_glow(run)
                    drawn_adms.add(title)
        except Exception: pass

        out_buf = io.BytesIO()
        prs.save(out_buf)
        out_buf.seek(0)
        return out_buf.getvalue()

