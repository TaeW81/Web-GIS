import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# 필수 라이브러리 체크
try:
    import shapefile  # pyshp
    import ezdxf
    import pyproj
except ImportError:
    pass

# --- 모던 라이트 테마 (Slate + Blue) ---
COLOR_BG = "#f1f5f9"          # 전체 배경 (slate-100)
COLOR_CARD = "#ffffff"        # 카드/프레임 배경 (화이트)
COLOR_HEADER = "#ffffff"      # 헤더 배경 (화이트)
COLOR_ACCENT = "#2563eb"      # 강조색 (blue-600)
COLOR_ACCENT_DARK = "#1d4ed8" # 강조색 hover (blue-700)
COLOR_ACCENT_SOFT = "#eff6ff" # 강조 연한 배경 (blue-50)
COLOR_TEXT = "#1e293b"        # 기본 텍스트 (slate-800)
COLOR_SUBTEXT = "#64748b"     # 보조 텍스트 (slate-500)
COLOR_SUCCESS = "#16a34a"     # 성공 색상 (green-600)
COLOR_BORDER = "#e2e8f0"      # 테두리 색상 (slate-200)
COLOR_SECTION = "#f8fafc"     # 섹션/구분 배경 (slate-50)
COLOR_SCROLL = "#cbd5e1"      # 스크롤바 thumb (slate-300)

FONT = "Malgun Gothic"        # 한글/영문 모두 깔끔하게 렌더링

# --- 한국 좌표계 EPSG 매핑 (데이텀 × 원점) ---
# grs80_current: 한국 2000 현행(가오프셋 200000/600000)
# bessel       : 한국 1985 베셀(Modified, 가오프셋 200000/500000)
# grs80_old    : 한국 2000 과거(가오프셋 200000/500000)
EPSG_TABLE = {
    ("grs80_current", "west"): 5185,
    ("grs80_current", "central"): 5186,
    ("grs80_current", "east"): 5187,
    ("grs80_current", "eastsea"): 5188,
    ("grs80_current", "jeju"): 5186,   # 제주는 중부원점(127°) 영역 사용
    ("bessel", "west"): 5173,
    ("bessel", "central"): 5174,
    ("bessel", "east"): 5176,
    ("bessel", "eastsea"): 5177,
    ("bessel", "jeju"): 5175,
    ("grs80_old", "west"): 5180,
    ("grs80_old", "central"): 5181,
    ("grs80_old", "east"): 5183,
    ("grs80_old", "eastsea"): 5184,
    ("grs80_old", "jeju"): 5182,
}

def get_shp_fields(shp_path):
    try:
        with shapefile.Reader(shp_path) as sf:
            return [f[0] for f in sf.fields[1:]]
    except Exception as e:
        return []

def get_unique_path(base_path):
    if not os.path.exists(base_path): return base_path
    d, f = os.path.split(base_path)
    n, e = os.path.splitext(f)
    c = 1
    while True:
        p = os.path.join(d, f"{n}({c}){e}")
        if not os.path.exists(p): return p
        c += 1

def format_value(val, decimal_places):
    if isinstance(val, (int, float)):
        try: return f"{float(val):.{decimal_places}f}"
        except: return str(val)
    return str(val)

def build_transformer(shp_path, target_epsg):
    """원본 .prj을 읽어 target_epsg로 변환하는 Transformer를 생성한다.
    반환: (transformer 또는 None, 경고 메시지 또는 None)
    반환: dict(transformer, warning, src, same)
      - transformer: 변환기 또는 None(변환 불필요/불가 시)
      - warning: 사용자 안내 메시지 또는 None
      - src: 감지된 원본 좌표계 이름 또는 None
      - same: 원본과 출력 좌표계가 사실상 동일하여 좌표가 바뀌지 않는 경우 True"""
    info = {"transformer": None, "warning": None, "src": None, "same": False}
    if not target_epsg:
        return info
    prj_path = os.path.splitext(shp_path)[0] + ".prj"
    if not os.path.exists(prj_path):
        info["warning"] = "원본 .prj 없음 → 좌표 변환 생략"
        return info
    try:
        with open(prj_path, "r", encoding="utf-8", errors="ignore") as f:
            wkt = f.read()
        src_crs = pyproj.CRS.from_wkt(wkt)
        dst_crs = pyproj.CRS.from_epsg(int(target_epsg))
        info["src"] = src_crs.name
        tr = pyproj.Transformer.from_crs(src_crs, dst_crs, always_xy=True)
        # 한국 투영좌표 대표점으로 실제 변위가 있는지 확인 (이름만 다르고 동일한 좌표계 감지)
        sx, sy = 200000.0, 500000.0
        tx, ty = tr.transform(sx, sy)
        if abs(tx - sx) < 1e-6 and abs(ty - sy) < 1e-6:
            info["same"] = True   # 변환해도 좌표 동일 → 변환 생략
            return info
        info["transformer"] = tr
        return info
    except Exception as e:
        info["warning"] = f"좌표계 해석 실패({e}) → 좌표 변환 생략"
        return info

