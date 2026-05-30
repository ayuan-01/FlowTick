import tkinter as tk
import tkinter.font as tkfont
import json
import os
import sys
import shutil
import math
import threading
import time
import winsound
from datetime import datetime, timedelta
from timer import Timer
from config import (
    WINDOW_WIDTH, WINDOW_HEIGHT, SIDEBAR_WIDTH, DEFAULT_SETTINGS,
)
from widgets import (
    FTK, _C, _round_rect, _canvas_btn, _bind_tooltip, _win_notify,
    _round_entry, _sb_btn, _confirm_dialog,
)
from dialogs import NoteDialog, SessionDialog, BreakOverlay, FolderDialog


class FlowTickApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FlowTick")
        sx = (self.root.winfo_screenwidth() - WINDOW_WIDTH) // 2
        sy = (self.root.winfo_screenheight() - WINDOW_HEIGHT) // 2
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{sx}+{sy}")

        # Logo（白底用于任务栏，透明用于托盘）
        _script_dir = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        self._logo_path = os.path.join(_script_dir, "fig", "LOGO.png")
        self._tray_logo_path = os.path.join(_script_dir, "fig", "LOGO_icon.png")
        if os.path.exists(self._logo_path):
            try:
                _logo = tk.PhotoImage(file=self._logo_path)
                self.root.iconphoto(True, _logo)
            except Exception:
                pass

        # 路径
        if getattr(sys, 'frozen', False):
            base_dir = os.path.join(os.environ['APPDATA'], 'FlowTick')
            os.makedirs(base_dir, exist_ok=True)
            # 迁移旧位置数据
            old_dir = os.path.dirname(sys.executable)
            for fname in ["notes.json", "events.json", "stats.json", "settings.json", "todos.json", "folders.json"]:
                old_path = os.path.join(old_dir, fname)
                new_path = os.path.join(base_dir, fname)
                if os.path.exists(old_path) and not os.path.exists(new_path):
                    shutil.move(old_path, new_path)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self.notes_file = os.path.join(base_dir, "notes.json")
        self.events_file = os.path.join(base_dir, "events.json")
        self.stats_file = os.path.join(base_dir, "stats.json")
        self.settings_file = os.path.join(base_dir, "settings.json")
        self.todos_file = os.path.join(base_dir, "todos.json")
        self.folders_file = os.path.join(base_dir, "folders.json")
        self.session_file = os.path.join(base_dir, "session.json")

        # 加载数据
        self.settings = self._load_settings()
        self.notes = self._load_notes()
        self.folders = self._load_json(self.folders_file)
        self._current_folder = None  # None=全部
        self._drag_note_idx = None
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
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
            ("<s>", lambda e: self._on_skip()),
            ("<Escape>", lambda e: self._on_terminate()),
            ("<t>", lambda e: self._add_todo()),
            ("<Key-1>", lambda e: self._switch_page("home")),
            ("<Key-2>", lambda e: self._switch_page("events")),
            ("<Key-3>", lambda e: self._switch_page("notes")),
            ("<Key-4>", lambda e: self._switch_page("todos")),
            ("<Key-5>", lambda e: self._switch_page("stats")),
        ]
        self._bind_shortcuts()
        self.root.bind("<Button-1>", self._root_click)

    @staticmethod
    def _is_click_on_focusable(widget):
        w = widget
        while w is not None and not isinstance(w, str):
            try:
                if w.winfo_toplevel() == w:
                    return True
                if str(w.cget("takefocus")) == "1":
                    return True
            except tk.TclError:
                pass
            w = w.master
        return False

    def _root_click(self, e):
        if not self._is_click_on_focusable(e.widget):
            self.root.focus_set()

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

        self.status_label = tk.Label(
            right, text="", font=(FTK, 9),
            bg=_C["card"], fg=_C["sec"],
        )
        self.status_label.pack(pady=(0, 0))

        self.timer_box = tk.Canvas(
            right, width=200, height=100,
            bg=_C["card"], highlightthickness=0,
        )
        self.timer_box.pack(pady=(20, 0))
        # 中心填充（card 色遮罩，避免弧与文字重叠）
        self.timer_box.create_oval(58, 8, 142, 92, fill=_C["card"], outline="")
        # 背景弧
        self._arc_bg = self.timer_box.create_arc(
            55, 5, 145, 95, start=90, extent=-270,
            style="arc", width=4, outline=_C["border"],
        )
        # 进度弧
        self._arc_progress = self.timer_box.create_arc(
            55, 5, 145, 95, start=90, extent=0,
            style="arc", width=4, outline=_C["accent"],
        )
        # 计时文字
        self.timer_label = tk.Label(
            self.timer_box, text="25:00", font=("Consolas", 26, "bold"),
            bg=_C["card"], fg=_C["pri"],
        )
        self.timer_box.create_window(100, 50, window=self.timer_label)
        self._arc_total = 0

        self._btn_row = tk.Frame(right, bg=_C["card"])
        self._btn_row.pack(pady=(14, 14))

        self.time_btn = _canvas_btn(self._btn_row, "⏱", self._on_set_time)
        self.time_btn.pack(side=tk.LEFT, padx=8)
        _bind_tooltip(self.time_btn, "设置时长")
        self.toggle_btn = _canvas_btn(self._btn_row, "▶", self._on_toggle)
        self.toggle_btn.pack(side=tk.LEFT, padx=8)
        _bind_tooltip(self.toggle_btn, "开始/暂停 (Space)")
        self.skip_btn = _canvas_btn(self._btn_row, "⏭", self._on_skip)
        self.skip_btn.pack(side=tk.LEFT, padx=8)
        _bind_tooltip(self.skip_btn, "跳过当前段")
        self.stop_btn = _canvas_btn(self._btn_row, "■", self._on_terminate)
        self.stop_btn.pack(side=tk.LEFT, padx=8)
        _bind_tooltip(self.stop_btn, "终止会话")
        self.reset_btn = _canvas_btn(self._btn_row, "↺", self._on_reset)
        self.reset_btn.pack(side=tk.LEFT, padx=8)
        _bind_tooltip(self.reset_btn, "重置 (R)")

        # 今日目标进度
        self._goal_frame = tk.Frame(right, bg=_C["card"])
        self._goal_frame.pack(pady=(4, 8))
        self._goal_cv = tk.Canvas(self._goal_frame, height=20, bg=_C["card"], highlightthickness=0)
        self._goal_cv.pack()
        self._update_goal_indicator()

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

        # 左侧文件夹面板
        self._folder_panel = tk.Frame(page, bg=_C["sidebar"], width=100)
        self._folder_panel.pack(side=tk.LEFT, fill=tk.Y)
        self._folder_panel.pack_propagate(False)
        self._folder_panel_width = 100

        self._folder_inner = tk.Frame(self._folder_panel, bg=_C["sidebar"])
        self._folder_inner.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        # 底部新建按钮
        add_folder_btn = tk.Label(self._folder_panel, text="+ 新建文件夹",
                                  font=(FTK, 10), fg=_C["sb_text"], bg=_C["sidebar"],
                                  cursor="hand2", height=2)
        add_folder_btn.pack(side=tk.BOTTOM, fill=tk.X)
        add_folder_btn.bind("<Button-1>", lambda e: self._add_folder())
        add_folder_btn.bind("<Enter>", lambda e: add_folder_btn.config(fg=_C["sb_sel"]))
        add_folder_btn.bind("<Leave>", lambda e: add_folder_btn.config(fg=_C["sb_text"]))

        # 可拖动分隔线
        self._splitter = tk.Frame(page, bg=_C["border"], width=5, cursor="sb_h_double_arrow")
        self._splitter.pack(side=tk.LEFT, fill=tk.Y)
        self._splitter.pack_propagate(False)
        self._splitter.bind("<ButtonPress-1>", self._split_press)
        self._splitter.bind("<B1-Motion>", self._split_motion)
        self._splitter.bind("<ButtonRelease-1>", self._split_release)
        self._split_start_x = 0
        self._split_start_w = 100

        # 右侧笔记区
        right_frame = tk.Frame(page, bg=_C["bg"])
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.notes_canvas = tk.Canvas(right_frame, bg=_C["bg"], highlightthickness=0)
        self.notes_canvas.pack(fill=tk.BOTH, expand=True, padx=(0, 12), pady=12)

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
        self._nt_search_cv, self._nt_search = _round_entry(right_frame, "搜索笔记...", width=160, height=28)
        self._nt_search.bind("<FocusIn>", lambda e: self._on_entry_focus(self._nt_search, "搜索笔记..."))
        self._nt_search.bind("<FocusOut>", lambda e: self._on_entry_blur(self._nt_search, "搜索笔记..."))
        self._nt_search.bind("<KeyRelease>", lambda e: self._refresh_notes())
        self.notes_canvas.bind("<Configure>", self._on_notes_resize)

        self._refresh_folder_list()

    def _split_press(self, e):
        self._split_start_x = e.x_root
        self._split_start_w = self._folder_panel_width

    def _split_motion(self, e):
        delta = e.x_root - self._split_start_x
        new_w = max(60, min(300, self._split_start_w + delta))
        self._folder_panel_width = new_w
        self._folder_panel.config(width=new_w)
        self._truncate_all_folder_names()

    def _split_release(self, e):
        pass

    def _truncate_label(self, lbl, full_name, max_width):
        fnt = tkfont.Font(font=lbl.cget("font"))
        if fnt.measure(full_name) <= max_width:
            lbl.config(text=full_name)
            lbl._full_name = full_name
            lbl._truncated = False
            return
        text = full_name
        while len(text) > 1 and fnt.measure(text + "…") > max_width:
            text = text[:-1]
        lbl.config(text=text + "…")
        lbl._full_name = full_name
        lbl._truncated = True

    def _truncate_all_folder_names(self):
        max_w = self._folder_panel_width - 15
        for wrapper in self._folder_inner.winfo_children():
            lbl = getattr(wrapper, '_lbl', None)
            if lbl and hasattr(lbl, '_full_name'):
                self._truncate_label(lbl, lbl._full_name, max_w)

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

    def _save_session(self):
        """保存当前会话状态到 session.json"""
        t = self.timer
        if t.state in (Timer.RUNNING, Timer.PAUSED):
            data = {
                "state": t.state,
                "current_idx": t.current_idx,
                "segment_remaining": t.segment_remaining,
                "focus_accumulated": t.focus_accumulated,
                "focus_total": t.focus_total,
                "focus_topic": self.focus_topic,
                "timestamp": time.time(),
            }
            self._save_json(self.session_file, data)
        else:
            # IDLE 状态清除 session 文件
            try:
                if os.path.exists(self.session_file):
                    os.remove(self.session_file)
            except OSError:
                pass

    def _load_session(self):
        """启动时恢复会话状态"""
        if not os.path.exists(self.session_file):
            return False
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return False

        state = data.get("state", Timer.IDLE)
        if state == Timer.IDLE:
            return False

        current_idx = data.get("current_idx", 0)
        segment_remaining = data.get("segment_remaining", 0)
        focus_accumulated = data.get("focus_accumulated", 0)
        focus_total = data.get("focus_total", 0)
        self.focus_topic = data.get("focus_topic", "")
        timestamp = data.get("timestamp", time.time())

        # 重建 segments
        self._build_session()
        if not self.timer.segments or current_idx >= len(self.timer.segments):
            return False

        # 时间漂移修正
        if state == Timer.RUNNING:
            elapsed = int(time.time() - timestamp)
            segment_remaining -= elapsed
            # 快进跳过已过期的 segments
            while segment_remaining <= 0 and current_idx < len(self.timer.segments) - 1:
                seg_type, seg_min = self.timer.segments[current_idx]
                if seg_type == Timer.FOCUS:
                    focus_accumulated += seg_min
                current_idx += 1
                segment_remaining += self.timer.segments[current_idx][1] * 60

            if focus_accumulated >= focus_total or current_idx >= len(self.timer.segments):
                # 会话在关闭期间已完成
                if focus_accumulated > 0:
                    self._record_focus(focus_accumulated)
                self._refresh_events()
                try:
                    os.remove(self.session_file)
                except OSError:
                    pass
                return False

        self.timer.restore_state(state, current_idx, max(0, segment_remaining),
                                 focus_accumulated, focus_total)
        # 更新 UI
        seg_type, seg_min = self.timer.segments[current_idx]
        self.timer.on_segment_change(seg_type, seg_min, current_idx,
                                     len(self.timer.segments),
                                     focus_accumulated, focus_total)
        self._update_timer_display(max(0, segment_remaining))
        if self.focus_topic:
            self.topic_label.config(text=self.focus_topic)
        if state == Timer.RUNNING:
            self._redraw_btn(self.toggle_btn, "⏸")
            self.timer.state = Timer.RUNNING
            self.timer._tick()
        elif state == Timer.PAUSED:
            self._redraw_btn(self.toggle_btn, "▶")
        return True

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

    def _record_focus(self, minutes):
        """记录一次专注完成"""
        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.stats:
            self.stats[today] = {"count": 0, "minutes": 0, "topics": []}
        self.stats[today]["count"] += 1
        self.stats[today]["minutes"] += minutes
        if self.focus_topic:
            self.stats[today]["topics"].append(self.focus_topic)
        self._save_stats()

        # 自动记录到事件
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.events.append({
            "time": now,
            "topic": self.focus_topic or "未命名专注",
            "minutes": minutes,
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
            self._bind_scroll_recursive(self.events_log_canvas, self.events_inner)
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
            self._bind_scroll_recursive(self.events_log_canvas, self.events_inner)
            self.events_inner.update_idletasks()
            self.events_log_canvas.configure(scrollregion=self.events_log_canvas.bbox("all"))
            return

        # 最新的在前面
        shown = list(reversed(shown))

        today_str = datetime.now().strftime("%Y-%m-%d")
        yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        last_date = None

        for idx, ev in shown:
            ev_date = ev.get("time", "")[:10]

            # 日期分组头
            if ev_date != last_date:
                last_date = ev_date
                if ev_date == today_str:
                    date_label = "今天"
                elif ev_date == yesterday_str:
                    date_label = "昨天"
                else:
                    try:
                        d = datetime.strptime(ev_date, "%Y-%m-%d")
                        date_label = f"{d.month}月{d.day}日"
                    except ValueError:
                        date_label = ev_date

                header = tk.Frame(self.events_inner, bg=_C["bg"])
                header.pack(fill=tk.X, pady=(8, 2))
                tk.Label(header, text=date_label, font=(FTK, 10, "bold"),
                         fg=_C["sec"], bg=_C["bg"]).pack(anchor="w", padx=8)

            item = tk.Frame(self.events_inner, bg=_C["item_bg"])
            item.pack(fill=tk.X, padx=6, pady=1)

            # 时间（只显示时分）
            time_display = ev.get("time", "")
            if len(time_display) >= 16:
                time_display = time_display[11:]
            tk.Label(
                item, text=time_display, font=(FTK, 9),
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

        self._bind_scroll_recursive(self.events_log_canvas, self.events_inner)
        self.events_inner.update_idletasks()
        self.events_log_canvas.configure(scrollregion=self.events_log_canvas.bbox("all"))

    def _delete_event_at(self, idx):
        if not _confirm_dialog(self.root, "删除事件", "确定删除这条专注记录？"):
            return
        ev = self.events.pop(idx)
        self._save_events()
        date_str = ev["time"][:10]
        if date_str in self.stats:
            s = self.stats[date_str]
            s["count"] = max(0, s["count"] - 1)
            s["minutes"] = max(0, s["minutes"] - ev.get("minutes", 0))
            if ev.get("topic") and ev["topic"] in s.get("topics", []):
                s["topics"].remove(ev["topic"])
            if s["count"] == 0:
                del self.stats[date_str]
            self._save_stats()
        self._refresh_events()

    def _delete_event_from_stats(self, idx):
        if not _confirm_dialog(self.root, "删除事件", "确定删除这条专注记录？"):
            return
        ev = self.events.pop(idx)
        self._save_events()
        date_str = ev["time"][:10]
        if date_str in self.stats:
            s = self.stats[date_str]
            s["count"] = max(0, s["count"] - 1)
            s["minutes"] = max(0, s["minutes"] - ev.get("minutes", 0))
            if ev.get("topic") and ev["topic"] in s.get("topics", []):
                s["topics"].remove(ev["topic"])
            if s["count"] == 0:
                del self.stats[date_str]
            self._save_stats()
        self._refresh_stats_page()
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

        # 文件夹筛选
        folder = self._current_folder
        if folder is None:
            filtered = list(enumerate(self.notes))
        else:
            filtered = [(i, n) for i, n in enumerate(self.notes)
                        if n.get("folder_id", "") == folder]

        # 关键词筛选
        if kw:
            filtered = [(i, n) for i, n in filtered
                        if kw.lower() in n.get("title", "").lower()
                        or kw.lower() in n.get("content", "").lower()]

        if not filtered:
            empty_text = "暂无笔记，点击 + 添加" if not kw else "无匹配结果"
            if folder is not None and not kw:
                fname = self._get_folder_name(folder)
                empty_text = f"「{fname}」暂无笔记"
            tk.Label(
                self.notes_inner, text=empty_text,
                font=(FTK, 11), fg=_C["mute"], bg=_C["card"],
            ).pack(expand=True, pady=30)
            self._bind_scroll_recursive(self.notes_log_canvas, self.notes_inner)
            self.notes_inner.update_idletasks()
            self.notes_log_canvas.configure(scrollregion=self.notes_log_canvas.bbox("all"))
            return

        shown = filtered

        if not shown:
            tk.Label(
                self.notes_inner, text="无匹配结果",
                font=(FTK, 11), fg=_C["mute"], bg=_C["card"],
            ).pack(expand=True, pady=30)
            self._bind_scroll_recursive(self.notes_log_canvas, self.notes_inner)
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
                widget.bind("<Double-1>", lambda e, i=idx: self._edit_note_at(i) if not self._dragging else None)
                widget.bind("<Button-3>", lambda e, i=idx: self._show_note_ctx(e, i))
                widget.bind("<ButtonPress-1>", lambda e, i=idx: self._on_note_press(e, i))
                widget.bind("<B1-Motion>", self._on_note_motion)
                widget.bind("<ButtonRelease-1>", self._on_note_release)

        self._bind_scroll_recursive(self.notes_log_canvas, self.notes_inner)
        self.notes_inner.update_idletasks()
        self.notes_log_canvas.configure(scrollregion=self.notes_log_canvas.bbox("all"))

    def _refresh_folder_list(self):
        for w in self._folder_inner.winfo_children():
            w.destroy()

        self._folder_wrappers = []

        # "全部" 固定项
        all_btn = self._make_folder_btn("全部", None)
        all_btn.pack(fill=tk.X, pady=2)

        for f in self.folders:
            btn = self._make_folder_btn(f["name"], f["id"])
            btn.pack(fill=tk.X, pady=2)

    def _make_folder_btn(self, name, folder_id):
        selected = (self._current_folder == folder_id)
        wrapper = tk.Frame(self._folder_inner, bg=_C["sidebar"])
        wrapper._folder_id = folder_id
        self._folder_wrappers.append(wrapper)

        ind = tk.Frame(wrapper, width=3, bg=_C["sb_sel"] if selected else _C["sidebar"])
        ind.pack(side=tk.LEFT, fill=tk.Y)

        fg = _C["sb_sel"] if selected else _C["sb_text"]
        fnt = (FTK, 11, "bold") if selected else (FTK, 11)
        lbl = tk.Label(wrapper, text=name, font=fnt, fg=fg, bg=_C["sidebar"],
                       cursor="hand2", anchor="w", padx=6)
        lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4)
        wrapper._lbl = lbl

        # 省略号截断
        max_w = self._folder_panel_width - 15
        self._truncate_label(lbl, name, max_w)

        # 条件 tooltip
        tip_win = {"win": None}

        def show_tip(e):
            if getattr(lbl, '_truncated', False) and not tip_win["win"]:
                x = lbl.winfo_rootx()
                y = lbl.winfo_rooty() + lbl.winfo_height() + 2
                win = tk.Toplevel(self.root)
                win.overrideredirect(True)
                win.attributes("-topmost", True)
                win.geometry(f"+{x}+{y}")
                tk.Label(win, text=lbl._full_name, font=(FTK, 9),
                         fg=_C["pri"], bg=_C["card"], relief="solid", bd=1, padx=6, pady=2).pack()
                tip_win["win"] = win

        def hide_tip(e):
            if tip_win["win"]:
                tip_win["win"].destroy()
                tip_win["win"] = None

        def hover(e):
            show_tip(e)
            if not (self._current_folder == folder_id):
                lbl.config(fg=_C["sb_sel"])
                ind.config(bg=_C["sb_hover"])
            wrapper.config(bg=_C["sb_hover"])

        def leave(e):
            hide_tip(e)
            lbl.config(fg=_C["sb_sel"] if (self._current_folder == folder_id) else _C["sb_text"])
            ind.config(bg=_C["sb_sel"] if (self._current_folder == folder_id) else _C["sidebar"])
            wrapper.config(bg=_C["sidebar"])

        def click(e):
            self._select_folder(folder_id)

        def cleanup(e):
            if tip_win["win"]:
                tip_win["win"].destroy()
                tip_win["win"] = None
        wrapper.bind("<Destroy>", cleanup)

        for w in (wrapper, lbl, ind):
            w.bind("<Enter>", hover)
            w.bind("<Leave>", leave)
            w.bind("<Button-1>", click)

        # 右键菜单（非"全部"项）
        if folder_id is not None:
            def ctx(e):
                menu = tk.Menu(self.root, tearoff=0)
                menu.add_command(label="重命名", command=lambda: self._rename_folder(folder_id))
                menu.add_command(label="删除", command=lambda: self._delete_folder(folder_id))
                menu.post(e.x_root, e.y_root)
            wrapper.bind("<Button-3>", ctx)
            lbl.bind("<Button-3>", ctx)

        return wrapper

    def _select_folder(self, folder_id):
        self._current_folder = folder_id
        self._refresh_folder_list()
        self._refresh_notes()

    def _on_note_press(self, event, idx):
        self._drag_note_idx = idx
        self._dragging = False
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root

    def _on_note_motion(self, event):
        dx = abs(event.x_root - self._drag_start_x)
        dy = abs(event.y_root - self._drag_start_y)
        if dx > 5 or dy > 5:
            self._dragging = True
            # 高亮鼠标下方的文件夹
            target = self.root.winfo_containing(event.x_root, event.y_root)
            for w in getattr(self, '_folder_wrappers', []):
                if w.winfo_exists():
                    is_target = False
                    t = target
                    while t:
                        if t == w:
                            is_target = True
                            break
                        t = t.master if hasattr(t, 'master') else None
                    if is_target and w._folder_id is not None:
                        w.config(bg=_C["sb_hover"])
                        w._lbl.config(fg=_C["sb_sel"])
                    else:
                        w.config(bg=_C["sidebar"])
                        w._lbl.config(fg=_C["sb_sel"] if (self._current_folder == w._folder_id) else _C["sb_text"])

    def _on_note_release(self, event):
        if self._dragging:
            self._drop_note_to_folder(event.x_root, event.y_root)
            # 恢复所有文件夹背景
            for w in getattr(self, '_folder_wrappers', []):
                if w.winfo_exists():
                    w.config(bg=_C["sidebar"])
                    w._lbl.config(fg=_C["sb_sel"] if (self._current_folder == w._folder_id) else _C["sb_text"])
        self._dragging = False
        self._drag_note_idx = None

    def _drop_note_to_folder(self, x, y):
        target_widget = self.root.winfo_containing(x, y)
        target_folder_id = None
        w = target_widget
        while w:
            if hasattr(w, "_folder_id"):
                target_folder_id = w._folder_id
                break
            w = w.master
        if target_folder_id is None and target_widget is not None:
            pw = target_widget.winfo_parent()
            if pw:
                try:
                    pw_widget = target_widget._nametowidget(pw)
                    if hasattr(pw_widget, "_folder_id"):
                        target_folder_id = pw_widget._folder_id
                except Exception:
                    pass
        if target_folder_id is not None and self._drag_note_idx is not None:
            if 0 <= self._drag_note_idx < len(self.notes):
                if self.notes[self._drag_note_idx].get("folder_id", "") != target_folder_id:
                    self.notes[self._drag_note_idx]["folder_id"] = target_folder_id
                    self._save_notes()
                    self._refresh_notes()

    def _add_folder(self):
        dlg = FolderDialog(self.root, "新建文件夹")
        if dlg.result:
            import uuid
            self.folders.append({"id": uuid.uuid4().hex[:8], "name": dlg.result})
            self._save_folders()
            self._refresh_folder_list()

    def _rename_folder(self, folder_id):
        folder = next((f for f in self.folders if f["id"] == folder_id), None)
        if not folder:
            return
        dlg = FolderDialog(self.root, "重命名文件夹", initial=folder["name"])
        if dlg.result:
            folder["name"] = dlg.result
            self._save_folders()
            self._refresh_folder_list()
            self._refresh_notes()

    def _delete_folder(self, folder_id):
        folder_name = self._get_folder_name(folder_id)
        if not _confirm_dialog(self.root, "删除文件夹", f"确定删除文件夹「{folder_name}」？其中的笔记将移至未分类。"):
            return
        # 清空该文件夹下笔记的 folder_id
        for note in self.notes:
            if note.get("folder_id") == folder_id:
                note["folder_id"] = ""
        self._save_notes()
        self.folders = [f for f in self.folders if f["id"] != folder_id]
        self._save_folders()
        if self._current_folder == folder_id:
            self._current_folder = None
        self._refresh_folder_list()
        self._refresh_notes()

    def _get_folder_name(self, folder_id):
        if not folder_id:
            return "未分类"
        folder = next((f for f in self.folders if f["id"] == folder_id), None)
        return folder["name"] if folder else "未分类"

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

    def _save_folders(self):
        self._save_json(self.folders_file, self.folders)

    def _refresh_todos(self):
        for w in self.todos_inner.winfo_children():
            w.destroy()

        if not self.todos:
            tk.Label(
                self.todos_inner, text="暂无待办，输入后添加",
                font=(FTK, 11), fg=_C["mute"], bg=_C["card"],
            ).pack(expand=True, pady=30)
            self._bind_scroll_recursive(self.todos_log_canvas, self.todos_inner)
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

            # 文字（占满整行，双击编辑）
            font_spec = (FTK, 11, "overstrike") if td.get("done") else (FTK, 11)
            fg_color = _C["mute"] if td.get("done") else _C["pri"]
            lbl = tk.Label(item, text=td["text"], font=font_spec,
                           fg=fg_color, bg=_C["item_bg"], anchor="w", cursor="hand2")
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6)
            circ.bind("<Button-1>", lambda e, i=idx: self._toggle_todo_at(i))
            lbl.bind("<Double-1>", lambda e, i=idx: self._edit_todo_at(i, e.widget))

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

        self._bind_scroll_recursive(self.todos_log_canvas, self.todos_inner)
        self.todos_inner.update_idletasks()
        self.todos_log_canvas.configure(scrollregion=self.todos_log_canvas.bbox("all"))

    def _add_todo(self):
        text = self._td_search.get().strip()
        if not text or text == "添加待办...":
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
        if not _confirm_dialog(self.root, "删除待办", "确定删除这条待办？"):
            return
        self.todos.pop(idx)
        self._save_todos()
        self._refresh_todos()

    def _edit_todo_at(self, idx, lbl):
        """双击待办文字，弹窗编辑"""
        old_text = self.todos[idx]["text"]
        dlg = FolderDialog(self.root, "编辑待办", initial=old_text)
        if dlg.result:
            self.todos[idx]["text"] = dlg.result
            self._save_todos()
            self._refresh_todos()

    def _clear_done_todos(self):
        done_count = sum(1 for t in self.todos if t.get("done"))
        if not _confirm_dialog(self.root, "清除已完成", f"确定清除 {done_count} 条已完成待办？"):
            return
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

        self.stats_canvas = tk.Canvas(page, bg=_C["bg"], highlightthickness=0)
        self.stats_canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        stats_outer = tk.Frame(self.stats_canvas, bg=_C["card"])
        self.stats_log_canvas = tk.Canvas(stats_outer, bg=_C["card"], highlightthickness=0)
        stats_sb = tk.Scrollbar(stats_outer, command=self.stats_log_canvas.yview)
        self.stats_log_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        stats_sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.stats_log_canvas.configure(yscrollcommand=stats_sb.set)
        self.stats_inner = tk.Frame(self.stats_log_canvas, bg=_C["card"])
        self.stats_log_canvas.create_window((0, 0), window=self.stats_inner, anchor="nw")
        self.stats_inner.bind("<Configure>",
                              lambda e: self.stats_log_canvas.configure(scrollregion=self.stats_log_canvas.bbox("all")))
        self.stats_log_canvas.bind("<MouseWheel>",
                                   lambda e: self.stats_log_canvas.yview_scroll(int(-e.delta / 120), "units"))
        self._stats_outer = stats_outer

        self._st_export_lbl = tk.Label(page, text="导出CSV", font=(FTK, 10),
                                       fg=_C["mute"], bg=_C["card"], cursor="hand2")
        self._st_export_lbl.bind("<Button-1>", lambda e: self._export_csv())
        self._st_export_lbl.bind("<Enter>", lambda e: self._st_export_lbl.config(fg=_C["pri"]))
        self._st_export_lbl.bind("<Leave>", lambda e: self._st_export_lbl.config(fg=_C["mute"]))

        self.stats_canvas.bind("<Configure>", self._on_stats_resize)

    def _on_stats_resize(self, event):
        c = self.stats_canvas
        w, h = event.width, event.height
        if w < 60 or h < 60:
            return
        c.delete("st_bg")
        _round_rect(c, 4, 4, w - 2, h - 2, r=14, fill=_C["shadow"], outline="", tags="st_bg")
        _round_rect(c, 2, 2, w - 4, h - 4, r=14, fill=_C["card"], outline=_C["border"], width=1, tags="st_bg")
        c.create_text(16, 22, text="总体统计", font=(FTK, 15, "bold"),
                      fill=_C["pri"], anchor="w", tags="st_bg")
        c.create_window(w - 14, 22, window=self._st_export_lbl, anchor="e", tags="st_bg")
        c.create_line(12, 42, w - 12, 42, fill=_C["border"], width=1, tags="st_bg")
        c.create_window(10, 48, window=self._stats_outer, anchor="nw",
                        width=w - 20, height=h - 52, tags="st_bg")
        # 图表宽度自适应
        chart_w = w - 40
        if chart_w != getattr(self, '_st_chart_w', 0):
            self._st_chart_w = chart_w
            self._redraw_stats_charts(chart_w)

    def _redraw_stats_charts(self, chart_w):
        """根据宽度重绘统计图表"""
        if getattr(self, '_st_week_cv', None):
            self._st_week_cv.delete("all")
            self._st_week_cv.config(width=chart_w)
            self._draw_weekly_chart(self._st_week_cv, chart_w,
                                    getattr(self, '_st_week_data', {}))
        if getattr(self, '_st_trend_cv', None):
            self._st_trend_cv.delete("all")
            self._st_trend_cv.config(width=chart_w)
            self._draw_trend_chart(self._st_trend_cv, chart_w,
                                   getattr(self, '_st_trend_data', []))

    def _bind_chart_hover(self, cv, data_attr):
        """给图表 canvas 绑定悬停显示数值"""
        tip = {"win": None}

        def on_motion(e):
            # 清除旧 tooltip
            if tip["win"]:
                tip["win"].destroy()
                tip["win"] = None
            regions = getattr(cv, data_attr, [])
            for r in regions:
                x1, y1, x2, y2, text = r
                if x1 <= e.x <= x2 and y1 <= e.y <= y2:
                    win = tk.Toplevel(cv)
                    win.overrideredirect(True)
                    win.attributes("-topmost", True)
                    wx = cv.winfo_rootx() + e.x + 10
                    wy = cv.winfo_rooty() + e.y - 25
                    win.geometry(f"+{wx}+{wy}")
                    tk.Label(win, text=text, font=(FTK, 9),
                             fg=_C["pri"], bg=_C["card"], relief="solid",
                             bd=1, padx=6, pady=2).pack()
                    tip["win"] = win
                    break

        def on_leave(e):
            if tip["win"]:
                tip["win"].destroy()
                tip["win"] = None

        cv.bind("<Motion>", on_motion)
        cv.bind("<Leave>", on_leave)

    def _draw_weekly_chart(self, cv, chart_w, week_data):
        """绘制本周每日柱状图，week_data: {0: minutes, 1: minutes, ...} 周一=0"""
        days_label = ["一", "二", "三", "四", "五", "六", "日"]
        chart_h = 100
        bar_w = max(16, (chart_w - 40) // 7 - 4)
        gap = max(4, (chart_w - 7 * bar_w) // 8)
        today_weekday = datetime.now().date().weekday()

        max_val = max(week_data.values(), default=0) or 1

        # 存储柱子区域用于悬停检测
        cv._bar_rects = []

        for i in range(7):
            mins = week_data.get(i, 0)
            bar_h = int((mins / max_val) * (chart_h - 20)) if mins > 0 else 0
            x = gap + i * (bar_w + gap)
            y_top = chart_h - bar_h

            fill = _C["accent"] if i == today_weekday else _C["border"]
            rid = _round_rect(cv, x, y_top, x + bar_w, chart_h, r=4, fill=fill, outline="")
            cv._bar_rects.append((x, y_top, x + bar_w, chart_h, f"周{days_label[i]}: {mins}分钟"))

            if mins > 0:
                cv.create_text(x + bar_w // 2, y_top - 8,
                               text=str(mins), font=(FTK, 8), fill=_C["sec"])

            cv.create_text(x + bar_w // 2, chart_h + 10,
                           text=days_label[i], font=(FTK, 9),
                           fill=_C["accent"] if i == today_weekday else _C["sec"])

    def _draw_trend_chart(self, cv, chart_w, trend_data):
        """绘制近 14 天趋势折线图，trend_data: [(date, minutes), ...]"""
        n = len(trend_data)
        if n == 0:
            return
        chart_h = 100
        pad_x = 20
        usable_w = chart_w - pad_x * 2
        step = usable_w / (n - 1) if n > 1 else 0
        max_m = max(m for _, m in trend_data) or 1
        today_date = datetime.now().date()

        # 计算坐标
        points = []
        for i, (d, mins) in enumerate(trend_data):
            x = pad_x + i * step
            y = chart_h - int(mins / max_m * (chart_h - 20)) if mins > 0 else chart_h
            points.append((x, y, d, mins))

        # 画折线
        if len(points) >= 2:
            coords = []
            for x, y, _, _ in points:
                coords.extend([x, y])
            cv.create_line(coords, fill=_C["accent"], width=2, smooth=True)

        # 存储数据点区域用于悬停检测
        cv._trend_points = []

        # 画数据点和标签
        for i, (x, y, d, mins) in enumerate(points):
            is_today = (d == today_date)
            dot_r = 4 if is_today else 3
            dot_color = _C["accent"] if is_today else _C["sec"]
            cv.create_oval(x - dot_r, y - dot_r, x + dot_r, y + dot_r,
                           fill=dot_color, outline=_C["card"], width=2)
            cv._trend_points.append((x - 8, y - 8, x + 8, y + 8,
                                     f"{d.strftime('%m/%d')}: {mins}分钟"))
            if mins > 0:
                cv.create_text(x, y - 10, text=str(mins), font=(FTK, 8),
                               fill=_C["sec"])
            # 日期标签（每 3 天一个）
            if i % 3 == 0:
                cv.create_text(x, chart_h + 10, text=d.strftime("%m/%d"),
                               font=(FTK, 9),
                               fill=_C["accent"] if is_today else _C["mute"])

    def _refresh_stats_page(self):
        for w in self.stats_inner.winfo_children():
            w.destroy()

        stats = self.stats
        _fmt = self._fmt_minutes

        total_count = sum(v["count"] for v in stats.values())
        total_minutes = sum(v["minutes"] for v in stats.values())
        total_days = len(stats)

        # 累计
        summary = tk.Frame(self.stats_inner, bg=_C["item_bg"], padx=10, pady=8)
        summary.pack(fill=tk.X, pady=(0, 6))
        tk.Label(summary, text=f"累计专注  {total_count} 次  /  {_fmt(total_minutes)}  /  {total_days} 天",
                 font=(FTK, 11), fg=_C["pri"], bg=_C["item_bg"]).pack()

        # 连续打卡
        streak = self._calc_streak()
        if streak > 0:
            streak_frame = tk.Frame(self.stats_inner, bg=_C["item_bg"], padx=10, pady=6)
            streak_frame.pack(fill=tk.X, pady=(0, 6))
            tk.Label(streak_frame, text=f"连续打卡  {streak} 天",
                     font=(FTK, 12, "bold"), fg=_C["accent"], bg=_C["item_bg"]).pack()

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

        period = tk.Frame(self.stats_inner, bg=_C["item_bg"], padx=10, pady=6)
        period.pack(fill=tk.X, pady=(0, 8))
        tk.Label(period, text=f"本周  {week_c} 次  /  {_fmt(week_m)}",
                 font=(FTK, 11), fg=_C["sec"], bg=_C["item_bg"]).pack(anchor="w")
        tk.Label(period, text=f"本月  {month_c} 次  /  {_fmt(month_m)}",
                 font=(FTK, 11), fg=_C["sec"], bg=_C["item_bg"]).pack(anchor="w")

        # 本周柱状图
        week_data = {}
        for ds, v in stats.items():
            try:
                d = datetime.strptime(ds, "%Y-%m-%d").date()
                if week_start <= d <= today:
                    week_data[d.weekday()] = v["minutes"]
            except ValueError:
                pass
        self._st_week_data = week_data
        self._st_week_cv = tk.Canvas(self.stats_inner, width=280, height=120,
                                      bg=_C["card"], highlightthickness=0)
        self._st_week_cv.pack(fill=tk.X, pady=(4, 8))
        self._bind_chart_hover(self._st_week_cv, "_bar_rects")

        # 近 14 天趋势
        trend_data = []
        for i in range(13, -1, -1):
            d = today - timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            trend_data.append((d, stats.get(ds, {}).get("minutes", 0)))
        self._st_trend_data = trend_data
        self._st_trend_cv = tk.Canvas(self.stats_inner, width=280, height=124,
                                       bg=_C["card"], highlightthickness=0)
        self._st_trend_cv.pack(fill=tk.X, pady=(4, 8))
        self._bind_chart_hover(self._st_trend_cv, "_trend_points")

        # 图表初始绘制
        self._st_chart_w = 0
        w = self.stats_canvas.winfo_width()
        if w > 60:
            self._redraw_stats_charts(w - 40)

        # 事项统计
        topic_stats = {}
        for ev in self.events:
            topic = ev.get("topic", "未命名专注")
            mins = ev.get("minutes", 0)
            if topic not in topic_stats:
                topic_stats[topic] = {"count": 0, "minutes": 0}
            topic_stats[topic]["count"] += 1
            topic_stats[topic]["minutes"] += mins
        if topic_stats:
            tk.Label(self.stats_inner, text="事项统计", font=(FTK, 13, "bold"),
                     fg=_C["pri"], bg=_C["card"]).pack(anchor="w", pady=(8, 4))
            sorted_topics = sorted(topic_stats.items(), key=lambda x: x[1]["minutes"], reverse=True)[:10]
            for topic, s in sorted_topics:
                row = tk.Frame(self.stats_inner, bg=_C["card"])
                row.pack(fill=tk.X, padx=(8, 0), pady=1)
                tk.Label(row, text=topic, font=(FTK, 10),
                         fg=_C["pri"], bg=_C["card"], anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
                tk.Label(row, text=f"{s['count']} 次 / {_fmt(s['minutes'])}",
                         font=(FTK, 9), fg=_C["sec"], bg=_C["card"]).pack(side=tk.RIGHT)

        # 每日记录（按周分组）
        tk.Label(self.stats_inner, text="专注记录", font=(FTK, 13, "bold"),
                 fg=_C["pri"], bg=_C["card"]).pack(anchor="w", pady=(0, 6))

        if not self.events:
            tk.Label(self.stats_inner, text="暂无记录", font=(FTK, 11),
                     fg=_C["mute"], bg=_C["card"]).pack(pady=20)
        else:
            from collections import OrderedDict
            # 按日期分组事件
            date_events = OrderedDict()
            for idx, ev in enumerate(self.events):
                time_str = ev.get("time", "")
                if len(time_str) >= 10:
                    date_str = time_str[:10]
                elif len(time_str) >= 5:
                    date_str = str(datetime.now().year) + "-" + time_str[:5]
                else:
                    date_str = "??-??"
                if date_str not in date_events:
                    date_events[date_str] = []
                date_events[date_str].append((idx, ev))

            # 按 ISO 周分组
            weeks = OrderedDict()
            for ds in reversed(list(date_events.keys())):
                try:
                    d = datetime.strptime(ds, "%Y-%m-%d").date()
                    iso_year, iso_week, _ = d.isocalendar()
                    key = (iso_year, iso_week)
                    if key not in weeks:
                        weeks[key] = []
                    weeks[key].append(ds)
                except ValueError:
                    pass

            for (year, week_num), date_list in weeks.items():
                # 周汇总
                w_c = sum(len(date_events[ds]) for ds in date_list)
                w_m = sum(ev.get("minutes", 0) for ds in date_list for _, ev in date_events[ds])
                try:
                    week_date = datetime.strptime(f"{year}-W{week_num:02d}-1", "%G-W%V-%u").date()
                    week_end = week_date + timedelta(days=6)
                    range_str = f"{week_date.strftime('%m/%d')} - {week_end.strftime('%m/%d')}"
                except Exception:
                    range_str = ""

                week_row = tk.Frame(self.stats_inner, bg=_C["card"])
                week_row.pack(fill=tk.X, pady=(6, 2))
                tk.Label(week_row, text=f"第 {week_num} 周 ({range_str})",
                         font=(FTK, 10, "bold"), fg=_C["pri"], bg=_C["card"],
                         width=22, anchor="w").pack(side=tk.LEFT)
                tk.Label(week_row, text=f"{w_c} 次 / {_fmt(w_m)}",
                         font=(FTK, 10), fg=_C["sec"], bg=_C["card"],
                         anchor="e").pack(side=tk.RIGHT)

                # 每日条目
                for ds in date_list:
                    day_row = tk.Frame(self.stats_inner, bg=_C["card"])
                    day_row.pack(fill=tk.X, padx=(16, 0), pady=(4, 1))
                    tk.Label(day_row, text=ds[5:] if len(ds) >= 10 else ds, font=(FTK, 10, "bold"),
                             fg=_C["sec"], bg=_C["card"], width=8, anchor="w").pack(side=tk.LEFT)

                    ev_list = date_events[ds]
                    day_m = sum(ev.get("minutes", 0) for _, ev in ev_list)
                    tk.Label(day_row, text=f"{len(ev_list)} 次 / {_fmt(day_m)}",
                             font=(FTK, 9), fg=_C["mute"], bg=_C["card"],
                             anchor="w").pack(side=tk.LEFT)

                    # 单条事件
                    for ev_idx, ev in ev_list:
                        ev_row = tk.Frame(self.stats_inner, bg=_C["card"])
                        ev_row.pack(fill=tk.X, padx=(32, 0), pady=1)
                        time_label = ev.get("time", "")
                        if len(time_label) >= 11:
                            time_label = time_label[11:]  # "HH:MM"
                        elif len(time_label) >= 6:
                            time_label = time_label[6:]
                        tk.Label(ev_row, text=time_label, font=(FTK, 9),
                                 fg=_C["mute"], bg=_C["card"], width=6, anchor="w").pack(side=tk.LEFT)
                        tk.Label(ev_row, text=ev.get("topic", ""), font=(FTK, 10),
                                 fg=_C["pri"], bg=_C["card"], anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True)
                        tk.Label(ev_row, text=f"{ev.get('minutes', 0)}分钟", font=(FTK, 9),
                                 fg=_C["sec"], bg=_C["card"]).pack(side=tk.LEFT)
                        del_btn = tk.Label(ev_row, text="×", font=(FTK, 14),
                                           fg=_C["border"], bg=_C["card"], cursor="hand2")
                        del_btn.pack(side=tk.RIGHT, padx=(4, 8))
                        del_btn.bind("<Button-1>", lambda e, i=ev_idx: self._delete_event_from_stats(i))
                        del_btn.bind("<Enter>", lambda e: e.widget.config(fg=_C["accent"]))
                        del_btn.bind("<Leave>", lambda e: e.widget.config(fg=_C["border"]))

        self._bind_scroll_recursive(self.stats_log_canvas, self.stats_inner)
        self.stats_inner.update_idletasks()
        self.stats_log_canvas.configure(scrollregion=self.stats_log_canvas.bbox("all"))

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

        def section_title(text):
            tk.Label(card, text=text, font=(FTK, 11, "bold"),
                     fg=_C["sec"], bg=_C["card"]).pack(anchor="w", pady=(12, 4))

        section_title("通用")
        add_toggle("sound_enabled", "声音提醒")
        add_toggle("auto_start_focus", "休息结束后自动开始专注")
        add_toggle("always_on_top", "窗口置顶")
        add_toggle("minimize_to_tray", "关闭时最小化到托盘")

        sep = tk.Frame(card, bg=_C["border"], height=1)
        sep.pack(fill=tk.X, pady=8)

        section_title("计时节奏")
        add_spin("focus_total_min", "总专注时长（分钟）", 15, 480)
        add_spin("rhythm_focus", "专注节奏（分钟）", 5, 60)
        add_spin("rhythm_break", "短休息（分钟）", 1, 30)
        add_spin("rhythm_long_break", "长休息（分钟）", 5, 60)
        add_spin("rhythm_long_interval", "长休息间隔（个番茄）", 2, 10)
        add_spin("daily_goal_pomodoros", "每日目标（个番茄）", 1, 20)

        sep2 = tk.Frame(card, bg=_C["border"], height=1)
        sep2.pack(fill=tk.X, pady=8)

        section_title("闲置检测")
        add_toggle("idle_detection", "闲置检测（无操作自动暂停）")
        add_spin("idle_timeout_min", "闲置超时（分钟）", 1, 30)

        tk.Label(card, text="FlowTick V2.3", font=(FTK, 9),
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
            if key == "daily_goal_pomodoros":
                self._update_goal_indicator()
        except ValueError:
            pass

    def _bind_scroll_recursive(self, canvas, outer):
        fn = lambda e: canvas.yview_scroll(int(-e.delta / 120), "units")
        def _bind(w):
            w.bind("<MouseWheel>", fn)
            for child in w.winfo_children():
                _bind(child)
        _bind(outer)

    def _truncate(self, text, font_spec, max_width):
        """截断文本到指定像素宽度，末尾加省略号"""
        f = tkfont.Font(font=font_spec)
        if f.measure(text) <= max_width:
            return text
        while len(text) > 1 and f.measure(text + "…") > max_width:
            text = text[:-1]
        return text + "…"

    @staticmethod
    def _fmt_minutes(minutes):
        if minutes >= 60:
            h, m = divmod(minutes, 60)
            if m == 0:
                return f"{h} 小时"
            return f"{h} 小时 {m} 分钟"
        return f"{minutes} 分钟"

    def _calc_streak(self):
        dates = sorted(self.stats.keys(), reverse=True)
        if not dates:
            return 0
        streak = 0
        check = datetime.now().date()
        while check.strftime("%Y-%m-%d") in self.stats:
            streak += 1
            check -= timedelta(days=1)
        return streak

    def _add_note(self):
        default_folder = self._current_folder if self._current_folder else ""
        dlg = NoteDialog(self.root, "添加笔记", folders=self.folders, folder_id=default_folder)
        if dlg.result:
            title, content, folder_id = dlg.result
            now = datetime.now().strftime("%m-%d %H:%M")
            self.notes.append({"title": title, "content": content, "time": now, "folder_id": folder_id})
            self._save_notes()
            self._refresh_notes()
            self.notes_log_canvas.yview_moveto(1.0)

    def _edit_note_at(self, idx):
        note = self.notes[idx]
        dlg = NoteDialog(self.root, "编辑笔记", title=note["title"], content=note["content"],
                         folders=self.folders, folder_id=note.get("folder_id", ""))
        if dlg.result:
            title, content, folder_id = dlg.result
            self.notes[idx] = {"title": title, "content": content, "folder_id": folder_id,
                               "time": note.get("time", "")}
            self._save_notes()
            self._refresh_notes()

    def _delete_note_at(self, idx):
        if not _confirm_dialog(self.root, "删除笔记", "确定删除这条笔记？"):
            return
        self.notes.pop(idx)
        self._save_notes()
        self._refresh_notes()

    def _show_note_ctx(self, event, idx):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="删除", command=lambda: self._delete_note_at(idx))
        menu.post(event.x_root, event.y_root)

    # ── 系统托盘 ──────────────────────────────────────────

    def _make_tray_icon(self):
        """加载透明 LOGO 作为托盘图标"""
        from PIL import Image
        _path = self._tray_logo_path if os.path.exists(self._tray_logo_path) else self._logo_path
        if os.path.exists(_path):
            try:
                return Image.open(_path).convert("RGBA").resize((64, 64))
            except Exception:
                pass
        # fallback
        from PIL import ImageDraw
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, 62, 62], fill="#4A90D9", outline="#2C5F8A", width=2)
        return img

    def _init_tray(self):
        """初始化并显示系统托盘图标"""
        import pystray
        icon_image = self._make_tray_icon()
        menu = pystray.Menu(
            pystray.MenuItem("开始/暂停", lambda: self.root.after(0, self._on_toggle)),
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
        self.root.after(0, self._save_session)
        self._tray_running = False
        self._tray_icon.stop()
        self.root.after(0, self.root.destroy)

    # ── Timer ──────────────────────────────────────────

    def _init_timer(self):
        self.timer = Timer(
            self.root,
            on_tick=self._on_tick,
            on_segment_change=self._on_segment_change,
            on_session_end=self._on_session_end,
        )
        if not self._load_session():
            self._build_session()
            first_seg_min = self.timer.segments[0][1] if self.timer.segments else 25
            self._update_timer_display(first_seg_min * 60)

    def _build_session(self):
        s = self.settings
        self.timer.build_session(
            s.get("focus_total_min", 60),
            s.get("rhythm_focus", 25),
            s.get("rhythm_break", 5),
            s.get("rhythm_long_break", 15),
            s.get("rhythm_long_interval", 4),
        )

    def _on_tick(self, remaining):
        self._update_timer_display(remaining)
        self._update_tray_title(remaining)

    def _update_tray_title(self, remaining):
        if not self._tray_running:
            return
        m, s = divmod(max(remaining, 0), 60)
        if self.timer.current_idx < len(self.timer.segments):
            seg_type = self.timer.segments[self.timer.current_idx][0]
        else:
            seg_type = Timer.FOCUS
        label = {Timer.FOCUS: "专注", Timer.SHORT_BREAK: "休息", Timer.LONG_BREAK: "长休息"}.get(seg_type, "专注")
        self._tray_icon.title = f"FlowTick - {label} {m:02d}:{s:02d}"

    def _on_segment_change(self, seg_type, seg_min, seg_idx, total, focus_acc, focus_total):
        """segment 切换回调"""
        self._arc_total = seg_min * 60
        label_map = {Timer.FOCUS: "专注", Timer.SHORT_BREAK: "短休息", Timer.LONG_BREAK: "长休息"}
        self.mode_label.config(text=label_map.get(seg_type, "专注"))

        # 进度文字
        focus_count = self.timer.current_focus_index
        total_focus = self.timer.focus_segments
        self.status_label.config(text=f"第 {focus_count + 1}/{total_focus} 个番茄 · 已专注 {focus_acc}/{focus_total} 分钟")
        self.topic_label.config(text=self.focus_topic if self.focus_topic else "准备就绪")

        if seg_type == Timer.FOCUS:
            # 从休息进入专注
            if seg_idx > 0:
                if self.settings.get("sound_enabled", True):
                    threading.Thread(target=lambda: winsound.Beep(1200, 300), daemon=True).start()
                threading.Thread(target=lambda: _win_notify("FlowTick", "休息结束，开始专注"), daemon=True).start()
                self._redraw_btn(self.toggle_btn, "⏸")
        else:
            # 从专注进入休息
            if seg_type == Timer.LONG_BREAK:
                msg = f"长休息 {seg_min} 分钟"
            else:
                msg = f"休息 {seg_min} 分钟"

            if self.settings.get("sound_enabled", True):
                threading.Thread(target=lambda: winsound.Beep(880, 500), daemon=True).start()
            BreakOverlay(self.root, msg)
            threading.Thread(target=lambda: _win_notify("FlowTick", f"专注结束，{msg}"), daemon=True).start()

    def _on_session_end(self, focus_acc):
        """会话结束回调"""
        total_focus = self.timer.focus_segments
        if focus_acc > 0:
            self._record_focus(focus_acc)
        self.mode_label.config(text="完成")
        self.status_label.config(text=f"本次会话完成 {total_focus} 个番茄，共专注 {focus_acc} 分钟")
        self._update_timer_display(0)
        if self.settings.get("sound_enabled", True):
            threading.Thread(target=lambda: winsound.Beep(1200, 300), daemon=True).start()
        threading.Thread(target=lambda: _win_notify("FlowTick", "会话完成！"), daemon=True).start()
        self._redraw_btn(self.toggle_btn, "▶")
        self._refresh_events()
        self._update_goal_indicator()
        if self._tray_running:
            self._tray_icon.title = "FlowTick - 会话完成"
        self._save_session()

    def _update_timer_display(self, seconds):
        m, s = divmod(seconds, 60)
        self.timer_label.config(text=f"{m:02d}:{s:02d}")
        # 更新进度弧
        if self._arc_total > 0:
            elapsed = self._arc_total - seconds
            ratio = max(0, min(1, elapsed / self._arc_total))
            self.timer_box.itemconfig(self._arc_progress, extent=int(-270 * ratio))

    def _update_goal_indicator(self):
        """更新今日目标进度小圆点"""
        if not hasattr(self, '_goal_cv'):
            return
        cv = self._goal_cv
        cv.delete("all")
        today = datetime.now().strftime("%Y-%m-%d")
        done = self.stats.get(today, {}).get("count", 0)
        goal = self.settings.get("daily_goal_pomodoros", 8)
        dot_r = 5
        gap = 6
        total_w = goal * (dot_r * 2 + gap)
        cv.config(width=max(total_w + 40, 120))
        for i in range(goal):
            x = 10 + i * (dot_r * 2 + gap) + dot_r
            if i < done:
                cv.create_oval(x - dot_r, 6 - dot_r, x + dot_r, 6 + dot_r,
                               fill=_C["accent"], outline=_C["accent"])
            else:
                cv.create_oval(x - dot_r, 6 - dot_r, x + dot_r, 6 + dot_r,
                               fill="", outline=_C["border"], width=1.5)
        cv.create_text(10 + goal * (dot_r * 2 + gap) + 6, 6,
                       text=f"今日 {done}/{goal}", font=(FTK, 9),
                       fill=_C["sec"], anchor="w")

    # ── 按钮事件 ───────────────────────────────────────

    def _on_toggle(self):
        if self.timer.state in (Timer.IDLE, Timer.PAUSED):
            self.timer.start() if self.timer.state == Timer.IDLE else self.timer.resume()
            self._redraw_btn(self.toggle_btn, "⏸")
            self._start_idle_check()
        elif self.timer.state == Timer.RUNNING:
            self.timer.pause()
            self._redraw_btn(self.toggle_btn, "▶")
        self._save_session()

    def _redraw_btn(self, btn, text):
        w, h = int(btn.cget("width")), int(btn.cget("height"))
        btn.delete("all")
        btn._rect = _round_rect(btn, 2, 2, w - 2, h - 2, r=10,
                                fill=_C["card"], outline=_C["border"])
        btn.create_text(w // 2, h // 2, text=text, font=(FTK, 14), fill=_C["pri"])
        btn._text = text

    def _on_terminate(self):
        if self.timer.state == Timer.IDLE:
            return
        focus_acc = self.timer.focus_accumulated
        if self.timer._job:
            self.root.after_cancel(self.timer._job)
            self.timer._job = None
        self.timer.state = Timer.IDLE
        if focus_acc > 0:
            self._record_focus(focus_acc)
        self.mode_label.config(text="已终止")
        self.status_label.config(text=f"已专注 {focus_acc} 分钟")
        self._update_timer_display(0)
        self._redraw_btn(self.toggle_btn, "▶")
        self._refresh_events()
        if focus_acc > 0:
            self._update_goal_indicator()
        if self._tray_running:
            self._tray_icon.title = "FlowTick - 已终止"
        self._save_session()

    def _on_reset(self):
        self.timer.reset()
        self._build_session()
        first_seg_min = self.timer.segments[0][1] if self.timer.segments else 25
        self._arc_total = 0
        self.timer_box.itemconfig(self._arc_progress, extent=0)
        self._update_timer_display(first_seg_min * 60)
        self.topic_label.config(text=self.focus_topic if self.focus_topic else "准备就绪")
        self.mode_label.config(text="专注")
        self.status_label.config(text="")
        if self._tray_running:
            self._tray_icon.title = "FlowTick"
        self._redraw_btn(self.toggle_btn, "▶")
        self._save_session()

    def _on_skip(self):
        self.timer.skip_segment()

    def _on_set_time(self):
        current_total = self.settings.get("focus_total_min", 60)
        dlg = SessionDialog(self.root, current_total, topic=self.focus_topic)
        if dlg.result:
            minutes, topic = dlg.result
            self.settings["focus_total_min"] = minutes
            self._save_settings()
            self.focus_topic = topic
            if topic:
                self.topic_label.config(text=topic)
            self.timer.reset()
            self._build_session()
            first_seg_min = self.timer.segments[0][1] if self.timer.segments else 25
            self._update_timer_display(first_seg_min * 60)
            self.mode_label.config(text="专注")
            self._redraw_btn(self.toggle_btn, "▶")

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


