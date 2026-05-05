import tkinter as tk
import tkinter.font as tkfont
import json
import os
import sys
import math
import threading
import winsound
from datetime import datetime, timedelta
from timer import Timer
from config import (
    DEFAULT_FOCUS_MIN, DEFAULT_BREAK_MIN, DEFAULT_LONG_BREAK_MIN,
    WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR, SIDEBAR_WIDTH,
    DEFAULT_SETTINGS, LIGHT_COLORS,
)

# 字体选择说明：
# 使用 "Noto Sans SC"（思源黑体）作为统一字体，理由如下：
# 1. 中英文混排时字形风格一致，不会出现中英文字体风格割裂的问题
# 2. Google 与 Adobe 联合开发，开源免费（SIL 许可），无商业授权风险
# 3. 支持 Thin/Light/Regular/Medium/Bold/Black 六种字重，
#    可通过字重建立层次（标题 Bold、正文 Regular、辅助文字 Light），无需切换字体族
# 4. Windows/macOS/Linux 均可使用，打包时可内嵌字体文件保证一致性
# 5. 字面率高、中宫开阔，在小字号下依然清晰可读，适合桌面工具 UI
FTK = "Noto Sans SC"

# 统一色系
_C = dict(LIGHT_COLORS)


def _round_rect(canvas, x1, y1, x2, y2, r=12, **kwargs):
    """在 Canvas 上绘制圆角矩形"""
    points = [
        x1 + r, y1, x2 - r, y1,
        x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r,
        x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def _canvas_btn(parent, text, command, card_bg=None, w=46, h=36):
    """带圆角背景的按钮 Canvas，hover 变色、点击闪烁"""
    if card_bg is None:
        card_bg = _C["card"]
    cv = tk.Canvas(parent, width=w, height=h,
                   bg=card_bg, highlightthickness=0, cursor="hand2")
    rect = _round_rect(cv, 2, 2, w - 2, h - 2, r=10,
                       fill=card_bg, outline=_C["border"])
    cv.create_text(w // 2, h // 2, text=text, font=(FTK, 14), fill=_C["pri"])
    cv._rect = rect
    cv._cmd = command
    cv._card_bg = card_bg
    cv._text = text

    def hover(_):
        cv.itemconfig(rect, fill=_C["hover"])
    def leave(_):
        cv.itemconfig(rect, fill=cv._card_bg)
    def click(_):
        cv.itemconfig(rect, fill=_C["active"])
        cv.after(100, lambda: cv.itemconfig(rect, fill=_C["hover"]))
        cv.after(120, cv._cmd)

    cv.bind("<Enter>", hover)
    cv.bind("<Leave>", leave)
    cv.bind("<Button-1>", click)
    return cv


def _bind_tooltip(widget, text):
    """绑定鼠标悬停提示"""
    tip = {"win": None}

    def enter(event):
        x = widget.winfo_rootx() + widget.winfo_width() // 2
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        win = tk.Toplevel(widget)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"+{x}+{y}")
        lbl = tk.Label(win, text=text, font=(FTK, 9),
                       fg=_C["pri"], bg="#ffffe0", relief="solid", bd=1, padx=6, pady=2)
        lbl.pack()
        tip["win"] = win

    def leave(event):
        if tip["win"]:
            tip["win"].destroy()
            tip["win"] = None

    widget.bind("<Enter>", enter, add="+")
    widget.bind("<Leave>", leave, add="+")


def _win_notify(title, message):
    """Windows 原生气泡通知（Shell_NotifyIconW）"""
    import ctypes
    from ctypes import wintypes

    NIM_ADD = 0x00000000
    NIM_DELETE = 0x00000002
    NIF_INFO = 0x00000010
    NIIF_NONE = 0x00000000

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HICON),
            ("szTip", ctypes.c_wchar * 128),
            ("dwState", wintypes.DWORD),
            ("dwStateMask", wintypes.DWORD),
            ("szInfo", ctypes.c_wchar * 256),
            ("uVersion", wintypes.UINT),
            ("szInfoTitle", ctypes.c_wchar * 64),
            ("dwInfoFlags", wintypes.DWORD),
        ]

    nid = NOTIFYICONDATAW()
    nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
    nid.uID = 1001
    nid.uFlags = NIF_INFO
    nid.szInfoTitle = title
    nid.szInfo = message
    nid.dwInfoFlags = NIIF_NONE

    Shell_NotifyIconW = ctypes.windll.shell32.Shell_NotifyIconW
    Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _remove():
        Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))

    threading.Timer(5.0, _remove, daemon=True).start()


def _round_entry(parent, placeholder="", width=160, height=28):
    """圆角输入框 Canvas"""
    cv = tk.Canvas(parent, width=width, height=height,
                   bg=_C["bg"], highlightthickness=0)
    _round_rect(cv, 1, 1, width - 1, height - 1, r=10,
                fill=_C["card"], outline=_C["border"], width=1)
    entry = tk.Entry(cv, font=(FTK, 10), bd=0, relief="flat",
                     bg=_C["card"], fg=_C["mute"], insertwidth=1,
                     highlightthickness=0)
    cv.create_window(8, height // 2, window=entry, anchor="w",
                     width=width - 16, height=height - 8)
    if placeholder:
        entry.insert(0, placeholder)
    cv._entry = entry
    return cv, entry


def _sb_btn(parent, label, command, selected=False):
    """侧边栏导航按钮 — 左侧窄竖线指示器"""
    wrapper = tk.Frame(parent, bg=_C["sidebar"])
    wrapper._selected = selected
    wrapper._cmd = command

    # 指示条
    ind = tk.Frame(wrapper, width=3, bg=_C["sb_sel"] if selected else _C["sidebar"])
    ind.pack(side=tk.LEFT, fill=tk.Y)

    # 文字
    fg = _C["sb_sel"] if selected else _C["sb_text"]
    fnt = (FTK, 11, "bold") if selected else (FTK, 11)
    lbl = tk.Label(wrapper, text=label, font=fnt,
                   fg=fg, bg=_C["sidebar"], cursor="hand2", width=6, height=1)
    lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
    wrapper._lbl = lbl
    wrapper._ind = ind

    def hover(e):
        if not wrapper._selected:
            lbl.config(fg=_C["sb_sel"])
            ind.config(bg=_C["sb_hover"])
        wrapper.config(bg=_C["sb_hover"])
    def leave(e):
        lbl.config(fg=_C["sb_sel"] if wrapper._selected else _C["sb_text"])
        ind.config(bg=_C["sb_sel"] if wrapper._selected else _C["sidebar"])
        wrapper.config(bg=_C["sidebar"])
    def click(e):
        wrapper._cmd()

    for w in (wrapper, lbl, ind):
        w.bind("<Enter>", hover)
        w.bind("<Leave>", leave)
        w.bind("<Button-1>", click)
    return wrapper


class FlowTickApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FlowTick")
        sx = (self.root.winfo_screenwidth() - WINDOW_WIDTH) // 2
        sy = (self.root.winfo_screenheight() - WINDOW_HEIGHT) // 2
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{sx}+{sy}")

        self.focus_min = DEFAULT_FOCUS_MIN
        self.break_min = DEFAULT_BREAK_MIN
        self.pomodoro_count = 0

        # 路径
        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        self.notes_file = os.path.join(base_dir, "notes.json")
        self.events_file = os.path.join(base_dir, "events.json")
        self.stats_file = os.path.join(base_dir, "stats.json")
        self.settings_file = os.path.join(base_dir, "settings.json")
        self.todos_file = os.path.join(base_dir, "todos.json")

        # 加载数据
        self.settings = self._load_settings()
        self.notes = self._load_notes()
        self.events = self._load_json(self.events_file)
        self.stats = self._load_stats()
        self.todos = self._load_json(self.todos_file)

        self._build_ui()
        self._refresh_events()
        self._refresh_notes()
        self._refresh_todos()
        self._init_timer()
        self._update_clock()
        self._tray_running = False
        self._init_tray()
        self._apply_settings()

        # 关闭按钮行为
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 快捷键
        self._shortcuts = [
            ("<space>", lambda e: self._on_toggle()),
            ("<r>", lambda e: self._on_reset()),
            ("<n>", lambda e: self._add_note()),
        ]
        self._bind_shortcuts()

    def _bind_shortcuts(self):
        for seq, func in self._shortcuts:
            self.root.bind(seq, func)

    def _unbind_shortcuts(self):
        for seq, _ in self._shortcuts:
            self.root.unbind(seq)

    def _on_entry_focus(self, entry, placeholder):
        self._unbind_shortcuts()
        if entry.get() == placeholder:
            entry.delete(0, tk.END)
            entry.config(fg=_C["pri"])

    def _on_entry_blur(self, entry, placeholder):
        self._bind_shortcuts()
        text = entry.get().strip()
        if not text:
            entry.delete(0, tk.END)
            entry.insert(0, placeholder)
            entry.config(fg=_C["mute"])
        if hasattr(self, "_ev_search") and entry is self._ev_search:
            self._refresh_events()
        elif hasattr(self, "_nt_search") and entry is self._nt_search:
            self._refresh_notes()

    # ── 设置 ─────────────────────────────────────────────

    def _load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    s = json.load(f)
                    merged = dict(DEFAULT_SETTINGS)
                    merged.update(s)
                    return merged
        except Exception:
            pass
        return dict(DEFAULT_SETTINGS)

    def _save_settings(self):
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _apply_settings(self):
        self.root.attributes('-topmost', self.settings.get("always_on_top", False))
        self._start_idle_check()

    def _get_idle_seconds(self):
        """获取用户闲置秒数（Windows）"""
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return millis / 1000.0
        return 0

    def _start_idle_check(self):
        if hasattr(self, "_idle_job"):
            self.root.after_cancel(self._idle_job)
        self._idle_check_loop()

    def _idle_check_loop(self):
        if self.settings.get("idle_detection", False) and self.timer.state == Timer.RUNNING:
            timeout = self.settings.get("idle_timeout_min", 5) * 60
            if self._get_idle_seconds() >= timeout:
                self.timer.pause()
                self._redraw_btn(self.toggle_btn, "▶")
                self._update_goal_display()
        self._idle_job = self.root.after(10000, self._idle_check_loop)

    def _on_close(self):
        if self.settings.get("minimize_to_tray", True):
            self._hide_to_tray()
        else:
            self._quit_from_tray()

    # ── UI ─────────────────────────────────────────────

    def _build_ui(self):
        main = tk.Frame(self.root, bg=_C["bg"])
        main.pack(fill=tk.BOTH, expand=True)

        # 侧边栏
        sidebar = tk.Frame(main, bg=_C["sidebar"], width=SIDEBAR_WIDTH)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        nav_frame = tk.Frame(sidebar, bg=_C["sidebar"])
        nav_frame.pack(fill=tk.X, pady=(8, 0))

        self._nav_btns = {}
        pages = [("home", "首页"), ("events", "事件"),
                 ("notes", "笔记"), ("todos", "待办"),
                 ("stats", "统计")]
        for key, label in pages:
            btn = _sb_btn(nav_frame, label,
                          lambda k=key: self._switch_page(k))
            btn.pack(fill=tk.X, pady=6)
            self._nav_btns[key] = btn

        bottom_nav = tk.Frame(sidebar, bg=_C["sidebar"])
        bottom_nav.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 8))
        self._nav_btns["settings"] = _sb_btn(
            bottom_nav, "设置", lambda: self._switch_page("settings"))
        self._nav_btns["settings"].pack(fill=tk.X, pady=6)

        # 内容区
        self._content = tk.Frame(main, bg=_C["bg"])
        self._content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._pages = {}
        self._build_home_page()
        self._build_events_page()
        self._build_notes_page()
        self._build_todos_page()
        self._build_stats_page()
        self._build_settings_page()

        self._switch_page("home")

    def _switch_page(self, name):
        for k, btn in self._nav_btns.items():
            sel = (k == name)
            btn._selected = sel
            btn._lbl.config(
                font=(FTK, 11, "bold") if sel else (FTK, 11),
                fg=_C["sb_sel"] if sel else _C["sb_text"])
            btn._ind.config(bg=_C["sb_sel"] if sel else _C["sidebar"])

        for p in self._pages.values():
            p.pack_forget()
        if name in self._pages:
            self._pages[name].pack(in_=self._content, fill=tk.BOTH, expand=True)

        if name == "stats":
            self._refresh_stats_page()
        elif name == "settings":
            self._refresh_settings_page()

    # ── 首页 ─────────────────────────────────────────

    def _build_home_page(self):
        page = tk.Frame(self._content, bg=_C["bg"])
        page.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        self._pages["home"] = page

        self.top_canvas = tk.Canvas(page, bg=_C["bg"], highlightthickness=0)
        self.top_canvas.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(self.top_canvas, bg=_C["card"])
        self.clock_size = 150
        self.clock_canvas = tk.Canvas(
            left, width=self.clock_size, height=self.clock_size,
            bg=_C["card"], highlightthickness=0,
        )
        self.clock_canvas.pack(pady=(12, 6))
        self.clock_label = tk.Label(
            left, text="--:--:--", font=(FTK, 20),
            bg=_C["card"], fg="black",
        )
        self.clock_label.pack(pady=(0, 12))

        right = tk.Frame(self.top_canvas, bg=_C["card"])
        self.focus_topic = ""

        self.mode_label = tk.Label(
            right, text="专注", font=(FTK, 16, "bold"),
            bg=_C["card"], fg=_C["sec"],
        )
        self.mode_label.pack(pady=(16, 0))

        self.topic_label = tk.Label(
            right, text="准备就绪", font=(FTK, 10),
            bg=_C["card"], fg=_C["mute"],
        )
        self.topic_label.pack(pady=(2, 0))

        self.timer_box = tk.Canvas(
            right, width=180, height=65,
            bg=_C["card"], highlightthickness=0,
        )
        self.timer_box.pack(pady=(20, 0))
        _round_rect(self.timer_box, 2, 2, 180, 65, r=14,
                    fill=_C["bg"], outline=_C["border"], width=1.5)
        self.timer_label = tk.Label(
            self.timer_box, text="25:00", font=(FTK, 36, "bold"),
            bg=_C["bg"], fg=_C["pri"],
        )
        self.timer_box.create_window(91, 34, window=self.timer_label)

        self._btn_row = tk.Frame(right, bg=_C["card"])
        self._btn_row.pack(pady=(14, 14))

        self.time_btn = _canvas_btn(self._btn_row, "⏱", self._on_set_time)
        self.time_btn.pack(side=tk.LEFT, padx=8)
        _bind_tooltip(self.time_btn, "设置时长")
        self.toggle_btn = _canvas_btn(self._btn_row, "▶", self._on_toggle)
        self.toggle_btn.pack(side=tk.LEFT, padx=8)
        _bind_tooltip(self.toggle_btn, "开始/暂停 (Space)")
        self.reset_btn = _canvas_btn(self._btn_row, "↺", self._on_reset)
        self.reset_btn.pack(side=tk.LEFT, padx=8)
        _bind_tooltip(self.reset_btn, "重置 (R)")

        self._left_frame = left
        self._right_frame = right
        self.top_canvas.bind("<Configure>", self._on_top_resize)

    # ── 事件页 ────────────────────────────────────────

    def _build_events_page(self):
        page = tk.Frame(self._content, bg=_C["bg"])
        self._pages["events"] = page

        self.events_canvas = tk.Canvas(page, bg=_C["bg"], highlightthickness=0)
        self.events_canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        events_outer = tk.Frame(self.events_canvas, bg=_C["card"])
        self.events_log_canvas = tk.Canvas(events_outer, bg=_C["card"], highlightthickness=0)
        events_sb = tk.Scrollbar(events_outer, command=self.events_log_canvas.yview)
        self.events_log_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        events_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.events_log_canvas.configure(yscrollcommand=events_sb.set)
        self.events_inner = tk.Frame(self.events_log_canvas, bg=_C["card"])
        self.events_log_canvas.create_window((0, 0), window=self.events_inner, anchor="nw")
        self.events_inner.bind("<Configure>",
                               lambda e: self.events_log_canvas.configure(scrollregion=self.events_log_canvas.bbox("all")))
        self.events_log_canvas.bind("<MouseWheel>",
                                    lambda e: self.events_log_canvas.yview_scroll(int(-e.delta / 120), "units"))
        self._events_outer = events_outer
        self._ev_search_cv, self._ev_search = _round_entry(page, "搜索事项...", width=160, height=28)
        self._ev_search.bind("<FocusIn>", lambda e: self._on_entry_focus(self._ev_search, "搜索事项..."))
        self._ev_search.bind("<FocusOut>", lambda e: self._on_entry_blur(self._ev_search, "搜索事项..."))
        self._ev_search.bind("<KeyRelease>", lambda e: self._refresh_events())
        self.events_canvas.bind("<Configure>", self._on_events_resize)

    # ── 笔记页 ────────────────────────────────────────

    def _build_notes_page(self):
        page = tk.Frame(self._content, bg=_C["bg"])
        self._pages["notes"] = page

        self.notes_canvas = tk.Canvas(page, bg=_C["bg"], highlightthickness=0)
        self.notes_canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        notes_outer = tk.Frame(self.notes_canvas, bg=_C["card"])
        self.notes_log_canvas = tk.Canvas(notes_outer, bg=_C["card"], highlightthickness=0)
        notes_sb = tk.Scrollbar(notes_outer, command=self.notes_log_canvas.yview)
        self.notes_log_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        notes_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.notes_log_canvas.configure(yscrollcommand=notes_sb.set)
        self.notes_inner = tk.Frame(self.notes_log_canvas, bg=_C["card"])
        self.notes_log_canvas.create_window((0, 0), window=self.notes_inner, anchor="nw")
        self.notes_inner.bind("<Configure>",
                              lambda e: self.notes_log_canvas.configure(scrollregion=self.notes_log_canvas.bbox("all")))
        self.notes_log_canvas.bind("<MouseWheel>",
                                   lambda e: self.notes_log_canvas.yview_scroll(int(-e.delta / 120), "units"))

        plus_canvas = tk.Canvas(self.notes_canvas, width=32, height=32,
                                bg=_C["card"], highlightthickness=0)
        plus_canvas.create_oval(2, 2, 30, 30, fill=_C["bg"], outline=_C["border"])
        plus_canvas.create_text(16, 16, text="+", font=(FTK, 16, "bold"), fill=_C["sec"])
        plus_canvas.bind("<Button-1>", lambda e: self._add_note())
        _bind_tooltip(plus_canvas, "添加笔记 (N)")
        self._plus_btn = plus_canvas
        self._notes_outer = notes_outer
        self._nt_search_cv, self._nt_search = _round_entry(page, "搜索笔记...", width=160, height=28)
        self._nt_search.bind("<FocusIn>", lambda e: self._on_entry_focus(self._nt_search, "搜索笔记..."))
        self._nt_search.bind("<FocusOut>", lambda e: self._on_entry_blur(self._nt_search, "搜索笔记..."))
        self._nt_search.bind("<KeyRelease>", lambda e: self._refresh_notes())
        self.notes_canvas.bind("<Configure>", self._on_notes_resize)

    # ── 待办页 ────────────────────────────────────────

    def _build_todos_page(self):
        page = tk.Frame(self._content, bg=_C["bg"])
        self._pages["todos"] = page

        self.todos_canvas = tk.Canvas(page, bg=_C["bg"], highlightthickness=0)
        self.todos_canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        todos_outer = tk.Frame(self.todos_canvas, bg=_C["card"])
        self.todos_log_canvas = tk.Canvas(todos_outer, bg=_C["card"], highlightthickness=0)
        todos_sb = tk.Scrollbar(todos_outer, command=self.todos_log_canvas.yview)
        self.todos_log_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        todos_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.todos_log_canvas.configure(yscrollcommand=todos_sb.set)
        self.todos_inner = tk.Frame(self.todos_log_canvas, bg=_C["card"])
        self.todos_log_canvas.create_window((0, 0), window=self.todos_inner, anchor="nw")
        self.todos_inner.bind("<Configure>",
                              lambda e: self.todos_log_canvas.configure(scrollregion=self.todos_log_canvas.bbox("all")))
        self.todos_log_canvas.bind("<MouseWheel>",
                                   lambda e: self.todos_log_canvas.yview_scroll(int(-e.delta / 120), "units"))
        self._todos_outer = todos_outer

        plus_canvas = tk.Canvas(self.todos_canvas, width=32, height=32,
                                bg=_C["card"], highlightthickness=0)
        plus_canvas.create_oval(2, 2, 30, 30, fill=_C["bg"], outline=_C["border"])
        plus_canvas.create_text(16, 16, text="+", font=(FTK, 16, "bold"), fill=_C["sec"])
        plus_canvas.bind("<Button-1>", lambda e: self._add_todo())
        _bind_tooltip(plus_canvas, "添加待办 (Enter)")
        self._td_plus_btn = plus_canvas

        self._td_search_cv, self._td_search = _round_entry(page, "添加待办...", width=160, height=28)
        self._td_search.bind("<FocusIn>", lambda e: self._on_entry_focus(self._td_search, "添加待办..."))
        self._td_search.bind("<FocusOut>", lambda e: self._on_entry_blur(self._td_search, "添加待办..."))
        self._td_search.bind("<Return>", lambda e: self._add_todo())

        self.todos_canvas.bind("<Configure>", self._on_todos_resize)

    # ── 数据 ───────────────────────────────────────────

    def _load_json(self, path):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_json(self, path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_notes(self):
        # 向后兼容：优先 notes.json，退回 events.json
        if os.path.exists(self.notes_file):
            return self._load_json(self.notes_file)
        old = os.path.join(os.path.dirname(self.notes_file), "events.json")
        if os.path.exists(old):
            data = self._load_json(old)
            self._save_json(self.notes_file, data)
            return data
        return []

    def _save_notes(self):
        self._save_json(self.notes_file, self.notes)

    def _save_events(self):
        self._save_json(self.events_file, self.events)

    def _load_stats(self):
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_stats(self):
        try:
            with open(self.stats_file, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _record_focus(self):
        """记录一次专注完成"""
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.stats:
            self.stats[today] = {"count": 0, "minutes": 0, "topics": []}
        self.stats[today]["count"] += 1
        self.stats[today]["minutes"] += self.focus_min
        if self.focus_topic:
            self.stats[today]["topics"].append(self.focus_topic)
        self._save_stats()

        # 自动记录到事件
        now = datetime.now().strftime("%m-%d %H:%M")
        self.events.append({
            "time": now,
            "topic": self.focus_topic or "未命名专注",
            "minutes": self.focus_min,
        })
        self._save_events()

    # ── 事件卡片 ───────────────────────────────────────

    def _refresh_events(self):
        kw = self._ev_search.get().strip()
        if kw == "搜索事项...":
            kw = ""

        for w in self.events_inner.winfo_children():
            w.destroy()

        if not self.events:
            tk.Label(
                self.events_inner, text="完成专注后自动记录",
                font=(FTK, 11), fg=_C["mute"], bg=_C["card"],
            ).pack(expand=True, pady=30)
            self.events_inner.update_idletasks()
            self.events_log_canvas.configure(scrollregion=self.events_log_canvas.bbox("all"))
            return

        shown = [(idx, ev) for idx, ev in enumerate(self.events)
                 if not kw or kw.lower() in ev.get("topic", "").lower()]

        if not shown:
            tk.Label(
                self.events_inner, text="无匹配结果",
                font=(FTK, 11), fg=_C["mute"], bg=_C["card"],
            ).pack(expand=True, pady=30)
            self.events_inner.update_idletasks()
            self.events_log_canvas.configure(scrollregion=self.events_log_canvas.bbox("all"))
            return

        for idx, ev in shown:
            item = tk.Frame(self.events_inner, bg=_C["item_bg"])
            item.pack(fill=tk.X, padx=6, pady=2)

            # 时间
            tk.Label(
                item, text=ev.get("time", ""), font=(FTK, 9),
                fg=_C["mute"], bg=_C["item_bg"],
            ).pack(side=tk.LEFT, padx=(8, 6), pady=4)

            # 事项
            tk.Label(
                item, text=ev.get("topic", ""), font=(FTK, 11),
                fg=_C["pri"], bg=_C["item_bg"], anchor="w",
            ).pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4)

            # 时长
            tk.Label(
                item, text=f"{ev.get('minutes', 0)}分钟", font=(FTK, 9),
                fg=_C["sec"], bg=_C["item_bg"],
            ).pack(side=tk.LEFT, padx=(0, 4), pady=4)

            # 删除按钮
            del_btn = tk.Label(
                item, text="×", font=(FTK, 14),
                fg=_C["border"], bg=_C["item_bg"], cursor="hand2",
            )
            del_btn.pack(side=tk.RIGHT, padx=(0, 4), pady=4)
            del_btn.bind("<Button-1>", lambda e, i=idx: self._delete_event_at(i))
            del_btn.bind("<Enter>", lambda e: e.widget.config(fg=_C["accent"]))
            del_btn.bind("<Leave>", lambda e: e.widget.config(fg=_C["border"]))
            item.bind("<Button-3>", lambda e, i=idx: self._show_event_ctx(e, i))

        self.events_inner.update_idletasks()
        self.events_log_canvas.configure(scrollregion=self.events_log_canvas.bbox("all"))

    def _delete_event_at(self, idx):
        self.events.pop(idx)
        self._save_events()
        self._refresh_events()

    def _show_event_ctx(self, event, idx):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="删除", command=lambda: self._delete_event_at(idx))
        menu.post(event.x_root, event.y_root)

    def _on_events_resize(self, event):
        c = self.events_canvas
        w, h = event.width, event.height
        if w < 60 or h < 60:
            return
        c.delete("ev_bg")
        _round_rect(c, 4, 4, w - 2, h - 2, r=14, fill=_C["shadow"], outline="", tags="ev_bg")
        _round_rect(c, 2, 2, w - 4, h - 4, r=14, fill=_C["card"], outline=_C["border"], width=1, tags="ev_bg")
        c.create_text(16, 22, text="事件", font=(FTK, 15, "bold"),
                      fill=_C["pri"], anchor="w", tags="ev_bg")
        c.create_window(w - 14, 22, window=self._ev_search_cv, anchor="e", tags="ev_bg")
        c.create_line(12, 42, w - 12, 42, fill=_C["border"], width=1, tags="ev_bg")
        c.create_window(10, 48, window=self._events_outer, anchor="nw",
                        width=w - 20, height=h - 52, tags="ev_bg")

    # ── 笔记卡片 ───────────────────────────────────────

    def _refresh_notes(self):
        kw = self._nt_search.get().strip()
        if kw == "搜索笔记...":
            kw = ""

        for w in self.notes_inner.winfo_children():
            w.destroy()

        if not self.notes:
            tk.Label(
                self.notes_inner, text="暂无笔记，点击 + 添加",
                font=(FTK, 11), fg=_C["mute"], bg=_C["card"],
            ).pack(expand=True, pady=30)
            self.notes_inner.update_idletasks()
            self.notes_log_canvas.configure(scrollregion=self.notes_log_canvas.bbox("all"))
            return

        shown = [(idx, note) for idx, note in enumerate(self.notes)
                 if not kw or kw.lower() in note.get("title", "").lower()
                 or kw.lower() in note.get("content", "").lower()]

        if not shown:
            tk.Label(
                self.notes_inner, text="无匹配结果",
                font=(FTK, 11), fg=_C["mute"], bg=_C["card"],
            ).pack(expand=True, pady=30)
            self.notes_inner.update_idletasks()
            self.notes_log_canvas.configure(scrollregion=self.notes_log_canvas.bbox("all"))
            return

        for idx, note in shown:
            item = tk.Frame(self.notes_inner, bg=_C["item_bg"])
            item.pack(fill=tk.X, padx=6, pady=2)

            top_row = tk.Frame(item, bg=_C["item_bg"])
            top_row.pack(fill=tk.X, padx=8, pady=(6, 0))

            title_lbl = tk.Label(
                top_row, text=note["title"], font=(FTK, 12, "bold"),
                fg=_C["pri"], bg=_C["item_bg"], anchor="w",
            )
            title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

            if note.get("time"):
                tk.Label(
                    top_row, text=note["time"], font=(FTK, 9),
                    fg=_C["mute"], bg=_C["item_bg"],
                ).pack(side=tk.LEFT, padx=(4, 0))

            del_btn = tk.Label(
                top_row, text="×", font=(FTK, 14),
                fg=_C["border"], bg=_C["item_bg"], cursor="hand2",
            )
            del_btn.pack(side=tk.RIGHT, padx=(4, 0))
            del_btn.bind("<Button-1>", lambda e, i=idx: self._delete_note_at(i))
            del_btn.bind("<Enter>", lambda e: e.widget.config(fg=_C["accent"]))
            del_btn.bind("<Leave>", lambda e: e.widget.config(fg=_C["border"]))

            content_lbl = None
            if note["content"]:
                font_spec = (FTK, 10)
                display = self._truncate(note["content"], font_spec, 180)
                content_lbl = tk.Label(
                    item, text=display, font=font_spec,
                    fg=_C["sec"], bg=_C["item_bg"], anchor="w",
                )
                content_lbl.pack(fill=tk.X, padx=8, pady=(0, 6))
            else:
                tk.Frame(item, bg=_C["item_bg"], height=4).pack()

            widgets = [item, title_lbl]
            if content_lbl:
                widgets.append(content_lbl)
            for widget in widgets:
                widget.bind("<Double-1>", lambda e, i=idx: self._edit_note_at(i))
                widget.bind("<Button-3>", lambda e, i=idx: self._show_note_ctx(e, i))

        self.notes_inner.update_idletasks()
        self.notes_log_canvas.configure(scrollregion=self.notes_log_canvas.bbox("all"))

    def _on_notes_resize(self, event):
        c = self.notes_canvas
        w, h = event.width, event.height
        if w < 60 or h < 60:
            return
        c.delete("nt_bg")
        _round_rect(c, 4, 4, w - 2, h - 2, r=14, fill=_C["shadow"], outline="", tags="nt_bg")
        _round_rect(c, 2, 2, w - 4, h - 4, r=14, fill=_C["card"], outline=_C["border"], width=1, tags="nt_bg")
        c.create_text(16, 22, text="笔记", font=(FTK, 15, "bold"),
                      fill=_C["pri"], anchor="w", tags="nt_bg")
        c.create_window(w - 16, 22, window=self._plus_btn, anchor="e", tags="nt_bg")
        c.create_window(w - 56, 22, window=self._nt_search_cv, anchor="e", tags="nt_bg")
        c.create_line(12, 42, w - 12, 42, fill=_C["border"], width=1, tags="nt_bg")
        c.create_window(10, 48, window=self._notes_outer, anchor="nw",
                        width=w - 20, height=h - 52, tags="nt_bg")

    # ── 待办 ───────────────────────────────────────────

    def _save_todos(self):
        self._save_json(self.todos_file, self.todos)

    def _refresh_todos(self):
        for w in self.todos_inner.winfo_children():
            w.destroy()

        if not self.todos:
            tk.Label(
                self.todos_inner, text="暂无待办，输入后添加",
                font=(FTK, 11), fg=_C["mute"], bg=_C["card"],
            ).pack(expand=True, pady=30)
            self.todos_inner.update_idletasks()
            self.todos_log_canvas.configure(scrollregion=self.todos_log_canvas.bbox("all"))
            return

        # 未完成在前，已完成在后
        undone = [(i, t) for i, t in enumerate(self.todos) if not t.get("done")]
        done = [(i, t) for i, t in enumerate(self.todos) if t.get("done")]

        for idx, td in undone + done:
            item = tk.Frame(self.todos_inner, bg=_C["item_bg"])
            item.pack(fill=tk.X, padx=6, pady=2)

            # 圆圈
            circ = tk.Canvas(item, width=22, height=22,
                             bg=_C["item_bg"], highlightthickness=0, cursor="hand2")
            circ.pack(side=tk.LEFT, padx=(8, 4), pady=6)
            if td.get("done"):
                circ.create_oval(3, 3, 19, 19, fill=_C["accent"], outline=_C["accent"])
                circ.create_text(11, 11, text="✓", font=(FTK, 10), fill="white")
            else:
                circ.create_oval(3, 3, 19, 19, fill="", outline=_C["border"], width=1.5)
            circ.bind("<Button-1>", lambda e, i=idx: self._toggle_todo_at(i))

            # 文字
            font_spec = (FTK, 11)
            text = td["text"]
            if td.get("done"):
                display = self._truncate(text, font_spec, max(item.winfo_width() - 80, 100))
                lbl = tk.Label(item, text=display, font=font_spec,
                               fg=_C["mute"], bg=_C["item_bg"], anchor="w")
                # 画删除线需要 Canvas，用 Label 的 overstrike 替代
                lbl.configure(font=(FTK, 11, "overstrike"))
            else:
                display = self._truncate(text, font_spec, max(item.winfo_width() - 80, 100))
                lbl = tk.Label(item, text=display, font=font_spec,
                               fg=_C["pri"], bg=_C["item_bg"], anchor="w")
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6)
            lbl.bind("<Button-1>", lambda e, i=idx: self._toggle_todo_at(i))

            # 完成时间
            if td.get("done") and td.get("done_time"):
                tk.Label(item, text=td["done_time"], font=(FTK, 9),
                         fg=_C["mute"], bg=_C["item_bg"]).pack(side=tk.LEFT, padx=(4, 0))

            # 删除按钮
            del_btn = tk.Label(item, text="×", font=(FTK, 14),
                               fg=_C["border"], bg=_C["item_bg"], cursor="hand2")
            del_btn.pack(side=tk.RIGHT, padx=(0, 4), pady=4)
            del_btn.bind("<Button-1>", lambda e, i=idx: self._delete_todo_at(i))
            del_btn.bind("<Enter>", lambda e: e.widget.config(fg=_C["accent"]))
            del_btn.bind("<Leave>", lambda e: e.widget.config(fg=_C["border"]))

        # 清除已完成按钮
        if done:
            clear_btn = _canvas_btn(self.todos_inner, "清除已完成",
                                    self._clear_done_todos, w=100, h=28)
            clear_btn.pack(pady=(8, 4))

        self.todos_inner.update_idletasks()
        self.todos_log_canvas.configure(scrollregion=self.todos_log_canvas.bbox("all"))

    def _add_todo(self):
        text = self._td_search.get().strip()
        if not text:
            return
        self.todos.append({"text": text, "done": False, "done_time": ""})
        self._td_search.delete(0, tk.END)
        self._save_todos()
        self._refresh_todos()

    def _toggle_todo_at(self, idx):
        td = self.todos[idx]
        if td.get("done"):
            td["done"] = False
            td["done_time"] = ""
        else:
            td["done"] = True
            td["done_time"] = datetime.now().strftime("%H:%M")
        self._save_todos()
        self._refresh_todos()

    def _delete_todo_at(self, idx):
        self.todos.pop(idx)
        self._save_todos()
        self._refresh_todos()

    def _clear_done_todos(self):
        self.todos = [t for t in self.todos if not t.get("done")]
        self._save_todos()
        self._refresh_todos()

    def _on_todos_resize(self, event):
        c = self.todos_canvas
        w, h = event.width, event.height
        if w < 60 or h < 60:
            return
        c.delete("td_bg")
        _round_rect(c, 4, 4, w - 2, h - 2, r=14, fill=_C["shadow"], outline="", tags="td_bg")
        _round_rect(c, 2, 2, w - 4, h - 4, r=14, fill=_C["card"], outline=_C["border"], width=1, tags="td_bg")
        c.create_text(16, 22, text="待办", font=(FTK, 15, "bold"),
                      fill=_C["pri"], anchor="w", tags="td_bg")
        c.create_window(w - 16, 22, window=self._td_plus_btn, anchor="e", tags="td_bg")
        c.create_window(w - 56, 22, window=self._td_search_cv, anchor="e", tags="td_bg")
        c.create_line(12, 42, w - 12, 42, fill=_C["border"], width=1, tags="td_bg")
        c.create_window(10, 48, window=self._todos_outer, anchor="nw",
                        width=w - 20, height=h - 52, tags="td_bg")

    # ── 统计页 ─────────────────────────────────────────

    def _build_stats_page(self):
        page = tk.Frame(self._content, bg=_C["bg"])
        self._pages["stats"] = page

        canvas = tk.Canvas(page, bg=_C["bg"], highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        outer = tk.Frame(canvas, bg=_C["card"], padx=16, pady=12)
        canvas.create_window(0, 0, window=outer, anchor="nw")

        def _on_stats_resize(e):
            w, h = e.width, e.height
            canvas.delete("st_bg")
            _round_rect(canvas, 4, 4, w - 2, h - 2, r=14, fill=_C["shadow"], outline="", tags="st_bg")
            _round_rect(canvas, 2, 2, w - 4, h - 4, r=14, fill=_C["card"], outline=_C["border"], width=1, tags="st_bg")
            canvas.coords(canvas.find_withtag("st_list"), 8, 8)
            canvas.itemconfig(canvas.find_withtag("st_list"), width=w - 16)
        canvas.bind("<Configure>", _on_stats_resize)
        canvas.create_window(0, 0, window=outer, anchor="nw", tags="st_list")

        # 滚动
        outer.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=lambda *a: None)
        sb = tk.Scrollbar(page, command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        self._stats_outer = outer
        self._stats_canvas = canvas

    def _refresh_stats_page(self):
        for w in self._stats_outer.winfo_children():
            w.destroy()

        stats = self.stats

        total_count = sum(v["count"] for v in stats.values())
        total_minutes = sum(v["minutes"] for v in stats.values())
        total_days = len(stats)

        # 标题行 + 导出
        header = tk.Frame(self._stats_outer, bg=_C["card"])
        header.pack(fill=tk.X, pady=(0, 10))
        tk.Label(header, text="总体统计", font=(FTK, 14, "bold"),
                 fg=_C["pri"], bg=_C["card"]).pack(side=tk.LEFT)
        export_lbl = tk.Label(header, text="导出CSV", font=(FTK, 10),
                              fg=_C["mute"], bg=_C["card"], cursor="hand2")
        export_lbl.pack(side=tk.RIGHT)
        export_lbl.bind("<Button-1>", lambda e: self._export_csv())
        export_lbl.bind("<Enter>", lambda e: export_lbl.config(fg=_C["pri"]))
        export_lbl.bind("<Leave>", lambda e: export_lbl.config(fg=_C["mute"]))

        # 累计
        summary = tk.Frame(self._stats_outer, bg=_C["item_bg"], padx=10, pady=8)
        summary.pack(fill=tk.X, pady=(0, 10))
        tk.Label(summary, text=f"累计专注  {total_count} 次  /  {total_minutes} 分钟  /  {total_days} 天",
                 font=(FTK, 11), fg=_C["pri"], bg=_C["item_bg"]).pack()

        # 本周/本月
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        week_c, week_m, month_c, month_m = 0, 0, 0, 0
        for ds, v in stats.items():
            try:
                d = datetime.strptime(ds, "%Y-%m-%d").date()
                if week_start <= d <= today:
                    week_c += v["count"]; week_m += v["minutes"]
                if month_start <= d <= today:
                    month_c += v["count"]; month_m += v["minutes"]
            except ValueError:
                pass

        period = tk.Frame(self._stats_outer, bg=_C["item_bg"], padx=10, pady=6)
        period.pack(fill=tk.X, pady=(0, 10))
        tk.Label(period, text=f"本周  {week_c} 个  /  {week_m} 分钟",
                 font=(FTK, 11), fg=_C["sec"], bg=_C["item_bg"]).pack(anchor="w")
        tk.Label(period, text=f"本月  {month_c} 个  /  {month_m} 分钟",
                 font=(FTK, 11), fg=_C["sec"], bg=_C["item_bg"]).pack(anchor="w")

        # 每日记录
        tk.Label(self._stats_outer, text="每日记录", font=(FTK, 13, "bold"),
                 fg=_C["pri"], bg=_C["card"]).pack(anchor="w", pady=(0, 6))

        sorted_dates = sorted(stats.keys(), reverse=True)
        for date in sorted_dates:
            s = stats[date]
            row = tk.Frame(self._stats_outer, bg=_C["card"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=date, font=(FTK, 10), fg=_C["sec"], width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{s['count']} 次", font=(FTK, 10, "bold"), fg=_C["pri"], width=6, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{s['minutes']} 分钟", font=(FTK, 10), fg=_C["pri"], anchor="w").pack(side=tk.LEFT)
            topics = s.get("topics", [])
            if topics:
                topic_text = "、".join(topics)
                if len(topic_text) > 30:
                    topic_text = topic_text[:30] + "…"
                tk.Label(self._stats_outer, text=f"  {topic_text}", font=(FTK, 9),
                         fg=_C["mute"], bg=_C["card"], anchor="w").pack(fill=tk.X, padx=(12, 0))

        if not sorted_dates:
            tk.Label(self._stats_outer, text="暂无记录", font=(FTK, 11),
                     fg=_C["mute"], bg=_C["card"]).pack(pady=20)

        self._stats_outer.update_idletasks()
        self._stats_canvas.configure(scrollregion=self._stats_canvas.bbox("all"))

    def _export_csv(self):
        import csv
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile=f"FlowTick_{datetime.now().strftime('%Y%m%d')}.csv",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["日期", "专注次数", "专注分钟", "专注事项"])
                for date in sorted(self.stats.keys()):
                    s = self.stats[date]
                    topics = "、".join(s.get("topics", []))
                    writer.writerow([date, s["count"], s["minutes"], topics])
            tk.messagebox.showinfo("导出成功", f"已导出到 {path}")
        except Exception as e:
            tk.messagebox.showerror("导出失败", str(e))

    # ── 设置页 ─────────────────────────────────────────

    def _build_settings_page(self):
        page = tk.Frame(self._content, bg=_C["bg"])
        self._pages["settings"] = page

        canvas = tk.Canvas(page, bg=_C["bg"], highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        outer = tk.Frame(canvas, bg=_C["card"], padx=20, pady=14)
        canvas.create_window(0, 0, window=outer, anchor="nw")

        sb = tk.Scrollbar(page, command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_fn = lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
        canvas.bind("<MouseWheel>", scroll_fn)
        outer.bind("<MouseWheel>", scroll_fn)
        outer.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _on_settings_resize(e):
            w = e.width
            canvas.itemconfig("sg_list", width=w - 16)
        canvas.bind("<Configure>", _on_settings_resize)
        canvas.create_window(8, 8, window=outer, anchor="nw", tags="sg_list")

        self._settings_outer = outer
        self._settings_canvas = canvas

    def _refresh_settings_page(self):
        for w in self._settings_outer.winfo_children():
            w.destroy()

        card = self._settings_outer

        tk.Label(card, text="设置", font=(FTK, 14, "bold"),
                 fg=_C["pri"], bg=_C["card"]).pack(anchor="w", pady=(0, 12))

        def add_toggle(key, label):
            var = tk.BooleanVar(value=self.settings.get(key, False))
            cb = tk.Checkbutton(card, text=label, variable=var,
                                font=(FTK, 11), fg=_C["pri"], bg=_C["card"],
                                selectcolor=_C["bg"], activebackground=_C["card"],
                                anchor="w",
                                command=lambda: self._on_setting_changed(key, var))
            cb.pack(fill=tk.X, pady=3)

        def add_spin(key, label, from_, to_):
            row = tk.Frame(card, bg=_C["card"])
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label, font=(FTK, 11),
                     fg=_C["pri"], bg=_C["card"]).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(self.settings.get(key, from_)))
            spin = tk.Spinbox(row, from_=from_, to=to_, width=5,
                              font=(FTK, 11), textvariable=var,
                              command=lambda: self._on_spin_changed(key, var))
            spin.bind("<Return>", lambda e: self._on_spin_changed(key, var))
            spin.bind("<FocusOut>", lambda e: self._on_spin_changed(key, var))
            spin.pack(side=tk.RIGHT)

        add_toggle("sound_enabled", "声音提醒")
        add_toggle("auto_start_focus", "休息结束后自动开始专注")
        add_toggle("always_on_top", "窗口置顶")
        add_toggle("minimize_to_tray", "关闭时最小化到托盘")

        sep = tk.Frame(card, bg=_C["border"], height=1)
        sep.pack(fill=tk.X, pady=8)

        add_spin("long_break_min", "长休息（分钟）", 5, 60)
        add_spin("long_break_interval", "长休息间隔（个番茄）", 2, 10)
        add_spin("daily_goal", "每日目标（个番茄）", 1, 20)

        sep2 = tk.Frame(card, bg=_C["border"], height=1)
        sep2.pack(fill=tk.X, pady=8)

        add_toggle("idle_detection", "闲置检测（无操作自动暂停）")
        add_spin("idle_timeout_min", "闲置超时（分钟）", 1, 30)

        tk.Label(card, text="FlowTick V1.0", font=(FTK, 9),
                 fg=_C["mute"], bg=_C["card"]).pack(pady=(20, 0))

        self._settings_outer.update_idletasks()
        self._settings_canvas.configure(scrollregion=self._settings_canvas.bbox("all"))
        # 绑定滚轮到所有子控件
        scroll_fn = lambda e: self._settings_canvas.yview_scroll(int(-e.delta / 120), "units")
        def _bind_scroll(w):
            w.bind("<MouseWheel>", scroll_fn)
            for child in w.winfo_children():
                _bind_scroll(child)
        _bind_scroll(self._settings_outer)

    def _on_setting_changed(self, key, var):
        self.settings[key] = var.get()
        self._save_settings()
        self._apply_settings()

    def _on_spin_changed(self, key, var):
        try:
            self.settings[key] = int(var.get())
            self._save_settings()
            self._apply_settings()
        except ValueError:
            pass

    def _truncate(self, text, font_spec, max_width):
        """截断文本到指定像素宽度，末尾加省略号"""
        f = tkfont.Font(font=font_spec)
        if f.measure(text) <= max_width:
            return text
        while len(text) > 1 and f.measure(text + "…") > max_width:
            text = text[:-1]
        return text + "…"

    def _add_note(self):
        dlg = NoteDialog(self.root, "添加笔记")
        if dlg.result:
            title, content = dlg.result
            now = datetime.now().strftime("%m-%d %H:%M")
            self.notes.append({"title": title, "content": content, "time": now})
            self._save_notes()
            self._refresh_notes()
            self.notes_log_canvas.yview_moveto(1.0)

    def _edit_note_at(self, idx):
        note = self.notes[idx]
        dlg = NoteDialog(self.root, "编辑笔记", title=note["title"], content=note["content"])
        if dlg.result:
            title, content = dlg.result
            self.notes[idx] = {"title": title, "content": content}
            self._save_notes()
            self._refresh_notes()

    def _delete_note_at(self, idx):
        self.notes.pop(idx)
        self._save_notes()
        self._refresh_notes()

    def _show_note_ctx(self, event, idx):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="删除", command=lambda: self._delete_note_at(idx))
        menu.post(event.x_root, event.y_root)

    # ── 系统托盘 ──────────────────────────────────────────

    def _make_tray_icon(self):
        """生成一个简单的时钟托盘图标"""
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, 62, 62], fill="#4A90D9", outline="#2C5F8A", width=2)
        draw.line([(32, 32), (32, 16)], fill="white", width=3)
        draw.line([(32, 32), (46, 38)], fill="white", width=2)
        draw.ellipse([29, 29, 35, 35], fill="white")
        return img

    def _init_tray(self):
        """初始化并显示系统托盘图标"""
        import pystray
        icon_image = self._make_tray_icon()
        menu = pystray.Menu(
            pystray.MenuItem("显示", self._show_from_tray, default=True),
            pystray.MenuItem("退出", self._quit_from_tray),
        )
        self._tray_icon = pystray.Icon("FlowTick", icon_image, "FlowTick", menu)
        self._tray_running = True
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _hide_to_tray(self):
        self.root.withdraw()

    def _show_from_tray(self, icon=None, item=None):
        self.root.after(0, self._restore_window)

    def _restore_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit_from_tray(self, icon=None, item=None):
        self._tray_running = False
        self._tray_icon.stop()
        self.root.after(0, self.root.destroy)

    # ── Timer ──────────────────────────────────────────

    def _init_timer(self):
        focus_sec = self.focus_min * 60
        break_sec = self.break_min * 60
        self.timer = Timer(
            self.root, focus_sec, break_sec,
            on_tick=self._on_tick,
            on_mode_change=self._on_mode_change,
        )
        self._update_timer_display(focus_sec)

    def _on_tick(self, remaining):
        self._update_timer_display(remaining)
        self._update_tray_title(remaining)

    def _update_tray_title(self, remaining):
        if not self._tray_running:
            return
        m, s = divmod(max(remaining, 0), 60)
        mode = "专注" if self.timer.mode == Timer.FOCUS else "休息"
        self._tray_icon.title = f"FlowTick - {mode} {m:02d}:{s:02d}"

    def _on_mode_change(self, mode):
        if mode == Timer.BREAK:
            self._record_focus()
            self.pomodoro_count += 1
            self.topic_label.config(text="准备就绪")
            self.focus_topic = ""

            # 长休息判断
            interval = self.settings.get("long_break_interval", 4)
            if self.pomodoro_count % interval == 0:
                long_min = self.settings.get("long_break_min", DEFAULT_LONG_BREAK_MIN)
                self.timer.break_sec = long_min * 60
                self.timer.remaining = self.timer.break_sec
                msg = f"长休息 {long_min} 分钟"
            else:
                self.timer.break_sec = self.break_min * 60
                self.timer.remaining = self.timer.break_sec
                msg = f"休息 {self.break_min} 分钟"

            if self.settings.get("sound_enabled", True):
                threading.Thread(target=lambda: winsound.Beep(880, 500), daemon=True).start()
            BreakOverlay(self.root, msg)
            threading.Thread(target=lambda: _win_notify("FlowTick", f"专注结束，{msg}"), daemon=True).start()

            # 刷新事件列表
            self._refresh_events()
        elif mode == Timer.FOCUS:
            if self.settings.get("sound_enabled", True):
                threading.Thread(target=lambda: winsound.Beep(1200, 300), daemon=True).start()
            threading.Thread(target=lambda: _win_notify("FlowTick", "休息结束，准备专注"), daemon=True).start()
            if self.settings.get("auto_start_focus", False):
                self.timer.start()
                self._redraw_btn(self.toggle_btn, "⏸")

        self._update_goal_display()

    def _update_goal_display(self):
        goal = self.settings.get("daily_goal", 8)
        text = "专注" if self.timer.mode == Timer.FOCUS else "休息"
        if goal > 0:
            self.mode_label.config(text=f"{text} {self.pomodoro_count}/{goal}")
        else:
            self.mode_label.config(text=text)

    def _update_timer_display(self, seconds):
        m, s = divmod(seconds, 60)
        self.timer_label.config(text=f"{m:02d}:{s:02d}")

    # ── 按钮事件 ───────────────────────────────────────

    def _on_toggle(self):
        if self.timer.state in (Timer.IDLE, Timer.PAUSED):
            self.timer.start() if self.timer.state == Timer.IDLE else self.timer.resume()
            self._redraw_btn(self.toggle_btn, "⏸")
            self._start_idle_check()
        elif self.timer.state == Timer.RUNNING:
            self.timer.pause()
            self._redraw_btn(self.toggle_btn, "▶")

    def _redraw_btn(self, btn, text):
        w, h = int(btn.cget("width")), int(btn.cget("height"))
        btn.delete("all")
        btn._rect = _round_rect(btn, 2, 2, w - 2, h - 2, r=10,
                                fill=_C["card"], outline=_C["border"])
        btn.create_text(w // 2, h // 2, text=text, font=(FTK, 14), fill=_C["pri"])
        btn._text = text

    def _on_reset(self):
        self.timer.reset()
        self._update_timer_display(self.timer.focus_sec)
        self.pomodoro_count = 0
        self.topic_label.config(text="准备就绪")
        self.focus_topic = ""
        if self._tray_running:
            self._tray_icon.title = "FlowTick"
        self._redraw_btn(self.toggle_btn, "▶")
        self._update_goal_display()

    def _on_set_time(self):
        dlg = TimeDialog(self.root, self.focus_min, self.break_min)
        if dlg.result:
            self.focus_min, self.break_min, self.focus_topic = dlg.result
            self.timer.set_durations(self.focus_min * 60, self.break_min * 60)
            if self.focus_topic:
                self.topic_label.config(text=self.focus_topic)

    # ── 上半区 ─────────────────────────────────────────

    def _on_top_resize(self, event):
        c = self.top_canvas
        w, h = event.width, event.height
        if w < 100 or h < 80:
            return
        c.delete("top_bg")
        _round_rect(c, 4, 4, w - 2, h - 2, r=14, fill=_C["shadow"], outline="", tags="top_bg")
        _round_rect(c, 2, 2, w - 4, h - 4, r=14, fill=_C["card"], outline=_C["border"], width=1, tags="top_bg")
        mid = w // 2
        cy = h // 2
        c.create_window(mid // 2, cy, window=self._left_frame, anchor="center",
                        width=mid - 4, tags="top_bg")
        c.create_window(mid + (w - mid) // 2, cy, window=self._right_frame, anchor="center",
                        width=w - mid - 4, tags="top_bg")
        c.create_line(mid, 18, mid, h - 18, fill=_C["border"], width=1, tags="top_bg")

    # ── 当前时间 ───────────────────────────────────────

    def _update_clock(self):
        now = datetime.now()
        self.clock_label.config(text=now.strftime("%H:%M:%S"))
        self._draw_analog_clock(now)
        self.root.after(1000, self._update_clock)

    def _draw_analog_clock(self, now):
        c = self.clock_canvas
        c.delete("all")
        s = self.clock_size
        cx, cy = s // 2, s // 2
        r = s // 2 - 8

        c.create_oval(cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2,
                      fill=_C["shadow"], outline="")
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill=_C["item_bg"], outline=_C["sec"], width=1.5)

        for i in range(1, 13):
            angle = math.radians(i * 30 - 90)
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            ix = cx + (r - 10) * cos_a; iy = cy + (r - 10) * sin_a
            ox = cx + (r - 3) * cos_a; oy = cy + (r - 3) * sin_a
            c.create_line(ix, iy, ox, oy, fill=_C["pri"], width=2.5, capstyle=tk.ROUND)
            tx = cx + (r - 22) * cos_a; ty = cy + (r - 22) * sin_a
            c.create_text(tx, ty, text=str(i), font=(FTK, 9, "bold"), fill=_C["pri"])

        for i in range(60):
            if i % 5 != 0:
                angle = math.radians(i * 6 - 90)
                cos_a, sin_a = math.cos(angle), math.sin(angle)
                ix = cx + (r - 5) * cos_a; iy = cy + (r - 5) * sin_a
                ox = cx + (r - 3) * cos_a; oy = cy + (r - 3) * sin_a
                c.create_line(ix, iy, ox, oy, fill=_C["sec"], width=1)

        h = now.hour % 12; m = now.minute; s_now = now.second

        def _hand_points(angle_deg, length, tail, width):
            a = math.radians(angle_deg - 90)
            perp = math.radians(angle_deg)
            cos_a, sin_a = math.cos(a), math.sin(a)
            cos_p, sin_p = math.cos(perp), math.sin(perp)
            hw = width / 2
            return [
                cx + length * cos_a, cy + length * sin_a,
                cx + hw * cos_p - tail * 0.3 * cos_a, cy + hw * sin_p - tail * 0.3 * sin_a,
                cx - tail * cos_a + hw * 0.5 * cos_p, cy - tail * sin_a + hw * 0.5 * sin_p,
                cx - tail * cos_a - hw * 0.5 * cos_p, cy - tail * sin_a - hw * 0.5 * sin_p,
                cx - hw * cos_p - tail * 0.3 * cos_a, cy - hw * sin_p - tail * 0.3 * sin_a,
            ]

        h_angle = (h + m / 60) * 30
        pts = _hand_points(h_angle, r - 38, 10, 7)
        c.create_polygon(pts, fill=_C["pri"], outline=_C["pri"], smooth=True)

        m_angle = (m + s_now / 60) * 6
        pts = _hand_points(m_angle, r - 22, 14, 4.5)
        c.create_polygon(pts, fill=_C["sec"], outline=_C["sec"], smooth=True)

        s_angle = s_now * 6
        sa = math.radians(s_angle - 90)
        cos_sa, sin_sa = math.cos(sa), math.sin(sa)
        tail_x = cx - 16 * cos_sa; tail_y = cy - 16 * sin_sa
        c.create_line(tail_x, tail_y, cx, cy, fill=_C["accent"], width=1)
        tip_x = cx + (r - 14) * cos_sa; tip_y = cy + (r - 14) * sin_sa
        c.create_line(cx, cy, tip_x, tip_y, fill=_C["accent"], width=1.5, capstyle=tk.ROUND)

        c.create_oval(cx - 5, cy - 5, cx + 5, cy + 5, fill=_C["sec"], outline=_C["sec"])
        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=_C["accent"], outline=_C["accent"])