def convert_shp_to_dxf(shp_path, dxf_path, field_settings=None, text_size=2.0, target_epsg=None):
    info = build_transformer(shp_path, target_epsg)
    transformer = info["transformer"]

    def tp(points):
        # [(x, y), ...] 목록을 타깃 좌표계로 변환 (transformer가 없으면 원본 반환)
        if transformer is None or not points:
            return points
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        tx, ty = transformer.transform(xs, ys)
        return list(zip(tx, ty))

    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    doc.layers.new(name='GEOMETRY', dxfattribs={'color': 7})
    if field_settings:
        for f_name in field_settings.keys():
            if f_name not in doc.layers:
                doc.layers.new(name=f_name, dxfattribs={'color': 2})
    with shapefile.Reader(shp_path, encoding='cp949') as sf:
        fields = [f[0] for f in sf.fields[1:]]
        for shape_rec in sf.shapeRecords():
            geom = shape_rec.shape
            record = shape_rec.record
            pts = tp(geom.points)  # 변환된 좌표 (parts 인덱스와 순서/길이 동일)
            if geom.shapeType in [3, 5, 8, 13, 15]:
                for i in range(len(geom.parts)):
                    si = geom.parts[i]
                    ei = geom.parts[i+1] if i+1 < len(geom.parts) else len(pts)
                    msp.add_lwpolyline(pts[si:ei], dxfattribs={'layer': 'GEOMETRY'})
            elif geom.shapeType in [1, 11, 21]:
                msp.add_point(pts[0], dxfattribs={'layer': 'GEOMETRY'})
            if field_settings:
                if pts:
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                    ai = 0
                    for fn, pr in field_settings.items():
                        if fn in fields:
                            v = record[fields.index(fn)]
                            if v is not None:
                                tv = format_value(v, pr)
                                msp.add_text(tv, dxfattribs={'layer': fn, 'height': text_size}).set_placement((cx, cy - (ai * text_size * 1.5)))
                                ai += 1
    doc.saveas(dxf_path)
    return info

class ConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SHP → DXF Converter")
        self.root.geometry("880x900")
        self.root.minsize(720, 560)
        self.root.configure(bg=COLOR_BG)
        
        self.all_files = {}
        self.file_field_controls = {}
        self.output_folder = tk.StringVar(value="")

        # 출력 좌표계 설정 (기본: 베셀 중부원점 = EPSG:5174)
        self.datum_var = tk.StringVar(value="bessel")
        self.origin_var = tk.StringVar(value="central")
        self.epsg_var = tk.StringVar(value="5174")
        self.origin_radios = []

        self.setup_styles()
        self.create_widgets()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        # 카드형 LabelFrame (얇은 테두리, 깔끔한 제목)
        style.configure("Card.TLabelframe", background=COLOR_CARD, bordercolor=COLOR_BORDER,
                        relief="solid", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background=COLOR_CARD, foreground=COLOR_TEXT,
                        font=(FONT, 11, "bold"))

        # 기본 라벨
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=(FONT, 10))

        # 보조(고스트) 버튼 — 흰 배경 + 얇은 테두리
        style.configure("TButton", font=(FONT, 10), padding=(14, 7), relief="flat",
                        background=COLOR_CARD, foreground=COLOR_TEXT,
                        bordercolor=COLOR_BORDER, focuscolor=COLOR_CARD)
        style.map("TButton",
                  background=[("active", COLOR_SECTION), ("pressed", COLOR_BORDER)],
                  bordercolor=[("active", COLOR_ACCENT)],
                  foreground=[("active", COLOR_ACCENT)])

        # 강조(Primary) 버튼 — 채워진 액센트
        style.configure("Accent.TButton", font=(FONT, 11, "bold"), padding=(16, 9), relief="flat",
                        background=COLOR_ACCENT, foreground="white",
                        bordercolor=COLOR_ACCENT, focuscolor=COLOR_ACCENT)
        style.map("Accent.TButton",
                  background=[("active", COLOR_ACCENT_DARK), ("pressed", COLOR_ACCENT_DARK)],
                  foreground=[("active", "white")])

        # Entry / Spinbox — 플랫 + 얇은 테두리
        style.configure("TEntry", fieldbackground="white", foreground=COLOR_TEXT,
                        bordercolor=COLOR_BORDER, lightcolor=COLOR_BORDER, darkcolor=COLOR_BORDER,
                        relief="flat", padding=5)
        style.map("TEntry", bordercolor=[("focus", COLOR_ACCENT)])
        style.configure("TSpinbox", fieldbackground="white", foreground=COLOR_TEXT, arrowsize=12,
                        bordercolor=COLOR_BORDER, lightcolor=COLOR_BORDER, darkcolor=COLOR_BORDER,
                        relief="flat", padding=4)
        style.map("TSpinbox", bordercolor=[("focus", COLOR_ACCENT)])

        # 체크박스 (카드 배경) — 선택 시 액센트로 채움
        for cb_style, bg in [("TCheckbutton", COLOR_CARD), ("Panel.TCheckbutton", COLOR_CARD)]:
            style.configure(cb_style, background=bg, foreground=COLOR_TEXT, font=(FONT, 10),
                            focuscolor=bg, indicatorrelief="flat", indicatorsize=11, padding=2)
            style.map(cb_style,
                      background=[("active", bg)],
                      indicatorbackground=[("selected", COLOR_ACCENT), ("!selected", "white")],
                      indicatorforeground=[("selected", "white")],
                      bordercolor=[("selected", COLOR_ACCENT), ("!selected", COLOR_SUBTEXT)])

        # 라디오 버튼 (좌표계 패널) — 선택 시 액센트
        style.configure("Panel.TRadiobutton", background=COLOR_CARD, foreground=COLOR_TEXT,
                        font=(FONT, 10), focuscolor=COLOR_CARD, indicatorrelief="flat", padding=2)
        style.map("Panel.TRadiobutton",
                  background=[("active", COLOR_CARD)],
                  indicatorbackground=[("selected", COLOR_ACCENT), ("!selected", "white")],
                  foreground=[("disabled", "#cbd5e1")],
                  bordercolor=[("selected", COLOR_ACCENT), ("!selected", COLOR_SUBTEXT)])

        # 슬림한 플랫 스크롤바
        style.configure("Vertical.TScrollbar", gripcount=0, background=COLOR_SCROLL,
                        troughcolor=COLOR_CARD, bordercolor=COLOR_CARD, arrowcolor=COLOR_CARD,
                        relief="flat", arrowsize=0, width=8)
        style.map("Vertical.TScrollbar", background=[("active", COLOR_SUBTEXT)])

        # Panedwindow sash
        style.configure("TPanedwindow", background=COLOR_BG)
        style.configure("Sash", sashthickness=8, gripcount=0)

    def _make_card(self, parent, title):
        """옅은 헤더 밴드(slate-50) + 흰색 본문 카드. (card, body) 반환."""
        card = tk.Frame(parent, bg=COLOR_CARD, highlightthickness=1,
                        highlightbackground=COLOR_BORDER, highlightcolor=COLOR_BORDER)
        head = tk.Frame(card, bg=COLOR_SECTION)
        head.pack(fill="x")
        tk.Label(head, text=title, bg=COLOR_SECTION, fg=COLOR_TEXT,
                 font=(FONT, 11, "bold"), anchor="w").pack(side="left", padx=14, pady=9)
        tk.Frame(card, bg=COLOR_BORDER, height=1).pack(fill="x")  # 헤더-본문 구분선
        body = tk.Frame(card, bg=COLOR_CARD)
        body.pack(fill="both", expand=True, padx=14, pady=12)
        return card, body

    def create_widgets(self):
        # 헤더 (화이트 + 하단 보더, 미니멀)
        header = tk.Frame(self.root, bg=COLOR_HEADER)
        header.pack(fill="x")
        inner = tk.Frame(header, bg=COLOR_HEADER)
        inner.pack(fill="x", padx=28, pady=(18, 16))
        tk.Label(inner, text="SHP → DXF Converter", font=(FONT, 17, "bold"),
                 bg=COLOR_HEADER, fg=COLOR_TEXT).pack(side="left")
        tk.Label(inner, text="Shapefile 일괄 변환 · 좌표계 변환", font=(FONT, 10),
                 bg=COLOR_HEADER, fg=COLOR_SUBTEXT).pack(side="left", padx=(12, 0), pady=(6, 0))
        tk.Frame(header, bg=COLOR_BORDER, height=1).pack(fill="x")

        # 하단 바 + 좌표계 패널 (가운데 영역보다 먼저 배치 → 창을 줄여도 항상 보임)
        self.create_bottom_bar()
        self.create_crs_panel()

        paned = ttk.Panedwindow(self.root, orient=tk.VERTICAL)
        paned.pack(fill="both", expand=True, padx=20, pady=16)

        # 1. 파일 선택
        self.f_frame, f_body = self._make_card(paned, "1. 변환 대상 SHP 파일 목록")
        paned.add(self.f_frame, weight=2)

        b_frame = tk.Frame(f_body, bg=COLOR_CARD)
        b_frame.pack(fill="x", pady=(0, 10))
        ttk.Button(b_frame, text="＋ 파일 추가", command=self.add_files).pack(side="left", padx=(0, 6))
        ttk.Button(b_frame, text="＋ 폴더 추가", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(b_frame, text="전체 선택", command=lambda: self.set_all_files(True)).pack(side="left", padx=6)
        ttk.Button(b_frame, text="비우기", command=self.clear_all).pack(side="right")

        self.f_canvas = tk.Canvas(f_body, bg=COLOR_CARD, highlightthickness=0, bd=0)
        self.f_sb = ttk.Scrollbar(f_body, orient="vertical", command=self.f_canvas.yview)
        self.f_scroll = tk.Frame(self.f_canvas, bg=COLOR_CARD)
        self.f_canvas.create_window((0, 0), window=self.f_scroll, anchor="nw")
        self.f_canvas.configure(yscrollcommand=self.f_sb.set)
        self.f_canvas.pack(side="left", fill="both", expand=True)
        self.f_sb.pack(side="right", fill="y")

        # 2. 필드 설정
        self.fd_frame, fd_body = self._make_card(paned, "2. 파일별 속성 필드 및 소수점 설정")
        paned.add(self.fd_frame, weight=4)

        self.fd_canvas = tk.Canvas(fd_body, bg=COLOR_CARD, highlightthickness=0, bd=0)
        self.fd_sb = ttk.Scrollbar(fd_body, orient="vertical", command=self.fd_canvas.yview)
        self.fd_scroll = tk.Frame(self.fd_canvas, bg=COLOR_CARD)
        self.fd_canvas.create_window((0, 0), window=self.fd_scroll, anchor="nw")
        self.fd_canvas.configure(yscrollcommand=self.fd_sb.set)
        self.fd_canvas.pack(side="left", fill="both", expand=True)
        self.fd_sb.pack(side="right", fill="y")

        # 캔버스 폭에 맞춰 내부 프레임 늘리기 (행 전체폭 hover/정렬)
        self.f_canvas.bind("<Configure>", lambda e: self.f_canvas.itemconfig("all", width=e.width))
        self.fd_canvas.bind("<Configure>", lambda e: self.fd_canvas.itemconfig("all", width=e.width))

        self._bind_mouse_wheel(self.f_canvas)
        self._bind_mouse_wheel(self.fd_canvas)

    def create_bottom_bar(self):
        tk.Frame(self.root, bg=COLOR_BORDER, height=1).pack(fill="x", side="bottom")  # 상단 구분선
        bottom_frame = tk.Frame(self.root, bg=COLOR_CARD, pady=16, padx=28)
        bottom_frame.pack(fill="x", side="bottom")

        # 저장 위치
        out_line = tk.Frame(bottom_frame, bg=COLOR_CARD)
        out_line.pack(fill="x", pady=(0, 12))
        tk.Label(out_line, text="저장 위치", bg=COLOR_CARD, fg=COLOR_SUBTEXT,
                 font=(FONT, 9, "bold"), width=8, anchor="w").pack(side="left")
        out_entry = tk.Entry(out_line, textvariable=self.output_folder, bg=COLOR_SECTION, fg=COLOR_TEXT,
                             relief="flat", readonlybackground=COLOR_SECTION,
                             highlightthickness=1, highlightbackground=COLOR_BORDER,
                             highlightcolor=COLOR_ACCENT, font=(FONT, 10))
        out_entry.pack(side="left", fill="x", expand=True, padx=10, ipady=5)
        ttk.Button(out_line, text="폴더 선택", command=self.browse_output).pack(side="left")

        # 옵션 및 실행
        exec_line = tk.Frame(bottom_frame, bg=COLOR_CARD)
        exec_line.pack(fill="x")

        tk.Label(exec_line, text="글자 크기", bg=COLOR_CARD, fg=COLOR_SUBTEXT,
                 font=(FONT, 9, "bold")).pack(side="left")
        self.txt_size = tk.DoubleVar(value=2.0)
        ttk.Spinbox(exec_line, from_=0.1, to=100.0, increment=0.5, textvariable=self.txt_size,
                    width=6).pack(side="left", padx=(10, 0))

        self.status_var = tk.StringVar(value="● 준비 완료")
        self.status_label = tk.Label(exec_line, textvariable=self.status_var, bg=COLOR_CARD,
                                     fg=COLOR_SUCCESS, font=(FONT, 10, "bold"))
        self.status_label.pack(side="left", padx=20)

        ttk.Button(exec_line, text="일괄 변환 시작  →", style="Accent.TButton",
                   command=self.run_batch).pack(side="right", ipadx=18)

    def create_crs_panel(self):
        panel_card, panel = self._make_card(self.root, "출력 도면 좌표계  ·  원본 .prj → 선택 좌표계로 변환")
        panel_card.pack(fill="x", side="bottom", padx=20, pady=(0, 4))

        def row(label):
            line = tk.Frame(panel, bg=COLOR_CARD)
            line.pack(fill="x", pady=3)
            tk.Label(line, text=label, bg=COLOR_CARD, fg=COLOR_SUBTEXT,
                     font=(FONT, 9, "bold"), width=7, anchor="w").pack(side="left")
            return line

        # 데이텀 선택
        datum_line = row("데이텀")
        for val, txt in [("grs80_current", "GRS80(현행)"), ("bessel", "베셀(Bessel)"),
                         ("wgs84", "WGS84/Google"), ("grs80_old", "GRS80(과거)")]:
            ttk.Radiobutton(datum_line, text=txt, variable=self.datum_var, value=val,
                            style="Panel.TRadiobutton", command=self.update_epsg).pack(side="left", padx=(0, 14))

        # 원점 선택
        origin_line = row("원점")
        self.origin_radios = []
        for val, txt in [("west", "서부"), ("central", "중부"), ("east", "동부"),
                         ("eastsea", "동해"), ("jeju", "제주")]:
            rb = ttk.Radiobutton(origin_line, text=txt, variable=self.origin_var, value=val,
                                 style="Panel.TRadiobutton", command=self.update_epsg)
            rb.pack(side="left", padx=(0, 14))
            self.origin_radios.append(rb)

        # EPSG 코드 (직접 입력 가능)
        epsg_line = row("EPSG")
        tk.Label(epsg_line, text="코드 직접 입력 가능", bg=COLOR_CARD, fg=COLOR_SUBTEXT,
                 font=(FONT, 9)).pack(side="left", padx=(0, 12))
        ttk.Entry(epsg_line, textvariable=self.epsg_var, width=12,
                  font=(FONT, 11, "bold")).pack(side="left")

    def update_epsg(self):
        d = self.datum_var.get()
        if d == "wgs84":
            for rb in self.origin_radios:
                rb.config(state="disabled")
            self.epsg_var.set("4326")  # WGS84 경위도 (필요시 3857 등으로 직접 수정)
            return
        for rb in self.origin_radios:
            rb.config(state="normal")
        code = EPSG_TABLE.get((d, self.origin_var.get()))
        if code:
            self.epsg_var.set(str(code))

    def _bind_mouse_wheel(self, canvas):
        def _on_mouse_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", _on_mouse_wheel))
        canvas.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))

    def browse_output(self):
        d = filedialog.askdirectory()
        if d: self.output_folder.set(d)

    def add_files(self):
        ps = filedialog.askopenfilenames(filetypes=[("Shapefiles", "*.shp")])
        for p in ps:
            if p not in self.all_files: self.all_files[p] = tk.BooleanVar(value=True)
        self.refresh_ui()

    def add_folder(self):
        d = filedialog.askdirectory()
        if d:
            for r, ds, fs in os.walk(d):
                for f in fs:
                    if f.lower().endswith(".shp"):
                        p = os.path.join(r, f)
                        if p not in self.all_files: self.all_files[p] = tk.BooleanVar(value=True)
            self.refresh_ui()

    def set_all_files(self, v):
        for var in self.all_files.values(): var.set(v)
        self.refresh_field_ui()

    def clear_all(self):
        self.all_files.clear()
        self.file_field_controls.clear()
        self.refresh_ui()

    def refresh_ui(self):
        for w in self.f_scroll.winfo_children(): w.destroy()
        items = sorted(self.all_files.items())
        if not items:
            tk.Label(self.f_scroll, text="파일 추가 또는 폴더 추가 버튼으로 SHP를 불러오세요.",
                     bg=COLOR_CARD, fg=COLOR_SUBTEXT, font=(FONT, 10), pady=24).pack(fill="x")
        for idx, (p, v) in enumerate(items):
            r = tk.Frame(self.f_scroll, bg=COLOR_CARD)
            r.pack(fill="x")
            ttk.Checkbutton(r, variable=v, command=self.refresh_field_ui).pack(side="left", padx=(6, 8), pady=8)
            tk.Label(r, text=os.path.basename(p), bg=COLOR_CARD, fg=COLOR_TEXT,
                     font=(FONT, 10, "bold"), anchor="w").pack(side="left")
            tk.Label(r, text=os.path.dirname(p), bg=COLOR_CARD, fg=COLOR_SUBTEXT,
                     font=(FONT, 8), anchor="w").pack(side="left", padx=12)
            if idx < len(items) - 1:
                tk.Frame(self.f_scroll, bg=COLOR_BORDER, height=1).pack(fill="x", padx=6)
        self.f_scroll.update_idletasks()
        self.f_canvas.config(scrollregion=self.f_canvas.bbox("all"))
        self.refresh_field_ui()

    def refresh_field_ui(self):
        for w in self.fd_scroll.winfo_children(): w.destroy()
        checked_paths = [p for p, v in self.all_files.items() if v.get()]
        if not checked_paths:
            tk.Label(self.fd_scroll, text="위 목록에서 변환할 파일을 체크하면 속성 필드가 표시됩니다.",
                     bg=COLOR_CARD, fg=COLOR_SUBTEXT, font=(FONT, 10), pady=24).pack(fill="x")
        for p in sorted(checked_paths):
            # 파일 헤더 (액센트 소프트 배경 + 좌측 액센트 바)
            f_header = tk.Frame(self.fd_scroll, bg=COLOR_ACCENT_SOFT)
            f_header.pack(fill="x", pady=(16, 0))
            tk.Frame(f_header, bg=COLOR_ACCENT, width=3).pack(side="left", fill="y")
            tk.Label(f_header, text=os.path.basename(p), font=(FONT, 10, "bold"),
                     bg=COLOR_ACCENT_SOFT, fg=COLOR_ACCENT, anchor="w").pack(side="left", padx=10, pady=7)

            if p not in self.file_field_controls:
                fields = get_shp_fields(p)
                self.file_field_controls[p] = {f: (tk.BooleanVar(value=False), tk.IntVar(value=0)) for f in fields}

            f_area = tk.Frame(self.fd_scroll, bg=COLOR_CARD)
            f_area.pack(fill="x", pady=(0, 4))

            for f_name, (cv, pv) in self.file_field_controls[p].items():
                row = tk.Frame(f_area, bg=COLOR_CARD)
                row.pack(fill="x", padx=14, pady=1)
                ttk.Checkbutton(row, variable=cv).pack(side="left", padx=(0, 8), pady=3)
                tk.Label(row, text=f_name, bg=COLOR_CARD, fg=COLOR_TEXT,
                         font=(FONT, 10), width=32, anchor="w").pack(side="left")
                tk.Label(row, text="소수점", bg=COLOR_CARD, fg=COLOR_SUBTEXT,
                         font=(FONT, 9)).pack(side="left")
                ttk.Spinbox(row, from_=0, to=10, textvariable=pv, width=4).pack(side="left", padx=10)
        self.fd_scroll.update_idletasks()
        self.fd_canvas.config(scrollregion=self.fd_canvas.bbox("all"))

    def run_batch(self):
        cps = [p for p, v in self.all_files.items() if v.get()]
        if not cps: return

        # 출력 좌표계 EPSG 확인 (비우면 좌표 변환 없이 원본 좌표 그대로 출력)
        epsg_text = self.epsg_var.get().strip()
        target_epsg = None
        if epsg_text:
            try:
                target_epsg = int(epsg_text)
            except ValueError:
                messagebox.showerror("좌표계 오류", f"EPSG 코드가 올바르지 않습니다: '{epsg_text}'\n숫자만 입력하세요. (예: 5174)")
                return

        self.status_var.set("● 변환 중...")
        self.status_label.config(fg=COLOR_ACCENT)
        self.root.update()
        sc, errs, warns, out_dirs, made = 0, [], [], [], []
        src_names, same_files = set(), []
        out_dir = self.output_folder.get()
        for p in cps:
            settings = {f: v[1].get() for f, v in self.file_field_controls[p].items() if v[0].get()}
            target = os.path.join(out_dir, os.path.splitext(os.path.basename(p))[0] + ".dxf") if out_dir else os.path.splitext(p)[0] + ".dxf"
            dp = get_unique_path(target)
            try:
                info = convert_shp_to_dxf(p, dp, settings, self.txt_size.get(), target_epsg)
                if info.get("warning"): warns.append(f"{os.path.basename(p)}: {info['warning']}")
                if info.get("src"): src_names.add(info["src"])
                if info.get("same"): same_files.append(os.path.basename(p))
                made.append(os.path.basename(dp))
                d = os.path.dirname(dp)
                if d not in out_dirs: out_dirs.append(d)
                sc += 1
            except Exception as e: errs.append(f"{os.path.basename(p)}: {e}")
        self.status_var.set("● 작업 완료")
        self.status_label.config(fg=(COLOR_SUCCESS if not errs else "#dc2626"))

        # 결과 메시지 구성
        lines = [f"성공: {sc} / 실패: {len(errs)}", ""]
        if src_names:
            lines.append("원본 좌표계: " + " · ".join(sorted(src_names)))
        lines.append(f"출력 좌표계: EPSG:{target_epsg}" if target_epsg else "출력 좌표계: 원본 유지(변환 없음)")
        if same_files:
            lines += ["", "ℹ️ 원본과 출력 좌표계가 동일하여 좌표가 변경되지 않았습니다.",
                      "   (다른 좌표계를 선택해야 좌표가 변환됩니다.)"]
        if made:
            shown = made[:8]
            lines += ["", "생성된 파일:"] + [f"  • {n}" for n in shown]
            if len(made) > len(shown):
                lines.append(f"  … 외 {len(made) - len(shown)}개")
        if errs:
            lines += ["", "❌ 실패:"] + errs
        if warns:
            lines += ["", "⚠️ 변환 경고:"] + warns
        msg = "\n".join(lines)

        if errs or warns: messagebox.showwarning("완료", msg)
        else: messagebox.showinfo("완료", msg)
        # 완료 후 생성된 파일이 있는 폴더 열기
        if sc:
            self.open_folders(out_dirs)

    def open_folders(self, dirs):
        """변환 결과가 저장된 폴더를 탐색기로 연다 (최대 3개)."""
        for d in dirs[:3]:
            if not d or not os.path.isdir(d):
                continue
            try:
                if sys.platform.startswith("win"):
                    os.startfile(d)
                elif sys.platform == "darwin":
                    import subprocess; subprocess.Popen(["open", d])
                else:
                    import subprocess; subprocess.Popen(["xdg-open", d])
            except Exception:
                pass

if __name__ == "__main__":
    try:
        import shapefile
        import ezdxf
        import pyproj
        root = tk.Tk()
        app = ConverterApp(root)
        root.mainloop()
    except ImportError:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("오류", "pip install pyshp ezdxf pyproj 를 실행하세요.")
        root.destroy()
