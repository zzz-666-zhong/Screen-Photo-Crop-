"""A persistent desktop workspace: original, editable corners, and crop together."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import sys

import numpy as np
from PIL import Image, ImageTk


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

    def reset(self):
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
            self.points.append(tuple(point))
            self.refresh()

    def undo(self):
        if self.points:
            self.points.pop()
        self.refresh()

    def accept(self):
        if self.preview is None:
            return None
        return self.backend.order_corners(np.float32(self.points)), self.preview.copy()


class CropWorkspace:
    BG = "#f3f5fa"
    TEXT = "#18243b"
    MUTED = "#69758a"
    ACCENT = "#4f46e5"
    TITLE = "拍屏裁剪工作台 / Screen Photo Crop"

    def __init__(self, backend):
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
        style.configure("Primary.TButton", background=self.ACCENT, foreground="white", borderwidth=0)
        style.map("Primary.TButton", background=[("disabled", "#c8ccdf"), ("active", "#4338ca")])
        style.configure("TEntry", padding=8, fieldbackground="white", font=("Microsoft YaHei UI", 10))
        style.configure("TRadiobutton", background="white", font=("Microsoft YaHei UI", 10), padding=5)
        style.configure("TCheckbutton", background="white", font=("Microsoft YaHei UI", 9), padding=3)
        style.configure("Horizontal.TProgressbar", background=self.ACCENT, troughcolor="#e0e5ef", borderwidth=0)

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
        ttk.Label(footer, textvariable=self.status, wraplength=1050, style="Hint.TLabel").pack(anchor="w")
        self.progress = ttk.Progressbar(footer, maximum=100)
        self.progress.pack(fill="x", pady=(8, 0))
        self.show_settings()

    def _settings_ui(self):
        ttk, tk = self.ttk, self.tk
        self.source = tk.StringVar()
        self.output = tk.StringVar()
        self.workflow = tk.StringVar(value="review")
        self.shape = tk.StringVar(value="full")
        self.recursive = tk.BooleanVar(value=False)
        self.overwrite = tk.BooleanVar(value=False)
        self.debug = tk.BooleanVar(value=False)
        self.trim = tk.BooleanVar(value=False)
        panel = self.settings
        panel.columnconfigure(1, weight=1)
        ttk.Label(panel, text="开始一批裁剪 / Start a batch", style="Card.TLabel",
                  font=("Microsoft YaHei UI", 15, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        for row, label, variable in ((1,"原照片 / Photos",self.source),(2,"结果目录 / Results",self.output)):
            ttk.Label(panel, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", padx=(0,12), pady=6)
            ttk.Entry(panel, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=6)
            ttk.Button(panel, text="选择 / Browse", command=lambda v=variable: self.browse(v)).grid(row=row, column=2, padx=(12,0))
        options = ttk.Frame(panel, style="Card.TFrame")
        options.grid(row=3, column=0, columnspan=3, sticky="ew", pady=6)
        options.columnconfigure((0,1), weight=1)
        modes = ttk.Frame(options, style="Card.TFrame")
        modes.grid(row=0, column=0, sticky="nw")
        ttk.Label(modes, text="01   处理方式 / Workflow", style="Card.TLabel", font=("Microsoft YaHei UI",11,"bold")).pack(anchor="w", pady=(0,5))
        for value, label in (("review","自动识别 · 逐张确认 / Review"),("manual","手动四角 · 逐张确认 / Manual"),("retry","失败图片补裁 / Retry failures")):
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
        ttk.Label(panel, text="原图与预览同页 · Enter 保存并下一张 / One page · Enter saves and advances",
                  style="Card.TLabel", foreground=self.MUTED, wraplength=900).grid(row=5, column=0, columnspan=3, sticky="w", pady=8)
        ttk.Button(panel, text="开始裁剪 / Start cropping", style="Primary.TButton", command=self._start).grid(row=6,column=0,columnspan=3,sticky="w")

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
        panes.rowconfigure(1, weight=1)
        ttk.Label(panes, text="01   原图 · 点击重选四角 / Original · Click to reselect").grid(row=0,column=0,sticky="w",pady=(0,8))
        ttk.Label(panes, text="02   裁剪预览 / Crop preview").grid(row=0,column=1,sticky="w",pady=(0,8),padx=(14,0))
        self.source_canvas = tk.Canvas(panes, background="#111c30", highlightthickness=0, width=400, height=350)
        self.preview_canvas = tk.Canvas(panes, background="white", highlightthickness=1, highlightbackground="#dfe5ee", width=400, height=350)
        self.source_canvas.grid(row=1,column=0,sticky="nsew")
        self.preview_canvas.grid(row=1,column=1,sticky="nsew",padx=(14,0))
        self.source_canvas.bind("<Configure>", lambda e: self.render_source())
        self.preview_canvas.bind("<Configure>", lambda e: self.render_preview())
        self.source_canvas.bind("<Button-1>", self._click)
        self.source_canvas.bind("<B1-Motion>", self._drag)
        self.source_canvas.bind("<ButtonRelease-1>", self._release)
        self.source_canvas.bind("<Button-3>", lambda e: self.undo())
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

    def browse(self, variable):
        from tkinter import filedialog
        path = filedialog.askdirectory(parent=self.root, title="选择文件夹 / Choose a folder")
        if path:
            variable.set(path)

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
            argv = [source, output, "--manual" if self.workflow.get()=="manual" else "--review"]
        for enabled, option in ((self.shape.get()=="square","--square"),(self.recursive.get(),"--recursive"),
                                (self.overwrite.get(),"--overwrite"),(self.debug.get(),"--debug"),(self.trim.get(),"--trim-black")):
            if enabled:
                argv.append(option)
        self.aborted = False
        self.stats = dict(ok=0, skipped=0, error=0, existing=0)
        try:
            result = self.backend.run(self.backend.parser().parse_args(argv), workspace=self)
        except (ValueError, OSError) as exc:
            self.busy = False
            self.status.set(str(exc))
            return
        if not self.closed:
            self.busy = False
            self.settings_button.configure(state="normal")
            self._disable_actions()
            self.status.set(f"{'本批已停止' if self.aborted else '本批已完成'} / Batch {'stopped' if self.aborted else 'complete'} · 保存 {self.stats['ok']} · 跳过 {self.stats['skipped']} · 错误 {self.stats['error']}  |  返回设置可开始下一批")
            self.progress.configure(value=100 if not self.aborted else self.progress['value'])

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
        self.mode_badge.set("正方形 1:1 / Square" if args.square else "完整图片 / Full picture")
        self.selection = CropSelection(image, args, self.backend)
        self.drag_index = None
        self.reselect_point = None
        self.source_pil = Image.fromarray(image[:,:,::-1])
        self.preview_pil = None
        self.action.set("pending")
        self._disable_actions()
        self.skip_button.configure(state="normal")
        self.stop_button.configure(state="normal")
        self.status.set("正在识别边界，可跳过或结束 / Detecting boundaries…")
        self.root.update_idletasks()
        self.render_source()
        self.render_preview()
        if proposed is not None:
            self.selection.set_corners(proposed)
            self._selection_changed()
        elif auto_detect:
            self.future = self.executor.submit(self.backend.detect_screen, image, square=args.square)
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
        except Exception as exc:
            error = str(exc)
        self.future = None
        self._selection_changed()
        if error:
            self.status.set(f"识别不可用，请手动选四角 / Select corners manually · {error}")

    def _disable_actions(self):
        for button in (self.save_button,self.reset_button,self.undo_button,self.skip_button,self.stop_button):
            button.configure(state="disabled")

    def _selection_changed(self):
        preview = self.selection.preview
        self.preview_pil = Image.fromarray(preview[:,:,::-1]) if preview is not None else None
        ready = preview is not None and self.drag_index is None
        self.save_button.configure(state="normal" if ready else "disabled")
        self.reset_button.configure(state="normal")
        self.undo_button.configure(state="normal" if self.selection.points else "disabled")
        self.preview_detail.set(f"{preview.shape[1]} × {preview.shape[0]} px · 尚未保存 / Not saved" if ready else "等待有效四角 / Waiting for valid corners")
        self.status.set(self.selection.error or ("预览已就绪 · 点击原图重选；拖动角点微调；Enter 保存并下一张 / Click original: reselect · Drag: adjust · Enter: save & next" if ready else f"请按顺序选四角 · 已选 {len(self.selection.points)}/4；可拖动角点 / Select 4 corners; drag to adjust"))
        self.render_source()
        self.render_preview()

    def render_source(self):
        canvas = self.source_canvas
        canvas.delete("all")
        if self.source_pil is None:
            return
        self.viewport = ImageViewport.fit(self.source_pil.size, (canvas.winfo_width(),canvas.winfo_height()))
        view = self.viewport
        self.source_photo = ImageTk.PhotoImage(self.source_pil.resize((view.width,view.height),Image.Resampling.LANCZOS),master=self.root)
        canvas.create_image(view.x,view.y,image=self.source_photo,anchor="nw")
        if self.selection is None:
            return
        points = [view.to_canvas(p) for p in self.selection.points]
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
        if self.drag_index is None:
            return
        point = self.viewport.to_image(event.x,event.y)
        if point is not None:
            if self.reselect_point is not None:
                if np.linalg.norm(np.array(point)-self.reselect_point)*self.viewport.scale < 3:
                    return
                self.reselect_point = None
            self.selection.points[self.drag_index] = point
            self.selection.preview = None
            self.save_button.configure(state="disabled")
            self.render_source()

    def _release(self, event):
        if self.drag_index is not None:
            self.drag_index = None
            if self.reselect_point is not None:
                point, self.reselect_point = self.reselect_point, None
                self.selection.reset()
                self.selection.add(point)
            else:
                self.selection.refresh()
            self._selection_changed()

    def _shortcut(self, event, callback):
        if self.busy and event.widget.winfo_class() not in {"TEntry","Entry","Text"}:
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
            self.aborted = True
            self._decide("abort")

    def record(self, status, relative, detail):
        if self.closed:
            return
        if status in self.stats:
            self.stats[status]+=1
        numbers = self.counter.get().split("/")
        if len(numbers)==2:
            self.progress.configure(value=int(numbers[0])/max(1,int(numbers[1]))*100)
        if status=="ok":
            self.preview_detail.set(f"{detail} px · 已保存 / Saved")

    def close(self):
        if self.closed:
            return
        self.closed = self.aborted = True
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
        if self.future is not None:
            self.future.cancel()
        self.executor.shutdown(wait=False,cancel_futures=True)
        self.root.destroy()