# ── 对话框 ─────────────────────────────────────────────

class NoteDialog:
    def __init__(self, parent, title_text, title="", content=""):
        self.result = None

        self.dlg = tk.Toplevel(parent)
        self.dlg.withdraw()
        self.dlg.update()
        self.dlg.title(title_text)
        self.dlg.resizable(True, True)
        self.dlg.transient(parent)
        self.dlg.grab_set()
        self.dlg.configure(bg=_C["bg"])
        self.dlg.minsize(340, 280)

        card = tk.Frame(self.dlg, bg=_C["card"], padx=16, pady=14)
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(card, text=title_text, font=(FTK, 13, "bold"),
                 fg=_C["pri"], bg=_C["card"]).pack(anchor="w", pady=(0, 10))

        tk.Label(card, text="标题", font=(FTK, 10),
                 fg=_C["sec"], bg=_C["card"]).pack(anchor="w")
        self.title_entry = tk.Entry(card, font=(FTK, 11), bd=1, relief="solid",
                                    highlightthickness=1, highlightcolor=_C["accent"],
                                    highlightbackground=_C["border"])
        self.title_entry.pack(fill=tk.X, pady=(2, 8))
        self.title_entry.insert(0, title)

        tk.Label(card, text="内容", font=(FTK, 10),
                 fg=_C["sec"], bg=_C["card"]).pack(anchor="w")
        content_frame = tk.Frame(card, bg=_C["card"])
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        self.content_text = tk.Text(content_frame, font=(FTK, 11), height=4, bd=1,
                                    relief="solid", highlightthickness=1,
                                    highlightcolor=_C["accent"],
                                    highlightbackground=_C["border"], wrap=tk.WORD)
        sb = tk.Scrollbar(content_frame, command=self.content_text.yview)
        self.content_text.configure(yscrollcommand=sb.set)
        self.content_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.content_text.insert("1.0", content)

        btn_row = tk.Frame(card, bg=_C["card"])
        btn_row.pack(fill=tk.X, pady=(10, 0))
        _canvas_btn(btn_row, "确定", self._ok, w=70).pack(side=tk.LEFT, padx=(0, 6))
        _canvas_btn(btn_row, "取消", self.dlg.destroy, w=70).pack(side=tk.LEFT)

        w = max(440, self.dlg.winfo_reqwidth())
        h = max(340, self.dlg.winfo_reqheight())
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.dlg.geometry(f"{w}x{h}+{px}+{py}")
        self.dlg.deiconify()

        self.title_entry.focus_set()
        self.dlg.wait_window()

    def _ok(self):
        title = self.title_entry.get().strip()
        content = self.content_text.get("1.0", tk.END).strip()
        if title:
            self.result = (title, content)
            self.dlg.destroy()


