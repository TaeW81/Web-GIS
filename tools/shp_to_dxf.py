import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# 필수 라이브러리 체크
try:
    import shapefile  # pyshp
    import ezdxf
except ImportError:
    pass

# --- 밝은 테마 디자인 설정 (Light Mode Palette) ---
COLOR_BG = "#f5f6f7"        # 전체 배경 (연한 그레이)
COLOR_CARD = "#ffffff"      # 카드/프레임 배경 (화이트)
COLOR_ACCENT = "#0066cc"    # 강조색 (프로페셔널 블루)
COLOR_TEXT = "#212529"      # 기본 텍스트 (어두운 그레이)
COLOR_SUBTEXT = "#6c757d"   # 보조 텍스트 (회색)
COLOR_SUCCESS = "#28a745"   # 성공 색상 (초록)
COLOR_BORDER = "#dee2e6"    # 테두리 색상

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

def convert_shp_to_dxf(shp_path, dxf_path, field_settings=None, text_size=2.0):
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
            if geom.shapeType in [3, 5, 8, 13, 15]:
                for i in range(len(geom.parts)):
                    si = geom.parts[i]
                    ei = geom.parts[i+1] if i+1 < len(geom.parts) else len(geom.points)
                    msp.add_lwpolyline(geom.points[si:ei], dxfattribs={'layer': 'GEOMETRY'})
            elif geom.shapeType in [1, 11, 21]:
                msp.add_point(geom.points[0], dxfattribs={'layer': 'GEOMETRY'})
            if field_settings:
                pts = geom.points
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

class ConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("SHP to DXF Converter Pro (Light)")
        self.root.geometry("950x950")
        self.root.configure(bg=COLOR_BG)
        
        self.all_files = {} 
        self.file_field_controls = {}
        self.output_folder = tk.StringVar(value="")

        self.setup_styles()
        self.create_widgets()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # LabelFrame 스타일
        style.configure("TLabelFrame", background=COLOR_BG, foreground=COLOR_TEXT, bordercolor=COLOR_BORDER)
        style.configure("TLabelFrame.Label", background=COLOR_BG, foreground=COLOR_ACCENT, font=("Malgun Gothic", 11, "bold"))
        
        # 기본 Label 및 Button 스타일
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=("Malgun Gothic", 10))
        style.configure("TButton", font=("Malgun Gothic", 10), padding=5)
        
        # 강조 버튼
        style.configure("Accent.TButton", background=COLOR_ACCENT, foreground="white")
        style.map("Accent.TButton", background=[('active', '#0052a3')])

        # Entry 스타일
        style.configure("TEntry", fieldbackground="white", foreground=COLOR_TEXT)

    def create_widgets(self):
        # 타이틀
        title_frame = tk.Frame(self.root, bg=COLOR_ACCENT, pady=15)
        title_frame.pack(fill="x")
        tk.Label(title_frame, text="SHP to DXF Batch Converter Pro", font=("Malgun Gothic", 16, "bold"), 
                 bg=COLOR_ACCENT, fg="white").pack()

        paned = ttk.Panedwindow(self.root, orient=tk.VERTICAL)
        paned.pack(fill="both", expand=True, padx=20, pady=15)

        # 1. 파일 선택
        self.f_frame = ttk.LabelFrame(paned, text=" 📂 1. 변환 대상 SHP 파일 목록 ", padding=10)
        paned.add(self.f_frame, weight=2)
        
        b_frame = tk.Frame(self.f_frame, bg=COLOR_BG)
        b_frame.pack(fill="x", pady=(0, 5))
        ttk.Button(b_frame, text="+ 파일 추가", command=self.add_files).pack(side="left", padx=3)
        ttk.Button(b_frame, text="+ 폴더 추가", command=self.add_folder).pack(side="left", padx=3)
        ttk.Button(b_frame, text="전체 선택", command=lambda: self.set_all_files(True)).pack(side="left", padx=3)
        ttk.Button(b_frame, text="비우기", command=self.clear_all).pack(side="right", padx=3)

        self.f_canvas = tk.Canvas(self.f_frame, bg=COLOR_CARD, highlightthickness=1, highlightbackground=COLOR_BORDER)
        self.f_sb = ttk.Scrollbar(self.f_frame, orient="vertical", command=self.f_canvas.yview)
        self.f_scroll = tk.Frame(self.f_canvas, bg=COLOR_CARD)
        self.f_canvas.create_window((0, 0), window=self.f_scroll, anchor="nw")
        self.f_canvas.configure(yscrollcommand=self.f_sb.set)
        self.f_canvas.pack(side="left", fill="both", expand=True)
        self.f_sb.pack(side="right", fill="y")

        # 2. 필드 설정
        self.fd_frame = ttk.LabelFrame(paned, text=" ⚙️ 2. 파일별 속성 필드 및 소수점 설정 ", padding=10)
        paned.add(self.fd_frame, weight=4)
        
        self.fd_canvas = tk.Canvas(self.fd_frame, bg=COLOR_CARD, highlightthickness=1, highlightbackground=COLOR_BORDER)
        self.fd_sb = ttk.Scrollbar(self.fd_frame, orient="vertical", command=self.fd_canvas.yview)
        self.fd_scroll = tk.Frame(self.fd_canvas, bg=COLOR_CARD)
        self.fd_canvas.create_window((0, 0), window=self.fd_scroll, anchor="nw")
        self.fd_canvas.configure(yscrollcommand=self.fd_sb.set)
        self.fd_canvas.pack(side="left", fill="both", expand=True)
        self.fd_sb.pack(side="right", fill="y")

        self._bind_mouse_wheel(self.f_canvas)
        self._bind_mouse_wheel(self.fd_canvas)

        # 3. 하단 바
        bottom_frame = tk.Frame(self.root, bg="white", height=120, pady=15, padx=30, 
                               highlightthickness=1, highlightbackground=COLOR_BORDER)
        bottom_frame.pack(fill="x", side="bottom")

        # 저장 위치
        out_line = tk.Frame(bottom_frame, bg="white")
        out_line.pack(fill="x", pady=5)
        tk.Label(out_line, text="💾 저장 위치:", bg="white", fg=COLOR_SUBTEXT, font=("", 9, "bold")).pack(side="left")
        out_entry = tk.Entry(out_line, textvariable=self.output_folder, bg="#f8f9fa", fg=COLOR_TEXT, 
                            relief="flat", readonlybackground="#f8f9fa")
        out_entry.pack(side="left", fill="x", expand=True, padx=10, ipady=3)
        ttk.Button(out_line, text="폴더 선택", command=self.browse_output).pack(side="left")

        # 옵션 및 실행
        exec_line = tk.Frame(bottom_frame, bg="white")
        exec_line.pack(fill="x", pady=10)
        
        tk.Label(exec_line, text="📏 글자 크기:", bg="white", fg=COLOR_TEXT).pack(side="left")
        self.txt_size = tk.DoubleVar(value=2.0)
        tk.Spinbox(exec_line, from_=0.1, to=100.0, increment=0.5, textvariable=self.txt_size, 
                   width=5, bg="#f8f9fa", relief="flat").pack(side="left", padx=10)
        
        self.status_var = tk.StringVar(value="준비 완료")
        self.status_label = tk.Label(exec_line, textvariable=self.status_var, bg="white", fg=COLOR_ACCENT, font=("", 10, "bold"))
        self.status_label.pack(side="left", padx=20)
        
        ttk.Button(exec_line, text="일괄 변환 시작", style="Accent.TButton", command=self.run_batch).pack(side="right", ipadx=30, ipady=8)

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
        for p, v in sorted(self.all_files.items()):
            r = tk.Frame(self.f_scroll, bg=COLOR_CARD, pady=2)
            r.pack(fill="x")
            cb = tk.Checkbutton(r, variable=v, bg=COLOR_CARD, activebackground=COLOR_CARD, command=self.refresh_field_ui)
            cb.pack(side="left")
            tk.Label(r, text=os.path.basename(p), bg=COLOR_CARD, fg=COLOR_TEXT, width=30, anchor="w").pack(side="left")
            tk.Label(r, text=os.path.dirname(p), bg=COLOR_CARD, fg=COLOR_SUBTEXT, font=("", 8)).pack(side="left", padx=10)
        self.f_scroll.update_idletasks()
        self.f_canvas.config(scrollregion=self.f_canvas.bbox("all"))
        self.refresh_field_ui()

    def refresh_field_ui(self):
        for w in self.fd_scroll.winfo_children(): w.destroy()
        checked_paths = [p for p, v in self.all_files.items() if v.get()]
        for p in sorted(checked_paths):
            f_header = tk.Frame(self.fd_scroll, bg="#e9ecef", pady=5)
            f_header.pack(fill="x", pady=(15, 0))
            tk.Label(f_header, text=f"  ■ {os.path.basename(p)}", font=("Malgun Gothic", 10, "bold"), 
                     bg="#e9ecef", fg=COLOR_ACCENT, anchor="w").pack(side="left")
            
            if p not in self.file_field_controls:
                fields = get_shp_fields(p)
                self.file_field_controls[p] = {f: (tk.BooleanVar(value=False), tk.IntVar(value=0)) for f in fields}
            
            f_area = tk.Frame(self.fd_scroll, bg=COLOR_CARD, pady=5)
            f_area.pack(fill="x")
            
            for f_name, (cv, pv) in self.file_field_controls[p].items():
                row = tk.Frame(f_area, bg=COLOR_CARD)
                row.pack(fill="x", padx=20, pady=1)
                tk.Checkbutton(row, variable=cv, bg=COLOR_CARD).pack(side="left")
                tk.Label(row, text=f_name, bg=COLOR_CARD, fg=COLOR_TEXT, width=35, anchor="w").pack(side="left")
                tk.Label(row, text="소수점:", bg=COLOR_CARD, fg=COLOR_SUBTEXT, font=("", 8)).pack(side="left")
                tk.Spinbox(row, from_=0, to=10, textvariable=pv, width=3).pack(side="left", padx=10)
        self.fd_scroll.update_idletasks()
        self.fd_canvas.config(scrollregion=self.fd_canvas.bbox("all"))

    def run_batch(self):
        cps = [p for p, v in self.all_files.items() if v.get()]
        if not cps: return
        self.status_var.set("⏳ 변환 중...")
        self.root.update()
        sc, errs = 0, []
        out_dir = self.output_folder.get()
        for p in cps:
            settings = {f: v[1].get() for f, v in self.file_field_controls[p].items() if v[0].get()}
            target = os.path.join(out_dir, os.path.splitext(os.path.basename(p))[0] + ".dxf") if out_dir else os.path.splitext(p)[0] + ".dxf"
            dp = get_unique_path(target)
            try:
                convert_shp_to_dxf(p, dp, settings, self.txt_size.get())
                sc += 1
            except Exception as e: errs.append(f"{os.path.basename(p)}: {e}")
        self.status_var.set("✅ 작업 완료")
        res = f"성공: {sc} / 실패: {len(errs)}"
        if errs: messagebox.showwarning("완료", res + "\n\n" + "\n".join(errs))
        else: messagebox.showinfo("완료", res)

if __name__ == "__main__":
    try:
        import shapefile
        import ezdxf
        root = tk.Tk()
        app = ConverterApp(root)
        root.mainloop()
    except ImportError:
        root = tk.Tk(); root.withdraw()
        messagebox.showerror("오류", "pip install pyshp ezdxf 를 실행하세요.")
        root.destroy()
