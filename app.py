import tkinter as tk
from tkinter import simpledialog
from timer import Timer
from config import DEFAULT_FOCUS_MIN, DEFAULT_BREAK_MIN, WINDOW_WIDTH, WINDOW_HEIGHT


class FlowTickApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FlowTick")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)

        self.show_seconds = False
        self.focus_min = DEFAULT_FOCUS_MIN
        self.break_min = DEFAULT_BREAK_MIN

        self._build_ui()
        self._init_timer()
        self._update_clock()

    # ── UI ─────────────────────────────────────────────

    def _build_ui(self):
        # 上半区：左右分栏
        top = tk.Frame(self.root)
        top.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        # 左侧：当前时间
        left = tk.Frame(top)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.clock_label = tk.Label(left, text="--:--", font=("Segoe UI", 48))
        self.clock_label.pack(expand=True)
        self.clock_label.bind("<Button-1>", self._toggle_seconds)

        # 右侧：倒计时 + 按钮
        right = tk.Frame(top)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.mode_label = tk.Label(right, text="专注", font=("Segoe UI", 12))
        self.mode_label.pack(pady=(20, 0))

        self.timer_label = tk.Label(right, text="25:00", font=("Segoe UI", 36))
        self.timer_label.pack(expand=True)

        btn_row = tk.Frame(right)
        btn_row.pack(pady=(0, 10))

        tk.Button(btn_row, text="设置", width=6, command=self._on_settings).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_row, text="开始", width=6, command=self._on_start).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_row, text="暂停", width=6, command=self._on_pause).pack(side=tk.LEFT, padx=3)
        tk.Button(btn_row, text="重置", width=6, command=self._on_reset).pack(side=tk.LEFT, padx=3)

        # 分隔线
        tk.Frame(self.root, height=1, bg="gray").pack(fill=tk.X, padx=10, pady=5)

        # 下半区：事件记录
        bottom = tk.Frame(self.root)
        bottom.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        log_header = tk.Frame(bottom)
        log_header.pack(fill=tk.X)
        tk.Label(log_header, text="事件记录", font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        tk.Button(log_header, text="+", width=3, command=self._add_note).pack(side=tk.RIGHT)

        list_frame = tk.Frame(bottom)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Segoe UI", 10))
        self.log_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_list.yview)

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

    def _on_mode_change(self, mode):
        text = "专注" if mode == Timer.FOCUS else "休息"
        self.mode_label.config(text=text)

    def _update_timer_display(self, seconds):
        m, s = divmod(seconds, 60)
        self.timer_label.config(text=f"{m:02d}:{s:02d}")

    # ── 按钮事件 ───────────────────────────────────────

    def _on_start(self):
        if self.timer.state == Timer.IDLE:
            self.timer.start()
        elif self.timer.state == Timer.PAUSED:
            self.timer.resume()

    def _on_pause(self):
        if self.timer.state == Timer.RUNNING:
            self.timer.pause()
        elif self.timer.state == Timer.PAUSED:
            self.timer.resume()

    def _on_reset(self):
        self.timer.reset()
        self._update_timer_display(self.timer.focus_sec)
        self.mode_label.config(text="专注")

    def _on_settings(self):
        dlg = SettingsDialog(self.root, self.focus_min, self.break_min)
        if dlg.result:
            self.focus_min, self.break_min = dlg.result
            self.timer.set_durations(self.focus_min * 60, self.break_min * 60)

    # ── 当前时间 ───────────────────────────────────────

    def _update_clock(self):
        from datetime import datetime
        now = datetime.now()
        if self.show_seconds:
            text = now.strftime("%H:%M:%S")
        else:
            text = now.strftime("%H:%M")
        self.clock_label.config(text=text)
        self.root.after(1000, self._update_clock)

    def _toggle_seconds(self, event=None):
        self.show_seconds = not self.show_seconds

    # ── 事件记录 ───────────────────────────────────────

    def _add_note(self):
        note = simpledialog.askstring("添加笔记", "输入笔记内容：", parent=self.root)
        if note and note.strip():
            from datetime import datetime
            time_str = datetime.now().strftime("%H:%M")
            self.log_list.insert(tk.END, f"{time_str}  {note.strip()}")


class SettingsDialog(simpledialog.Dialog):
    def __init__(self, parent, focus_min, break_min):
        self.focus_min = focus_min
        self.break_min = break_min
        self.result = None
        super().__init__(parent, "设置")

    def body(self, master):
        tk.Label(master, text="专注时长（分钟）：").grid(row=0, column=0, sticky="w")
        tk.Label(master, text="休息时长（分钟）：").grid(row=1, column=0, sticky="w")

        self.focus_entry = tk.Entry(master, width=10)
        self.break_entry = tk.Entry(master, width=10)

        self.focus_entry.grid(row=0, column=1, padx=5, pady=5)
        self.break_entry.grid(row=1, column=1, padx=5, pady=5)

        self.focus_entry.insert(0, str(self.focus_min))
        self.break_entry.insert(0, str(self.break_min))

        return self.focus_entry

    def apply(self):
        try:
            f = int(self.focus_entry.get())
            b = int(self.break_entry.get())
            if f > 0 and b > 0:
                self.result = (f, b)
        except ValueError:
            pass