class TimeDialog:
    def __init__(self, parent, focus_min, break_min):
        self.result = None

        self.dlg = tk.Toplevel(parent)
        self.dlg.withdraw()
        self.dlg.update()
        self.dlg.title("设置时间")
        self.dlg.resizable(True, True)
        self.dlg.transient(parent)
        self.dlg.grab_set()
        self.dlg.configure(bg=_C["bg"])
        self.dlg.minsize(300, 230)

        card = tk.Frame(self.dlg, bg=_C["card"], padx=16, pady=14)
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(card, text="设置时间", font=(FTK, 13, "bold"),
                 fg=_C["pri"], bg=_C["card"]).pack(anchor="w", pady=(0, 10))

        self._make_field(card, "专注（分钟）", str(focus_min))
        self._make_field(card, "休息（分钟）", str(break_min))
        self._make_field(card, "专注事项", "")

        btn_row = tk.Frame(card, bg=_C["card"])
        btn_row.pack(fill=tk.X, pady=(10, 0))
        _canvas_btn(btn_row, "确定", self._ok, w=70).pack(side=tk.LEFT, padx=(0, 6))
        _canvas_btn(btn_row, "取消", self.dlg.destroy, w=70).pack(side=tk.LEFT)

        w = max(380, self.dlg.winfo_reqwidth())
        h = max(320, self.dlg.winfo_reqheight())
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.dlg.geometry(f"{w}x{h}+{px}+{py}")
        self.dlg.deiconify()

        self.focus_entry.focus_set()
        self.dlg.wait_window()

    def _make_field(self, parent, label, default):
        tk.Label(parent, text=label, font=(FTK, 10),
                 fg=_C["sec"], bg=_C["card"]).pack(anchor="w")
        entry = tk.Entry(parent, font=(FTK, 11), bd=1, relief="solid",
                         highlightthickness=1, highlightcolor=_C["accent"],
                         highlightbackground=_C["border"])
        entry.pack(fill=tk.X, pady=(2, 8))
        if default:
            entry.insert(0, default)
        if label.startswith("专注（"):
            self.focus_entry = entry
        elif label.startswith("休息（"):
            self.break_entry = entry
        else:
            self.topic_entry = entry

    def _ok(self):
        try:
            f = int(self.focus_entry.get())
            b = int(self.break_entry.get())
            if f > 0 and b > 0:
                topic = self.topic_entry.get().strip()
                self.result = (f, b, topic)
                self.dlg.destroy()
        except ValueError:
            pass


