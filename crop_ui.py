"""A persistent desktop workspace: original, editable corners, and crop together."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
import sys

import numpy as np
from PIL import Image, ImageTk, ImageOps
from batch_state import atomic_json, load_preferences, read_json, OutputDirectoryError
from batch_status import existing_crops, image_state, matches_filter, progress_summary


@dataclass(frozen=True)
class ImageViewport:
    scale: float
    x: float
    y: float
    width: int
    height: int

    @classmethod
    def fit(cls, image_size, canvas_size, padding=24):
        iw, ih = image_size
        cw, ch = canvas_size
        scale = min(max(1, cw-padding*2)/iw, max(1, ch-padding*2)/ih)
        width, height = max(1, round(iw*scale)), max(1, round(ih*scale))
        return cls(scale, (cw-width)/2, (ch-height)/2, width, height)

    def to_image(self, x, y):
        if self.x <= x < self.x+self.width and self.y <= y < self.y+self.height:
            return ((x-self.x)/self.scale, (y-self.y)/self.scale)
        return None

    def to_canvas(self, point):
        return self.x+point[0]*self.scale, self.y+point[1]*self.scale


class CropSelection:
    """Only a valid current preview can be accepted; resetting cannot save stale pixels."""

    def __init__(self, image, args, backend):
        self.image, self.args, self.backend = image, args, backend
        self.points = []
        self.preview = None
        self.error = ""
        self.manual_modified = False

    def reset(self):
        self.manual_modified = True
        self.points = []
        self.preview = None
        self.error = ""

    def refresh(self):
        self.preview = None
        self.error = ""
        if len(self.points) != 4:
            return
        try:
            corners = self.backend.order_corners(np.float32(self.points))
            self.preview = self.backend.finish_crop(
                self.backend.rectify(self.image, corners, square=self.args.square), self.args)
        except ValueError as exc:
            self.error = str(exc)

    def set_corners(self, corners):
        self.points = [tuple(map(float, p)) for p in self.backend.order_corners(corners)]
        self.refresh()

    def add(self, point):
        if len(self.points) < 4:
            self.manual_modified = True
            self.points.append(tuple(point))
            self.refresh()

    def undo(self):
        if self.points:
            self.manual_modified = True
            self.points.pop()
        self.refresh()

    def accept(self):
        if self.preview is None:
            return None
        return self.backend.order_corners(np.float32(self.points)), self.preview.copy()


@dataclass
class ImageNavigation:
    """Zoom/pan only the view; crop points always remain in source pixels."""

    zoom: float = 1.
    center: tuple | None = None

    def reset(self):
        self.zoom, self.center = 1., None

    def viewport(self, image_size, canvas_size):
        iw, ih = image_size
        cw, ch = canvas_size
        scale = ImageViewport.fit(image_size, canvas_size).scale * self.zoom
        width, height = max(1, round(iw*scale)), max(1, round(ih*scale))
        cx, cy = self.center or (iw/2, ih/2)
        def position(size, canvas, center):
            if size <= canvas-48:
                return (canvas-size)/2
            return min(24., max(canvas-24.-size, canvas/2-center*scale))
        x, y = position(width, cw, cx), position(height, ch, cy)
        self.center = ((cw/2-x)/scale, (ch/2-y)/scale)
        return ImageViewport(scale, x, y, width, height)

    def zoom_at(self, factor, anchor, image_size, canvas_size):
        view = self.viewport(image_size, canvas_size)
        cw, ch = canvas_size
        ax, ay = anchor
        point = view.to_image(ax, ay)
        if point is None:
            ax, ay = cw/2, ch/2
            point = self.center
        new_zoom = min(16., max(1., self.zoom*factor))
        scale = view.scale*new_zoom/self.zoom
        self.center = (point[0]-(ax-cw/2)/scale, point[1]-(ay-ch/2)/scale)
        self.zoom = new_zoom

    def pan(self, dx, dy, image_size, canvas_size):
        view = self.viewport(image_size, canvas_size)
        self.center = (self.center[0]-dx/view.scale, self.center[1]-dy/view.scale)

    def focus(self, points, image_size, canvas_size):
        if len(points) < 2:
            return
        low, high = np.min(points, axis=0), np.max(points, axis=0)
        size = np.maximum(high-low, 8)
        scale = min(max(1, canvas_size[0]-64)/size[0],
                    max(1, canvas_size[1]-64)/size[1]) * .8
        self.zoom = min(16., max(1., scale/ImageViewport.fit(image_size, canvas_size).scale))
        self.center = tuple((low+high)/2)


class CropWorkspace:
    BG = "#f3f5fa"
    TEXT = "#18243b"
    MUTED = "#69758a"
    ACCENT = "#4f46e5"
    TITLE = "拍屏裁剪工作台 / Screen Photo Crop"

    def __init__(self, backend, *, preferences_path=None):
        if sys.platform == "win32":
            # Avoid Windows bitmap scaling placing the footer below the taskbar.
            import ctypes
            try:
                ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            except (AttributeError, OSError):
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(1)
                except (AttributeError, OSError):
                    pass
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk, self.backend = tk, ttk, backend
        self.root = tk.Tk()
        self.root.title(self.TITLE)
        dpi = self.root.winfo_fpixels("1i")/96
        width = min(round(1280*dpi), self.root.winfo_screenwidth()-80)
        height = min(round(800*dpi), self.root.winfo_screenheight()-140)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(min(round(850*dpi), width), min(round(600*dpi), height))
        self.root.configure(bg=self.BG)
        self.closed = self.aborted = self.busy = False
        self.selection = None
        self.future = None
        self.poll_id = None
        self.drag_index = None
        self.reselect_point = None
        self.enter_down = False
        self.source_pil = self.preview_pil = None
        self.source_photo = self.preview_photo = None
        self.viewport = None
        self.navigation = ImageNavigation()
        self.pan_anchor = None
        self.space_down = False
        self.session = self.labels = self.batch_args = None
        self.current_index = 0
        self.batch_decision = ''
        self.requested_index = None
        self.restore_draft = None
        self.source_digest = ''
        self.automatic_quad = None
        self.paused = False
        self.thumb_cache = OrderedDict()
        self.thumb_photos = []
        self.saved_crop_names = set()
        self.preferences_path = Path(preferences_path) if preferences_path else Path(__file__).with_name('.crop-settings.json')
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="screen-detection")
        self.action = tk.StringVar(master=self.root, value="pending")
        self.status = tk.StringVar(value="选择文件夹和裁剪模式，开始处理 / Choose folders and a mode")
        self.filename = tk.StringVar(value="本地处理 · 原图保留 / Local processing · Originals preserved")
        self.counter = tk.StringVar(value="READY")
        self.mode_badge = tk.StringVar(value="完整图片 / Full picture")
        self.stats = dict(ok=0, skipped=0, error=0, existing=0)
        self._style()
        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Return>", self._enter)
        self.root.bind("<KeyRelease-Return>", lambda e: setattr(self, "enter_down", False))
        self.root.bind("<r>", lambda e: self._shortcut(e, self.recrop))
        self.root.bind("<R>", lambda e: self._shortcut(e, self.recrop))
        self.root.bind("<Escape>", lambda e: self._shortcut(e, lambda: self._decide("skip")))
        self.root.bind("<BackSpace>", lambda e: self._shortcut(e, self.undo))
        self.root.after(50, self.root.lift)

    def _style(self):
        style = self.ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=self.BG)
        style.configure("Card.TFrame", background="white")
        style.configure("TLabel", background=self.BG, foreground=self.TEXT, font=("Microsoft YaHei UI", 10))
        style.configure("Card.TLabel", background="white")
        style.configure("Hint.TLabel", foreground=self.MUTED, font=("Microsoft YaHei UI", 9))
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 20, "bold"))
        style.configure("TButton", font=("Microsoft YaHei UI", 10), padding=(14, 9), relief="flat")
        style.configure("View.TButton", font=("Microsoft YaHei UI", 9), padding=(6, 4))
        style.configure("Primary.TButton", background=self.ACCENT, foreground="white", borderwidth=0)
        style.map("Primary.TButton", background=[("disabled", "#c8ccdf"), ("active", "#4338ca")])
        style.configure("TEntry", padding=8, fieldbackground="white", font=("Microsoft YaHei UI", 10))
        style.configure("TRadiobutton", background="white", font=("Microsoft YaHei UI", 10), padding=5)
        style.configure("TCheckbutton", background="white", font=("Microsoft YaHei UI", 9), padding=3)
        style.configure("Horizontal.TProgressbar", background=self.ACCENT, troughcolor="#e0e5ef", borderwidth=0)
        dpi=self.root.winfo_fpixels('1i')/96
        style.configure('PictureList.Treeview',font=('Microsoft YaHei UI',10),
                        rowheight=max(24,round(25*dpi)),background='white',fieldbackground='white')
        style.configure('PictureList.Treeview.Heading',font=('Microsoft YaHei UI',9,'bold'))

    def _build(self):
        ttk, tk = self.ttk, self.tk
        header = ttk.Frame(self.root, padding=(24, 10))
        header.pack(fill="x")
        ttk.Label(header, text="Screen Photo Crop", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=f"拍屏裁剪工作台   v{self.backend.__version__}", style="Hint.TLabel").pack(side="left", padx=18)
        self.settings_button = ttk.Button(header, text="返回设置 / Settings", command=self.show_settings)
        self.settings_button.pack(side="right")
        self.container = ttk.Frame(self.root, padding=(24, 0, 24, 8))
        self.container.pack(fill="both", expand=True)
        self.settings = ttk.Frame(self.container, style="Card.TFrame", padding=16)
        self.editor = ttk.Frame(self.container)
        self._settings_ui()
        self._editor_ui()
        footer = ttk.Frame(self.root, padding=(24, 8, 24, 14))
        footer.pack(fill="x")
        tk.Label(footer,textvariable=self.status,wraplength=1050,height=2,anchor='w',justify='left',
                 bg=self.BG,fg=self.MUTED,font=('Microsoft YaHei UI',9)).pack(fill='x')
        self.progress = ttk.Progressbar(footer, maximum=100)
        self.progress.pack(fill="x", pady=(8, 0))
        self.show_settings()

    def _settings_ui(self):
        ttk, tk = self.ttk, self.tk
        saved = load_preferences(self.preferences_path)
        self.source = tk.StringVar(value=saved.get('source',''))
        self.output = tk.StringVar(value=saved.get('output',''))
        self.workflow = tk.StringVar(value=saved.get('workflow','review') if saved.get('workflow') in ('review','manual','retry','fixed','black_review') else 'review')
        self.shape = tk.StringVar(value=saved.get('shape','full') if saved.get('shape') in ('full','square') else 'full')
        self.recursive = tk.BooleanVar(value=saved.get('recursive') is True)
        self.overwrite = tk.BooleanVar(value=saved.get('overwrite') is True)
        self.debug = tk.BooleanVar(value=saved.get('debug') is True)
        self.trim = tk.BooleanVar(value=saved.get('trim') is True)
        panel = self.settings
        panel.columnconfigure(1, weight=1)
        ttk.Label(panel, text="开始一批裁剪 / Start a batch", style="Card.TLabel",
                  font=("Microsoft YaHei UI", 15, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        for row, label, variable in ((1,"原照片 / Photos",self.source),(2,"结果目录 / Results",self.output)):
            ttk.Label(panel, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", padx=(0,12), pady=6)
            entry=ttk.Entry(panel, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            if row==2:self.output_entry=entry
            ttk.Button(panel, text="选择 / Browse", command=lambda v=variable: self.browse(v)).grid(row=row, column=2, padx=(12,0))
        options = ttk.Frame(panel, style="Card.TFrame")
        options.grid(row=3, column=0, columnspan=3, sticky="ew", pady=6)
        options.columnconfigure((0,1), weight=1)
        modes = ttk.Frame(options, style="Card.TFrame")
        modes.grid(row=0, column=0, sticky="nw")
        ttk.Label(modes, text="01   处理方式 / Workflow", style="Card.TLabel", font=("Microsoft YaHei UI",11,"bold")).pack(anchor="w", pady=(0,5))
        for value, label in (("review","自动识别 · 逐张确认 / Review"),("manual","手动四角 · 逐张确认 / Manual"),
                             ("black_review","黑边识别 · 逐张确认 / Black-border review"),
                             ("fixed","固定坐标 · 首张确认后批量导出 / Fixed coordinates"),("retry","失败图片补裁 / Retry failures")):
            ttk.Radiobutton(modes, text=label, value=value, variable=self.workflow).pack(anchor="w")
        shapes = ttk.Frame(options, style="Card.TFrame")
        shapes.grid(row=0, column=1, sticky="nw", padx=(20,0))
        ttk.Label(shapes, text="02   图片形状 / Picture shape", style="Card.TLabel", font=("Microsoft YaHei UI",11,"bold")).pack(anchor="w", pady=(0,5))
        ttk.Radiobutton(shapes, text="完整图片 / Full picture", value="full", variable=self.shape).pack(anchor="w")
        ttk.Radiobutton(shapes, text="正方形 · 1:1 / Square", value="square", variable=self.shape).pack(anchor="w")
        ttk.Label(shapes, text="适用于原本为正方形的目标 / Originally square pictures",
                  style="Card.TLabel", foreground=self.MUTED, font=("Microsoft YaHei UI",9)).pack(anchor="w", pady=6)
        flags = ttk.Frame(panel, style="Card.TFrame")
        flags.grid(row=4, column=0, columnspan=3, sticky="w", pady=6)
        for i,(label, variable) in enumerate((("包含子目录 / Recursive",self.recursive),("覆盖旧结果 / Overwrite",self.overwrite),
                                ("保存识别框 / Debug",self.debug),("清除黑边 / Trim black",self.trim))):
            ttk.Checkbutton(flags, text=label, variable=variable).grid(row=i//2,column=i%2,sticky="w",padx=(0,20))
        self.workflow_hint=tk.StringVar()
        self.workflow.trace_add('write',lambda *_:self.update_workflow_hint())
        self.update_workflow_hint()
        ttk.Label(panel, textvariable=self.workflow_hint,
                  style="Card.TLabel", foreground=self.MUTED, wraplength=900).grid(row=5, column=0, columnspan=3, sticky="w", pady=8)
        buttons = ttk.Frame(panel,style='Card.TFrame')
        buttons.grid(row=6,column=0,columnspan=3,sticky='w')
        ttk.Button(buttons, text="开始裁剪 / Start", style="Primary.TButton", command=self._start).pack(side='left')
        ttk.Button(buttons,text='继续上次批次 / Resume',command=self.resume_last).pack(side='left',padx=8)
        ttk.Button(buttons,text='导出确认标签 / Export labels',command=self.export_labels).pack(side='left')

    def _editor_ui(self):
        ttk, tk = self.ttk, self.tk
        top = ttk.Frame(self.editor)
        top.pack(fill="x", pady=(0,10))
        ttk.Label(top, textvariable=self.counter, foreground=self.ACCENT, font=("Microsoft YaHei UI",12,"bold")).pack(side="left")
        ttk.Label(top, textvariable=self.filename, width=54).pack(side="left", padx=15)
        ttk.Label(top, textvariable=self.mode_badge, style="Hint.TLabel").pack(side="right")
        panes = ttk.Frame(self.editor)
        panes.pack(fill="both", expand=True)
        panes.columnconfigure((0,1), weight=1, uniform="images")
        panes.columnconfigure(2,weight=0,minsize=230)
        panes.rowconfigure(2, weight=1)
        ttk.Label(panes, text="01   原图 · 点击重选四角 / Original · Click to reselect").grid(row=0,column=0,sticky="w",pady=(0,8))
        ttk.Label(panes, text="02   裁剪预览 / Crop preview").grid(row=0,column=1,sticky="w",pady=(0,8),padx=(14,0))
        navigation = ttk.Frame(panes)
        navigation.grid(row=1,column=0,sticky="w",pady=(0,6))
        self.zoom_label = tk.StringVar(value="1.0×")
        for label, command in (("−",lambda:self.zoom_source(1/1.25)),
                               ("+",lambda:self.zoom_source(1.25)),
                               ("适应 Fit",self.fit_source),("选区 Focus",self.focus_source)):
            ttk.Button(navigation,text=label,command=command,style="View.TButton").pack(side="left",padx=(0,4))
        ttk.Label(navigation,textvariable=self.zoom_label,style="Hint.TLabel").pack(side="left",padx=4)
        self.source_canvas = tk.Canvas(panes, background="#111c30", highlightthickness=0, width=400, height=350)
        self.preview_canvas = tk.Canvas(panes, background="white", highlightthickness=1, highlightbackground="#dfe5ee", width=400, height=350)
        self.source_canvas.grid(row=2,column=0,sticky="nsew")
        self.preview_canvas.grid(row=1,column=1,rowspan=2,sticky="nsew",padx=(14,0))
        ttk.Label(panes,text="滚轮缩放 · 空格/中键拖移 / Wheel zoom · Space/middle drag",style="Hint.TLabel").grid(row=3,column=0,sticky="w",pady=(5,0))
        self._picture_list_ui(panes)
        self.source_canvas.bind("<Configure>", lambda e: self.render_source())
        self.preview_canvas.bind("<Configure>", lambda e: self.render_preview())
        self.source_canvas.bind("<Button-1>", self._click)
        self.source_canvas.bind("<B1-Motion>", self._drag)
        self.source_canvas.bind("<ButtonRelease-1>", self._release)
        self.source_canvas.bind("<Button-3>", lambda e: self.undo())
        self.source_canvas.bind("<MouseWheel>", self._wheel)
        self.source_canvas.bind("<Button-4>", lambda e:self.zoom_source(1.25,(e.x,e.y)))
        self.source_canvas.bind("<Button-5>", lambda e:self.zoom_source(1/1.25,(e.x,e.y)))
        self.source_canvas.bind("<Button-2>", self._pan_start)
        self.source_canvas.bind("<B2-Motion>", self._pan_move)
        self.source_canvas.bind("<ButtonRelease-2>", self._pan_end)
        self.source_canvas.bind("<KeyPress-space>", lambda e:self._space(True))
        self.source_canvas.bind("<KeyRelease-space>", lambda e:self._space(False))
        self.source_canvas.bind("<FocusOut>", lambda e:self._space(False))
        self.preview_detail = tk.StringVar(value="等待四角 / Waiting for corners")
        ttk.Label(self.editor, textvariable=self.preview_detail, style="Hint.TLabel").pack(anchor="e", pady=8)
        toolbar = ttk.Frame(self.editor)
        toolbar.pack(fill="x", pady=(0,4))
        self.reset_button = ttk.Button(toolbar,text="重新裁剪 / Re-crop (R)",command=self.recrop)
        self.reset_button.pack(side="left")
        self.undo_button = ttk.Button(toolbar,text="撤销 / Undo",command=self.undo)
        self.undo_button.pack(side="left",padx=8)
        self.stop_button = ttk.Button(toolbar,text="结束 / Stop",command=self.stop)
        self.stop_button.pack(side="left")
        self.save_button = ttk.Button(toolbar,text="保存并下一张 / Save & next ↵",style="Primary.TButton",command=lambda:self._decide("save"))
        self.save_button.pack(side="right")
        self.skip_button = ttk.Button(toolbar,text="跳过 / Skip (Esc)",command=lambda:self._decide("skip"))
        self.skip_button.pack(side="right",padx=8)
        batchbar = ttk.Frame(self.editor)
        batchbar.pack(fill='x',pady=(4,4))
        self.previous_button=ttk.Button(batchbar,text='上一张修改 / Previous',command=self.previous)
        self.previous_button.pack(side='left')
        self.pause_button=ttk.Button(batchbar,text='暂停 / Pause',command=self.pause)
        self.pause_button.pack(side='left',padx=8)
        self.resume_button=ttk.Button(batchbar,text='继续 / Resume',command=self.resume_last)
        self.resume_button.pack(side='left')
        ttk.Button(batchbar,text='导出确认标签 / Export labels',command=self.export_labels).pack(side='right')
        self.gallery=self.tk.Canvas(self.editor,height=90,bg=self.BG,highlightthickness=0)
        self.gallery.pack(fill='x')
        gallery_scroll=ttk.Scrollbar(self.editor,orient='horizontal',command=self._gallery_scroll)
        gallery_scroll.pack(fill='x')
        self.gallery.configure(xscrollcommand=gallery_scroll.set)
        self.gallery.bind('<Configure>',lambda e:self.render_gallery())
        self.gallery.bind('<Button-1>',self._gallery_click)

    def _picture_list_ui(self, parent):
        ttk,tk=self.ttk,self.tk
        panel=ttk.Frame(parent,padding=(12,0,0,0))
        panel.grid(row=0,column=2,rowspan=4,sticky='nsew')
        panel.columnconfigure(0,weight=1)
        panel.rowconfigure(4,weight=1)
        ttk.Label(panel,text='03   图片状态 / Images',font=('Microsoft YaHei UI',10,'bold')).grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,5))
        self.picture_summary=tk.StringVar(value='开始批次后显示进度 / Progress appears after Start')
        ttk.Label(panel,textvariable=self.picture_summary,style='Hint.TLabel',justify='left',wraplength=300).grid(row=1,column=0,columnspan=2,sticky='w',pady=(0,5))
        controls=ttk.Frame(panel)
        controls.grid(row=2,column=0,columnspan=2,sticky='ew',pady=(0,4))
        controls.columnconfigure(0,weight=1)
        self.picture_filter=tk.StringVar(value='全部 / All')
        self.picture_filter_box=ttk.Combobox(controls,textvariable=self.picture_filter,state='readonly',
            values=('全部 / All','未裁剪 / No crop','已裁剪 / Cropped','待处理 / Pending','已跳过 / Skipped','失败 / Error'))
        self.picture_filter_box.grid(row=0,column=0,sticky='ew')
        self.picture_filter_box.bind('<<ComboboxSelected>>',lambda event:self.rebuild_picture_list())
        ttk.Button(controls,text='刷新',style='View.TButton',command=self.refresh_picture_list).grid(row=0,column=1,padx=(4,0))
        ttk.Label(panel,text='双击图片跳转 / Double-click to open',style='Hint.TLabel').grid(row=3,column=0,columnspan=2,sticky='w',pady=(0,4))
        self.picture_list=ttk.Treeview(panel,columns=('status','filename'),show='headings',selectmode='browse',height=8,style='PictureList.Treeview')
        self.picture_list.heading('status',text='状态')
        self.picture_list.heading('filename',text='文件 / File')
        self.picture_list.column('status',width=130,minwidth=100,stretch=False)
        self.picture_list.column('filename',width=135,minwidth=90,stretch=True)
        self.picture_list.grid(row=4,column=0,sticky='nsew')
        scrollbar=ttk.Scrollbar(panel,orient='vertical',command=self.picture_list.yview)
        scrollbar.grid(row=4,column=1,sticky='ns')
        self.picture_list.configure(yscrollcommand=scrollbar.set)
        for state,color in (('saved','#178562'),('saved_draft','#4f46e5'),('draft','#4f46e5'),
                            ('error','#bd4141'),('saved_error','#bd4141'),('skipped','#ab7c24'),
                            ('saved_skipped','#ab7c24'),('missing','#bd4141'),('pending','#69758a')):
            self.picture_list.tag_configure(state,foreground=color)
        self.picture_list.bind('<Double-1>',self._picture_list_click)

    def browse(self, variable):
        from tkinter import filedialog
        path = filedialog.askdirectory(parent=self.root, title="选择文件夹 / Choose a folder")
        if path:
            variable.set(path)

    def update_workflow_hint(self):
        messages={
            'fixed':'固定坐标：首张 Enter 确认后自动导出；原图尺寸和目标位置须一致。 / Fixed: confirm once; same size and target position required.',
            'black_review':'识别中间图片的细黑框；检查、调整四角，按 Enter 确认后才保存。 / Detect the picture frame; adjust corners, then Enter to confirm each crop.'}
        self.workflow_hint.set(messages.get(self.workflow.get(),
            '原图与预览同页 · Enter 保存并下一张 / One page · Enter saves and advances'))

    def show_settings(self):
        if self.busy or self.closed:
            return
        self.editor.pack_forget()
        self.settings.pack(fill="both", expand=True)
        self.progress.configure(value=0)
        self.status.set("失败补裁请选择上次结果目录；其他方式请选择原照片和结果目录。 / Retry uses the previous result folder.")

    def _start(self):
        source, output = self.source.get().strip(), self.output.get().strip()
        if self.workflow.get() == "retry":
            folder = output or source
            if not folder:
                self.status.set("请填写上次结果目录 / Choose the previous result folder")
                return
            argv = [folder, "--retry-failed"]
        else:
            if not source or not output:
                self.status.set("请选择原照片和结果目录 / Choose both folders")
                return
            argv = [source, output, {'manual':'--manual','fixed':'--fixed','black_review':'--black-review'}.get(self.workflow.get(),'--review')]
        for enabled, option in ((self.shape.get()=="square","--square"),(self.recursive.get(),"--recursive"),
                                (self.overwrite.get(),"--overwrite"),(self.debug.get(),"--debug"),(self.trim.get(),"--trim-black")):
            if enabled:
                argv.append(option)
        self.remember_settings()
        self._run_batch(self.backend.parser().parse_args(argv))

    def remember_settings(self):
        try:
            atomic_json(self.preferences_path,{key:getattr(self,key).get() for key in
                ('source','output','workflow','shape','recursive','overwrite','debug','trim')})
        except OSError as exc:
            self.status.set(f'设置未保存 / Settings not saved · {exc}')

    def _run_batch(self,args):
        self.aborted = self.paused = False
        self.stats = dict(ok=0, skipped=0, error=0, existing=0)
        try:
            self.backend.run(args, workspace=self)
        except OutputDirectoryError as exc:
            self.busy = False
            self.settings_button.configure(state='normal')
            self._disable_actions()
            self.show_settings()
            self.output_entry.focus_set()
            self.output_entry.selection_range(0,'end')
            self.status.set('结果目录不可写，请更换目录或从桌面重新启动。 / Output unavailable: choose another folder or relaunch from desktop.')
            from tkinter import messagebox
            messagebox.showerror('无法保存结果 / Cannot save results',str(exc),parent=self.root)
            return
        except (ValueError, OSError) as exc:
            self.busy = False
            self.settings_button.configure(state='normal')
            self._disable_actions()
            self.previous_button.configure(state='normal' if self.session and self.current_index>0 and not args.fixed else 'disabled')
            self.resume_button.configure(state='normal' if self.session and self.session.first_pending()<len(self.session.files) else 'disabled')
            self.status.set(str(exc))
            return
        if not self.closed:
            self.busy = False
            self.settings_button.configure(state="normal")
            self._disable_actions()
            word = '暂停' if self.paused else '停止' if self.aborted else '完成'
            self.status.set(f"本批已{word} / Batch {'paused' if self.paused else 'stopped' if self.aborted else 'complete'} · 保存 {self.stats['ok']} · 跳过 {self.stats['skipped']} · 错误 {self.stats['error']}")
            self.previous_button.configure(state='normal' if self.current_index>0 and not args.fixed else 'disabled')
            self.resume_button.configure(state='normal' if self.session and self.session.first_pending()<len(self.session.files) else 'disabled')
            self.render_gallery()

    def begin_batch(self, session, labels, args):
        self.session,self.labels,self.batch_args=session,labels,args
        self.busy=True
        self.settings.pack_forget()
        self.editor.pack(fill='both',expand=True)
        self.settings_button.configure(state='disabled')
        session.persist('running')
        self.source.set(str(session.source))
        self.output.set(str(session.destination))
        self.workflow.set('retry' if args.retry_failed else 'fixed' if args.fixed else 'black_review' if args.black_review else 'manual' if args.manual else 'review')
        self.shape.set('square' if args.square else 'full')
        shape = '正方形 1:1 / Square' if args.square else '完整图片 / Full picture'
        self.mode_badge.set(('固定坐标 / Fixed · ' if args.fixed else '黑边确认 / Black review · ' if args.black_review else '') + shape)
        for key in ('recursive','overwrite','debug'):getattr(self,key).set(getattr(args,key))
        self.trim.set(not args.no_trim_black)
        self.remember_settings()
        self.thumb_cache.clear()
        self.refresh_picture_list()

    def prepare_item(self,index):
        self.current_index=index
        self.batch_decision=''
        self.requested_index=None
        self.restore_draft=None
        self.source_digest=''
        self.automatic_quad=None
        self.selection=None
        self.fixed_outline=None
        self.source_pil=self.preview_pil=None
        self.counter.set(f'{index+1} / {len(self.session.files)}')
        self.filename.set(self.session.names[index])
        self.select_picture_list(index)
        self.preview_detail.set('等待当前图片四角 / Waiting for current corners')
        self.render_source();self.render_preview()
        self.previous_button.configure(state='normal' if index>0 else 'disabled')
        self.pause_button.configure(state='normal')
        self.resume_button.configure(state='disabled')
        total=max(1,len(self.session.files)*112)
        self.gallery.configure(scrollregion=(0,0,total,90))
        left=self.gallery.canvasx(0)
        right=self.gallery.canvasx(max(1,self.gallery.winfo_width()))
        if index*112<left or (index+1)*112>right:
            self.gallery.xview_moveto(max(0,index*112-112)/total)
        self.render_gallery()

    def restore_item(self,digest,record):
        self.source_digest=digest
        draft=self.session.drafts.get(self.session.names[self.current_index])
        self.restore_draft=draft if draft and draft.get('source_sha256')==digest else None
        self.restored_modified=record.get('manual_modified',False) if record.get('source_sha256')==digest else False

    def selection_metadata(self):
        return dict(manual_modified=self.selection.manual_modified)

    def checkpoint_selection(self):
        if getattr(self,'session',None) is not None and self.selection is not None:
            self.session.draft(self.selection.points,modified=self.selection.manual_modified,
                               automatic=self.automatic_quad,source_sha256=self.source_digest)
            if hasattr(self,'picture_list'):
                self.update_picture_row(self.current_index)

    def resume_last(self):
        if self.busy:return
        destination=self.output.get().strip() or self.source.get().strip()
        path=Path(destination)/('manual_crop_session.json' if self.workflow.get()=='retry' else 'crop_session.json')
        data=read_json(path)
        if not isinstance(data,dict) or data.get('schema')!=1:
            self.status.set('没有可继续的批次，请先开始裁剪 / No saved batch; start one first')
            return
        options=data['options']
        argv=[data['destination']] if options['retry_failed'] else [data['source'],data['destination']]
        for key in ('manual','review','retry_failed','fixed','black_review','recursive','square','overwrite','debug'):
            if options.get(key,False):argv.append('--'+key.replace('_','-'))
        if not options['no_trim_black']:argv.append('--trim-black')
        for key in ('black_threshold','max_trim','inset'):argv.extend(['--'+key.replace('_','-'),str(options[key])])
        argv.append('--resume')
        self._run_batch(self.backend.parser().parse_args(argv))

    def pause(self):
        if self.busy:
            self.checkpoint_selection()
            self.paused=True
            self.batch_decision='pause'
            self._decide('pause')

    def previous(self):
        if self.current_index>0:self.jump_to(self.current_index-1)

    def jump_to(self,index):
        if self.batch_args is not None and self.batch_args.fixed:
            self.status.set('固定坐标批次使用同一组四角；修改坐标请返回设置并开始新批次。 / To change fixed corners, start a new batch in Settings.')
            return
        if self.session is None or not 0<=index<len(self.session.files):return
        if self.busy:
            if index==self.current_index:return
            self.checkpoint_selection()
            self.requested_index=index
            self.batch_decision='jump'
            self._decide('jump')
        else:
            import copy
            args=copy.copy(self.batch_args)
            args.resume=True;args.start_index=index
            self._run_batch(args)

    def export_labels(self):
        from batch_state import LabelStore
        from tkinter import filedialog
        destination=self.output.get().strip()
        if not destination:
            self.status.set('请先选择结果目录 / Choose a result directory first');return
        path=filedialog.asksaveasfilename(parent=self.root,title='导出人工确认标签 / Export reviewed labels',
            initialdir=destination,initialfile='reviewed_labels.json',defaultextension='.json',filetypes=[('JSON','*.json')])
        if not path:return
        try:
            count=LabelStore(destination).export(path)
            self.status.set(f'已导出 {count} 条确认标签 / Exported {count} reviewed labels · {path}')
        except (ValueError,OSError) as exc:self.status.set(str(exc))

    def _gallery_scroll(self,*args):
        self.gallery.xview(*args);self.render_gallery()

    def _gallery_click(self,event):
        self.jump_to(int(self.gallery.canvasx(event.x)//112))

    def picture_filter_key(self):
        return {'未裁剪 / No crop':'uncropped','已裁剪 / Cropped':'cropped',
                '待处理 / Pending':'pending','已跳过 / Skipped':'skipped',
                '失败 / Error':'error'}.get(self.picture_filter.get(),'all')

    def picture_values(self,index):
        state=image_state(self.session,index,self.saved_crop_names)
        labels={'saved':'已裁 Done','saved_draft':'已裁·草稿','draft':'草稿 Draft',
                'error':'失败 Error','saved_error':'失败·旧图','skipped':'跳过 Skip',
                'saved_skipped':'跳过·旧图','missing':'结果缺失','pending':'未裁 Wait'}
        return state,(labels[state],f'{index+1} · {self.session.names[index]}')

    def update_picture_summary(self):
        if self.session is None:return
        summary=progress_summary(self.session,self.saved_crop_names)
        total=summary['total']
        self.picture_summary.set(
            f"已裁 Cropped {summary['cropped']}/{total}\n"
            f"未裁 No crop {summary['uncropped']}\n"
            f"草稿 {summary['drafts']} · 跳过 {summary['skipped']} · 失败 {summary['errors']}\n"
            f"处理 Processed {summary['processed']}/{total}")
        self.progress.configure(value=summary['cropped']/max(1,total)*100)

    def rebuild_picture_list(self):
        if self.closed or self.session is None:return
        tree=self.picture_list
        tree.delete(*tree.get_children())
        choice=self.picture_filter_key()
        for index in range(len(self.session.names)):
            if matches_filter(self.session,index,self.saved_crop_names,choice):
                state,values=self.picture_values(index)
                tree.insert('','end',iid=str(index),values=values,tags=(state,))
        self.update_picture_summary()
        self.select_picture_list(self.current_index)

    def refresh_picture_list(self):
        if self.session is None:return
        self.saved_crop_names=existing_crops(self.session.destination,self.session.names)
        self.rebuild_picture_list()
        self.render_gallery()

    def select_picture_list(self,index):
        if self.session is None:return
        iid=str(index)
        if self.picture_list.exists(iid):
            self.picture_list.selection_set(iid)
            self.picture_list.see(iid)
        else:
            self.picture_list.selection_remove(self.picture_list.selection())

    def update_picture_row(self,index):
        if self.closed or self.session is None:return
        tree=self.picture_list;iid=str(index)
        matches=matches_filter(self.session,index,self.saved_crop_names,self.picture_filter_key())
        if matches:
            state,values=self.picture_values(index)
            if tree.exists(iid):tree.item(iid,values=values,tags=(state,))
            else:
                previous=sum(int(item)<index for item in tree.get_children())
                tree.insert('',previous,iid=iid,values=values,tags=(state,))
        elif tree.exists(iid):tree.delete(iid)
        self.update_picture_summary()
        self.select_picture_list(self.current_index)

    def _picture_list_click(self,event):
        iid=self.picture_list.identify_row(event.y)
        if iid:self.jump_to(int(iid))

    def render_gallery(self):
        if self.closed or self.session is None:return
        canvas=self.gallery
        count=len(self.session.files)
        canvas.configure(scrollregion=(0,0,count*112,90))
        canvas.delete('all');self.thumb_photos=[]
        first=max(0,int(canvas.canvasx(0)//112)-1)
        last=min(count,int(canvas.canvasx(max(1,canvas.winfo_width()))//112)+2)
        colors={'ok':'#178562','existing':'#178562','skipped':'#ab7c24','error':'#bd4141','paused':self.ACCENT}
        for index in range(first,last):
            name=self.session.names[index];record=self.session.records.get(name,{})
            path=self.session.destination/record['output'] if record.get('saved') or record.get('status') in ('ok','existing') else self.session.files[index]
            x=index*112+4
            color=self.ACCENT if index==self.current_index else colors.get(record.get('status'),'#b8c2d2')
            canvas.create_rectangle(x,2,x+104,88,outline=color,width=2,fill='white')
            try:
                key=(str(path),path.stat().st_mtime_ns)
                if key not in self.thumb_cache:
                    with Image.open(path) as opened:
                        opened.draft('RGB',(100,64))
                        thumb=ImageOps.exif_transpose(opened).convert('RGB')
                        thumb.thumbnail((96,56),Image.Resampling.LANCZOS)
                    self.thumb_cache[key]=ImageTk.PhotoImage(thumb,master=self.root)
                    if len(self.thumb_cache)>48:self.thumb_cache.popitem(last=False)
                photo=self.thumb_cache[key];self.thumb_cache.move_to_end(key)
                self.thumb_photos.append(photo)
                canvas.create_image(x+52,33,image=photo)
            except (OSError,ValueError,Image.DecompressionBombError):
                canvas.create_text(x+52,32,text='待处理 / Pending',fill=self.MUTED,font=('Microsoft YaHei UI',8))
            short=Path(name).name
            if len(short)>13:short=short[:10]+'…'
            label=f'{index+1} · {short}'
            canvas.create_text(x+52,73,text=label,fill=color,font=('Microsoft YaHei UI',8))

    def launch(self):
        self.root.mainloop()
        return 0

    def review(self, image, proposed, args, title, *, auto_detect, filename=""):
        self.busy = True
        self.settings.pack_forget()
        self.editor.pack(fill="both", expand=True)
        self.settings_button.configure(state="disabled")
        self.filename.set(filename or "当前图片 / Current image")
        self.counter.set(title.replace("/", " / "))
        shape = "正方形 1:1 / Square" if args.square else "完整图片 / Full picture"
        self.mode_badge.set(('固定坐标 / Fixed · ' if args.fixed else '黑边确认 / Black review · ' if args.black_review else '') + shape)
        self.save_button.configure(text='确认并批量导出 / Confirm & export ↵' if args.fixed else
                                   '确认保存并下一张 / Confirm & next ↵' if args.black_review else '保存并下一张 / Save & next ↵')
        self.selection = CropSelection(image, args, self.backend)
        self.drag_index = None
        self.reselect_point = None
        self.navigation.reset()
        self.pan_anchor = None
        self.space_down = False
        self.source_pil = Image.fromarray(image[:,:,::-1])
        self.preview_pil = None
        self.preview_detail.set('等待当前图片四角 / Waiting for current corners')
        self.action.set("pending")
        self._disable_actions()
        self.skip_button.configure(state="normal")
        self.stop_button.configure(state="normal")
        self.pause_button.configure(state='normal')
        self.previous_button.configure(state='normal' if self.current_index>0 and not args.fixed else 'disabled')
        self.status.set('正在识别目标图片细黑框，请等待预览后确认 / Detecting the thin picture frame…' if args.black_review else
                        "正在识别边界，可跳过或结束 / Detecting boundaries…")
        self.root.update_idletasks()
        self.render_source()
        self.render_preview()
        if self.restore_draft is not None and (self.restore_draft['points'] or self.restore_draft['manual_modified']):
            draft=self.restore_draft
            self.selection.points=[tuple(p) for p in draft['points']]
            self.selection.manual_modified=draft['manual_modified']
            self.automatic_quad=draft.get('automatic_quad')
            self.selection.refresh()
            self._selection_changed()
        elif proposed is not None:
            self.selection.set_corners(proposed)
            self.selection.manual_modified=self.restored_modified
            self._selection_changed()
        elif auto_detect:
            self.future = self.executor.submit(self.detect_review_corners, image, args)
            self._poll_detection()
        else:
            self._selection_changed()
        self.source_canvas.focus_set()
        try:
            self.root.wait_variable(self.action)
        except self.tk.TclError:
            return None
        if self.poll_id is not None and not self.closed:
            self.root.after_cancel(self.poll_id)
            self.poll_id = None
        if self.future is not None:
            self.future.cancel()
            self.future = None
        if self.action.get() == "save":
            return self.selection.accept()
        return None

    def detect_review_corners(self,image,args):
        detector=self.backend.detect_black_border if args.black_review else self.backend.detect_screen
        return detector(image,square=args.square)

    def _poll_detection(self):
        self.poll_id = None
        if self.closed or self.action.get() != "pending":
            return
        if not self.future.done():
            self.poll_id = self.root.after(60, self._poll_detection)
            return
        error = ""
        try:
            corners = self.future.result()
            if corners is not None:
                self.selection.set_corners(corners)
                self.automatic_quad=corners.astype(float).tolist()
        except Exception as exc:
            error = str(exc)
        self.future = None
        self._selection_changed()
        if error:
            self.status.set(f"识别不可用，请手动选四角 / Select corners manually · {error}")
        elif self.selection.args.black_review and not self.selection.points:
            self.status.set('未找到可信细黑框，请放大后手动选四角 / No reliable frame; zoom in and select four corners manually')

    def _disable_actions(self):
        for button in (self.save_button,self.reset_button,self.undo_button,self.skip_button,self.stop_button,
                       self.previous_button,self.pause_button,self.resume_button):
            button.configure(state="disabled")

    def _selection_changed(self):
        preview = self.selection.preview
        self.preview_pil = Image.fromarray(preview[:,:,::-1]) if preview is not None else None
        ready = preview is not None and self.drag_index is None
        self.save_button.configure(state="normal" if ready else "disabled")
        self.reset_button.configure(state="normal")
        self.undo_button.configure(state="normal" if self.selection.points else "disabled")
        self.preview_detail.set(f"{preview.shape[1]} × {preview.shape[0]} px · 尚未保存 / Not saved" if ready else "等待有效四角 / Waiting for valid corners")
        ready_message = ("四角确认后按 Enter：后续按相同坐标自动导出，无需逐张审核 / Enter: confirm corners and export the rest without review"
                         if self.selection.args.fixed else
                         '检查黑框四角与预览 · 点击重选、拖动微调 · Enter 确认保存下一张 / Inspect frame and preview · Click/drag to adjust · Enter confirms'
                         if self.selection.args.black_review else
                         "预览已就绪 · 点击原图重选；拖动角点微调；Enter 保存并下一张 / Click original: reselect · Drag: adjust · Enter: save & next")
        self.status.set(self.selection.error or (ready_message if ready else f"请按顺序选四角 · 已选 {len(self.selection.points)}/4；可拖动角点 / Select 4 corners; drag to adjust"))
        self.render_source()
        self.render_preview()
        self.checkpoint_selection()

    def render_source(self):
        canvas = self.source_canvas
        canvas.delete("all")
        if self.source_pil is None:
            return
        canvas_size = (max(1,canvas.winfo_width()),max(1,canvas.winfo_height()))
        self.viewport = self.navigation.viewport(self.source_pil.size, canvas_size)
        view = self.viewport
        # Render only the visible canvas, not a potentially enormous zoomed bitmap.
        visible = self.source_pil.transform(canvas_size, Image.Transform.AFFINE,
                    (1/view.scale,0,-view.x/view.scale,0,1/view.scale,-view.y/view.scale),
                    resample=Image.Resampling.BICUBIC,fillcolor=(17,28,48))
        self.source_photo = ImageTk.PhotoImage(visible,master=self.root)
        canvas.create_image(0,0,image=self.source_photo,anchor="nw")
        self.zoom_label.set(f"{self.navigation.zoom:.1f}×")
        corners = self.selection.points if self.selection is not None else (getattr(self,'fixed_outline',None) or [])
        points = [view.to_canvas(p) for p in corners]
        if len(points)>1:
            outline = points+[points[0]] if len(points)==4 else points
            canvas.create_line(*[n for p in outline for n in p],fill="#54d9da",width=2)
        for i,(x,y) in enumerate(points):
            canvas.create_oval(x-6,y-6,x+6,y+6,fill="#54d9da",outline="white",width=2)
            canvas.create_text(x+14,y-14,text=str(i+1),fill="white",font=("Microsoft YaHei UI",11,"bold"))

    def render_preview(self):
        canvas = self.preview_canvas
        canvas.delete("all")
        w,h = canvas.winfo_width(),canvas.winfo_height()
        if self.preview_pil is None:
            canvas.create_text(w/2,h/2,text="裁剪结果将在这里显示\nCrop preview appears here",fill=self.MUTED,justify="center",font=("Microsoft YaHei UI",12))
            return
        view = ImageViewport.fit(self.preview_pil.size,(w,h))
        self.preview_photo = ImageTk.PhotoImage(self.preview_pil.resize((view.width,view.height),Image.Resampling.LANCZOS),master=self.root)
        canvas.create_image(view.x,view.y,image=self.preview_photo,anchor="nw")

    def _click(self, event):
        if self.space_down:
            return self._pan_start(event)
        if self.selection is None or self.future is not None or not self.busy:
            return
        point = self.viewport.to_image(event.x,event.y)
        if point is None:
            return
        self.source_canvas.focus_set()
        self.reselect_point = None
        for i,p in enumerate(self.selection.points):
            if np.linalg.norm(np.array(point)-p)*self.viewport.scale<=14:
                self.drag_index=i
                # A handle click also starts over; a deliberate drag still adjusts it.
                if len(self.selection.points) == 4:
                    self.reselect_point = point
                self.save_button.configure(state="disabled")
                return
        if len(self.selection.points) == 4:
            self.selection.reset()
        self.selection.add(point)
        self._selection_changed()

    def _drag(self, event):
        if self.pan_anchor is not None:
            return self._pan_move(event)
        if self.drag_index is None:
            return
        point = self.viewport.to_image(event.x,event.y)
        if point is not None:
            if self.reselect_point is not None:
                if np.linalg.norm(np.array(point)-self.reselect_point)*self.viewport.scale < 3:
                    return
                self.reselect_point = None
            self.selection.points[self.drag_index] = point
            self.selection.manual_modified = True
            self.selection.preview = None
            self.save_button.configure(state="disabled")
            self.render_source()

    def _release(self, event):
        if self.pan_anchor is not None:
            return self._pan_end(event)
        if self.drag_index is not None:
            self.drag_index = None
            if self.reselect_point is not None:
                point, self.reselect_point = self.reselect_point, None
                self.selection.reset()
                self.selection.add(point)
            else:
                self.selection.refresh()
            self._selection_changed()

    def _source_size(self):
        return (max(1,self.source_canvas.winfo_width()),max(1,self.source_canvas.winfo_height()))

    def zoom_source(self, factor, anchor=None):
        if self.source_pil is None or self.drag_index is not None or self.pan_anchor is not None:
            return "break"
        size = self._source_size()
        self.navigation.zoom_at(factor,anchor or (size[0]/2,size[1]/2),self.source_pil.size,size)
        self.render_source()
        self.source_canvas.focus_set()
        return "break"

    def _wheel(self, event):
        if event.delta:
            steps = event.delta/120 if abs(event.delta)>=120 else np.sign(event.delta)
            return self.zoom_source(1.25**np.clip(steps,-4,4),(event.x,event.y))
        return "break"

    def fit_source(self):
        if self.source_pil is not None and self.drag_index is None and self.pan_anchor is None:
            self.navigation.reset()
            self.render_source()
            self.source_canvas.focus_set()

    def focus_source(self):
        if self.selection is not None and self.drag_index is None and self.pan_anchor is None:
            self.navigation.focus(self.selection.points,self.source_pil.size,self._source_size())
            self.render_source()
            self.source_canvas.focus_set()

    def _space(self, pressed):
        self.space_down = pressed
        self.source_canvas.configure(cursor="fleur" if pressed or self.pan_anchor else "")
        return "break"

    def _pan_start(self, event):
        if self.source_pil is not None and self.drag_index is None:
            self.source_canvas.focus_set()
            self.pan_anchor = (event.x,event.y)
            self.source_canvas.configure(cursor="fleur")
        return "break"

    def _pan_move(self, event):
        if self.pan_anchor is not None:
            dx,dy = event.x-self.pan_anchor[0],event.y-self.pan_anchor[1]
            self.navigation.pan(dx,dy,self.source_pil.size,self._source_size())
            self.pan_anchor = (event.x,event.y)
            self.render_source()
        return "break"

    def _pan_end(self, event):
        self.pan_anchor = None
        self.source_canvas.configure(cursor="fleur" if self.space_down else "")
        return "break"

    def _shortcut(self, event, callback):
        # Enter and editing shortcuts must not save/reset a crop while the user
        # is interacting with the filter or navigating the image list.
        if self.busy and event.widget.winfo_class() not in {"TEntry","Entry","Text","TCombobox","Treeview","Listbox"}:
            callback()
            return "break"

    def _enter(self, event):
        if self.enter_down:
            return "break"
        self.enter_down = True
        return self._shortcut(event, lambda:self._decide("save"))

    def recrop(self):
        if self.selection is None or self.future is not None or not self.busy:
            return
        self.drag_index = self.reselect_point = None
        self.selection.reset()
        self._selection_changed()
        self.source_canvas.focus_set()

    def undo(self):
        if self.selection is not None and self.busy and self.future is None:
            self.drag_index = self.reselect_point = None
            self.selection.undo()
            self._selection_changed()

    def _decide(self, action):
        if not self.busy or self.action.get() != "pending":
            return
        if action=="save" and (self.future is not None or self.drag_index is not None or self.selection.accept() is None):
            return
        self._disable_actions()
        self.action.set(action)

    def stop(self):
        if self.busy:
            self.checkpoint_selection()
            self.aborted = True
            self._decide("abort")

    def fixed_batch_tick(self):
        """Service Pause/Stop/Close between unattended exports, without a review."""
        if self.closed:
            return
        self.selection = None
        self.action.set('pending')
        self._disable_actions()
        self.stop_button.configure(state='normal')
        self.pause_button.configure(state='normal')
        self.previous_button.configure(state='disabled')
        self.status.set('正在按已确认坐标批量导出 · 可暂停或结束 / Exporting with fixed coordinates · Pause/Stop available')
        self.root.update()

    def show_fixed_result(self, image, corners, cropped):
        if self.closed:
            return
        self.selection = None
        self.fixed_outline = corners.astype(float).tolist()
        self.source_pil = Image.fromarray(image[:,:,::-1])
        self.preview_pil = Image.fromarray(cropped[:,:,::-1])
        self.navigation.reset()
        self.render_source()
        self.render_preview()
        self.root.update_idletasks()

    def record(self, status, relative, detail):
        if self.closed:
            return
        self.stats={key:sum(row.get('status')==key for row in self.session.records.values()) for key in self.stats}
        self.stats['ok']=sum(row.get('saved',row.get('status')=='ok') for row in self.session.records.values())
        name=self.session.names[self.current_index]
        if self.session.records.get(name,{}).get('saved'):
            self.saved_crop_names.add(name)
        else:
            self.saved_crop_names.discard(name)
        self.update_picture_row(self.current_index)
        self.render_gallery()
        if status=="ok":
            self.preview_detail.set(f"{detail} px · 已保存 / Saved")

    def close(self):
        if self.closed:
            return
        self.remember_settings()
        if self.busy:
            try:
                self.checkpoint_selection()
                if self.session is not None:self.session.persist('stopped')
            except OSError as exc:
                print(f'Could not save the closing checkpoint: {exc}',file=sys.stderr)
        self.closed = self.aborted = True
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
        if self.future is not None:
            self.future.cancel()
        self.executor.shutdown(wait=False,cancel_futures=True)
        self.root.destroy()