class SettingsDialog:
    """应用设置面板"""

    def __init__(self, parent, settings):
        self.result = None
        self._settings = dict(settings)

        self.dlg = tk.Toplevel(parent)
        self.dlg.withdraw()
        self.dlg.update()
        self.dlg.title("设置")
        self.dlg.resizable(False, False)
        self.dlg.transient(parent)
        self.dlg.grab_set()
        self.dlg.configure(bg=_C["bg"])

        card = tk.Frame(self.dlg, bg=_C["card"], padx=20, pady=14)
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(card, text="设置", font=(FTK, 14, "bold"),
                 fg=_C["pri"], bg=_C["card"]).pack(anchor="w", pady=(0, 12))

        self._checks = {}
        self._spins = {}

        def add_toggle(key, label):
            var = tk.BooleanVar(value=self._settings.get(key, False))
            cb = tk.Checkbutton(card, text=label, variable=var,
                                font=(FTK, 11), fg=_C["pri"], bg=_C["card"],
                                selectcolor=_C["bg"], activebackground=_C["card"],
                                anchor="w")
            cb.pack(fill=tk.X, pady=3)
            self._checks[key] = var

        def add_spin(key, label, from_, to_):
            row = tk.Frame(card, bg=_C["card"])
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label, font=(FTK, 11),
                     fg=_C["pri"], bg=_C["card"]).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(self._settings.get(key, from_)))
            spin = tk.Spinbox(row, from_=from_, to=to_, width=5,
                              font=(FTK, 11), textvariable=var)
            spin.pack(side=tk.RIGHT)
            self._spins[key] = var

        add_toggle("sound_enabled", "声音提醒")
        add_toggle("auto_start_focus", "休息结束后自动开始专注")
        add_toggle("always_on_top", "窗口置顶")
        add_toggle("minimize_to_tray", "关闭时最小化到托盘")

        sep = tk.Frame(card, bg=_C["border"], height=1)
        sep.pack(fill=tk.X, pady=8)

        add_spin("long_break_min", "长休息（分钟）", 5, 60)
        add_spin("long_break_interval", "长休息间隔（个番茄）", 2, 10)
        add_spin("daily_goal", "每日目标（个番茄）", 1, 20)

        sep2 = tk.Frame(card, bg=_C["border"], height=1)
        sep2.pack(fill=tk.X, pady=8)

        add_toggle("idle_detection", "闲置检测（无操作自动暂停）")
        add_spin("idle_timeout_min", "闲置超时（分钟）", 1, 30)

        btn_row = tk.Frame(card, bg=_C["card"])
        btn_row.pack(fill=tk.X, pady=(16, 0))
        _canvas_btn(btn_row, "确定", self._ok, w=70).pack(side=tk.LEFT, padx=(0, 6))
        _canvas_btn(btn_row, "取消", self.dlg.destroy, w=70).pack(side=tk.LEFT)

        tk.Label(card, text="FlowTick V1.0", font=(FTK, 9),
                 fg=_C["mute"], bg=_C["card"]).pack(pady=(12, 0))

        self.dlg.update_idletasks()
        w, h = 300, self.dlg.winfo_reqheight()
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.dlg.geometry(f"{w}x{h}+{px}+{py}")
        self.dlg.deiconify()

        self.dlg.wait_window()

    def _ok(self):
        for key, var in self._checks.items():
            self._settings[key] = var.get()
        for key, var in self._spins.items():
            try:
                self._settings[key] = int(var.get())
            except ValueError:
                pass
        self.result = self._settings
        self.dlg.destroy()


class StatsDialog:
    """专注统计面板"""

    def __init__(self, parent, stats):
        self._stats = stats
        self.dlg = tk.Toplevel(parent)
        self.dlg.title("专注统计")
        self.dlg.resizable(False, False)
        self.dlg.transient(parent)
        self.dlg.grab_set()

        x, y = parent.winfo_pointerxy()
        self.dlg.geometry(f"360x420+{x - 180}+{y - 210}")

        frame = tk.Frame(self.dlg, padx=15, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        total_count = sum(v["count"] for v in stats.values())
        total_minutes = sum(v["minutes"] for v in stats.values())
        total_days = len(stats)

        header_row = tk.Frame(frame, bg=_C["bg"])
        header_row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(header_row, text="总体统计", font=(FTK, 14, "bold"), fg=_C["pri"]).pack(side=tk.LEFT)
        _canvas_btn(header_row, "导出 CSV", self._export_csv, w=82, h=30).pack(side=tk.RIGHT)

        summary = tk.Frame(frame, bg=_C["item_bg"], padx=10, pady=8)
        summary.pack(fill=tk.X, pady=(0, 12))
        tk.Label(summary, text=f"累计专注  {total_count} 次  /  {total_minutes} 分钟  /  {total_days} 天",
                 font=(FTK, 11), fg=_C["pri"], bg=_C["item_bg"]).pack()

        # 本周 / 本月汇总
        week_c, week_m = self._calc_period(stats, "week")
        month_c, month_m = self._calc_period(stats, "month")

        period_frame = tk.Frame(frame, bg=_C["item_bg"], padx=10, pady=6)
        period_frame.pack(fill=tk.X, pady=(0, 12))
        tk.Label(period_frame, text=f"本周  {week_c} 个  /  {week_m} 分钟",
                 font=(FTK, 11), fg=_C["sec"], bg=_C["item_bg"]).pack(anchor="w")
        tk.Label(period_frame, text=f"本月  {month_c} 个  /  {month_m} 分钟",
                 font=(FTK, 11), fg=_C["sec"], bg=_C["item_bg"]).pack(anchor="w")

        tk.Label(frame, text="每日记录", font=(FTK, 13, "bold"), fg=_C["pri"]).pack(anchor="w", pady=(0, 6))

        list_canvas = tk.Canvas(frame, highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, command=list_canvas.yview)
        list_inner = tk.Frame(list_canvas)

        list_canvas.pack(fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        list_canvas.configure(yscrollcommand=scrollbar.set)
        list_canvas.create_window((0, 0), window=list_inner, anchor="nw")
        list_inner.bind("<Configure>",
                        lambda e: list_canvas.configure(scrollregion=list_canvas.bbox("all")))

        sorted_dates = sorted(stats.keys(), reverse=True)
        for date in sorted_dates:
            s = stats[date]
            row = tk.Frame(list_inner)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=date, font=(FTK, 10), fg=_C["sec"], width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{s['count']} 次", font=(FTK, 10, "bold"), fg=_C["pri"], width=6, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{s['minutes']} 分钟", font=(FTK, 10), fg=_C["pri"], anchor="w").pack(side=tk.LEFT)
            topics = s.get("topics", [])
            if topics:
                topic_text = "、".join(topics)
                if len(topic_text) > 30:
                    topic_text = topic_text[:30] + "…"
                tk.Label(list_inner, text=f"  {topic_text}", font=(FTK, 9),
                         fg=_C["mute"], anchor="w").pack(fill=tk.X, padx=(12, 0))

        if not sorted_dates:
            tk.Label(list_inner, text="暂无记录", font=(FTK, 11), fg=_C["mute"]).pack(pady=20)

        tk.Button(frame, text="关闭", font=(FTK, 10), width=8, command=self.dlg.destroy).pack(pady=(10, 0))
        self.dlg.wait_window()

    def _calc_period(self, stats, period):
        """计算本周或本月的专注次数和分钟数"""
        from datetime import timedelta
        today = datetime.now().date()
        if period == "week":
            # 本周一到今天
            start = today - timedelta(days=today.weekday())
        else:
            # 本月 1 号到今天
            start = today.replace(day=1)

        count, minutes = 0, 0
        for date_str, v in stats.items():
            try:
                d = datetime.strptime(date_str, "%Y-%m-%d").date()
                if start <= d <= today:
                    count += v.get("count", 0)
                    minutes += v.get("minutes", 0)
            except ValueError:
                pass
        return count, minutes

    def _export_csv(self):
        import csv
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile=f"FlowTick_{datetime.now().strftime('%Y%m%d')}.csv",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["日期", "专注次数", "专注分钟", "专注事项"])
                for date in sorted(self._stats.keys()):
                    s = self._stats[date]
                    topics = "、".join(s.get("topics", []))
                    writer.writerow([date, s["count"], s["minutes"], topics])
            tk.messagebox.showinfo("导出成功", f"已导出到 {path}", parent=self.dlg)
        except Exception as e:
            tk.messagebox.showerror("导出失败", str(e), parent=self.dlg)


class BreakOverlay:
    """休息提醒遮罩"""

    def __init__(self, parent, message):
        self.win = tk.Toplevel(parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=_C["bg"])

        sw = parent.winfo_screenwidth()
        sh = parent.winfo_screenheight()
        w, h = 360, 200
        self.win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        card = tk.Frame(self.win, bg=_C["card"], padx=30, pady=25)
        card.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        tk.Label(card, text="休息时间", font=(FTK, 22, "bold"),
                 fg=_C["accent"], bg=_C["card"]).pack(pady=(0, 8))
        tk.Label(card, text=message, font=(FTK, 14),
                 fg=_C["sec"], bg=_C["card"]).pack(pady=(0, 16))

        _canvas_btn(card, "知道了", self.win.destroy, w=90, h=36).pack()

        self.win.bind("<Return>", lambda e: self.win.destroy())
        self.win.focus_set()
