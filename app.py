import tkinter as tk
from datetime import datetime
from timer import Timer
from config import (
    DEFAULT_FOCUS_MIN, DEFAULT_BREAK_MIN,
    WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR,
)


class FlowTickApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FlowTick")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.configure(bg=BG_COLOR)

        self.show_seconds = False
        self.focus_min = DEFAULT_FOCUS_MIN
        self.break_min = DEFAULT_BREAK_MIN

        # 事件记录数据
        self.events = []  # [{"title": str, "content": str}]

        self._build_ui()
        self._init_timer()
        self._update_clock()

    # ── UI ─────────────────────────────────────────────

    def _build_ui(self):
        # 主容器
        main = tk.Frame(self.root, bg=BG_COLOR)
        main.pack(fill=tk.BOTH, expand=True)

        # ── 上半区：左右分栏 ──
        top = tk.Frame(main, bg=BG_COLOR)
        top.pack(fill=tk.BOTH, padx=10, pady=(5, 0))

        # 左侧：模拟时钟 + 数字时间
        left = tk.Frame(top, bg=BG_COLOR)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.clock_size = 130
        self.clock_canvas = tk.Canvas(
            left, width=self.clock_size, height=self.clock_size,
            bg=BG_COLOR, highlightthickness=0,
        )
        self.clock_canvas.pack(pady=(10, 2))

        self.clock_label = tk.Label(
            left, text="--:--", font=("黑体", 16),
            bg=BG_COLOR, fg="#333333",
        )
        self.clock_label.pack()
        self.clock_label.bind("<Button-1>", self._toggle_seconds)

        # 中间竖线分隔
        tk.Frame(top, width=1, bg="#c0d8f0").pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # 右侧：倒计时 + 图标按钮
        right = tk.Frame(top, bg=BG_COLOR)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.mode_label = tk.Label(
            right, text="专注", font=("黑体", 11),
            bg=BG_COLOR, fg="#555555",
        )
        self.mode_label.pack(pady=(10, 0))

        self.timer_label = tk.Label(
            right, text="25:00", font=("黑体", 30),
            bg=BG_COLOR, fg="#333333",
        )
        self.timer_label.pack(expand=True)

        btn_row = tk.Frame(right, bg=BG_COLOR)
        btn_row.pack(pady=(0, 10))

        icon_btn_style = dict(
            font=("黑体", 15), bg=BG_COLOR, bd=0,
            activebackground=BG_COLOR, cursor="hand2",
        )
        tk.Button(
            btn_row, text="🕐", font=("Segoe UI Emoji", 13),
            bg=BG_COLOR, bd=0, cursor="hand2",
            command=self._on_set_time,
        ).pack(side=tk.LEFT, padx=8)
        self.toggle_btn = tk.Button(btn_row, text="▶", command=self._on_toggle, **icon_btn_style)
        self.toggle_btn.pack(side=tk.LEFT, padx=8)
        tk.Button(btn_row, text="↺", command=self._on_reset, **icon_btn_style).pack(side=tk.LEFT, padx=8)

        # ── 分隔线 ──
        tk.Frame(main, height=1, bg="#c0d8f0").pack(fill=tk.X, padx=10, pady=5)

        # ── 下半区：事件记录 ──
        bottom = tk.Frame(main, bg=BG_COLOR)
        bottom.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        log_header = tk.Frame(bottom, bg=BG_COLOR)
        log_header.pack(fill=tk.X)
        tk.Label(
            log_header, text="事件记录", font=("黑体", 10, "bold"),
            bg=BG_COLOR, fg="#333333",
        ).pack(side=tk.LEFT)
        tk.Button(
            log_header, text="+", font=("黑体", 14),
            bg=BG_COLOR, bd=0, cursor="hand2",
            command=self._add_note,
        ).pack(side=tk.RIGHT)

        list_frame = tk.Frame(bottom, bg=BG_COLOR)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_list = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set,
            font=("黑体", 10), bg="white", fg="#333333",
            selectbackground="#b3d4fc",
        )
        self.log_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_list.yview)

        self.log_list.bind("<Double-1>", self._edit_note)
        self.log_list.bind("<Button-3>", self._show_context_menu)

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

    def _on_toggle(self):
        if self.timer.state in (Timer.IDLE, Timer.PAUSED):
            self.timer.start() if self.timer.state == Timer.IDLE else self.timer.resume()
            self.toggle_btn.config(text="⏸")
        elif self.timer.state == Timer.RUNNING:
            self.timer.pause()
            self.toggle_btn.config(text="▶")

    def _on_reset(self):
        self.timer.reset()
        self._update_timer_display(self.timer.focus_sec)
        self.mode_label.config(text="专注")
        self.toggle_btn.config(text="▶")

    def _on_set_time(self):
        dlg = TimeDialog(self.root, self.focus_min, self.break_min)
        if dlg.result:
            self.focus_min, self.break_min = dlg.result
            self.timer.set_durations(self.focus_min * 60, self.break_min * 60)

    # ── 当前时间 ───────────────────────────────────────

    def _update_clock(self):
        now = datetime.now()

        # 数字时间
        if self.show_seconds:
            text = now.strftime("%H:%M:%S")
        else:
            text = now.strftime("%H:%M")
        self.clock_label.config(text=text)

        # 模拟时钟
        self._draw_analog_clock(now)

        self.root.after(1000, self._update_clock)

    def _draw_analog_clock(self, now):
        c = self.clock_canvas
        c.delete("all")
        s = self.clock_size
        cx, cy = s // 2, s // 2
        r = s // 2 - 8

        # 表盘圆
        c.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#888888", width=2)

        import math

        # 刻度和数字
        for i in range(1, 13):
            angle = math.radians(i * 30 - 90)
            ix = cx + (r - 6) * math.cos(angle)
            iy = cy + (r - 6) * math.sin(angle)
            ox = cx + r * math.cos(angle)
            oy = cy + r * math.sin(angle)
            c.create_line(ix, iy, ox, oy, fill="#555555", width=2)
            tx = cx + (r - 16) * math.cos(angle)
            ty = cy + (r - 16) * math.sin(angle)
            c.create_text(tx, ty, text=str(i), font=("Segoe UI", 7), fill="#333333")

        # 分钟刻度
        for i in range(60):
            if i % 5 != 0:
                angle = math.radians(i * 6 - 90)
                ix = cx + (r - 3) * math.cos(angle)
                iy = cy + (r - 3) * math.sin(angle)
                ox = cx + r * math.cos(angle)
                oy = cy + r * math.sin(angle)
                c.create_line(ix, iy, ox, oy, fill="#aaaaaa", width=1)

        h = now.hour % 12
        m = now.minute
        s_now = now.second

        # 时针
        h_angle = math.radians((h + m / 60) * 30 - 90)
        hx = cx + (r - 30) * math.cos(h_angle)
        hy = cy + (r - 30) * math.sin(h_angle)
        c.create_line(cx, cy, hx, hy, fill="#333333", width=3, capstyle=tk.ROUND)

        # 分针
        m_angle = math.radians((m + s_now / 60) * 6 - 90)
        mx = cx + (r - 18) * math.cos(m_angle)
        my = cy + (r - 18) * math.sin(m_angle)
        c.create_line(cx, cy, mx, my, fill="#555555", width=2, capstyle=tk.ROUND)

        # 秒针
        s_angle = math.radians(s_now * 6 - 90)
        sx = cx + (r - 10) * math.cos(s_angle)
        sy = cy + (r - 10) * math.sin(s_angle)
        c.create_line(cx, cy, sx, sy, fill="#e04040", width=1, capstyle=tk.ROUND)

        # 中心圆点
        c.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill="#e04040", outline="")

    def _toggle_seconds(self, event=None):
        self.show_seconds = not self.show_seconds

    # ── 事件记录 ───────────────────────────────────────

    def _add_note(self):
        dlg = NoteDialog(self.root, "添加笔记")
        if dlg.result:
            title, content = dlg.result
            self.events.append({"title": title, "content": content})
            self.log_list.insert(tk.END, title)

    def _edit_note(self, event=None):
        sel = self.log_list.curselection()
        if not sel:
            return
        idx = sel[0]
        ev = self.events[idx]
        dlg = NoteDialog(self.root, "编辑笔记", title=ev["title"], content=ev["content"])
        if dlg.result:
            title, content = dlg.result
            self.events[idx] = {"title": title, "content": content}
            self.log_list.delete(idx)
            self.log_list.insert(idx, title)

    def _delete_note(self):
        sel = self.log_list.curselection()
        if not sel:
            return
        idx = sel[0]
        self.log_list.delete(idx)
        self.events.pop(idx)

    def _show_context_menu(self, event):
        sel = self.log_list.nearest(event.y)
        if sel < 0 or sel >= len(self.events):
            return
        self.log_list.selection_clear(0, tk.END)
        self.log_list.selection_set(sel)

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="删除", command=self._delete_note)
        menu.post(event.x_root, event.y_root)


# ── 对话框 ─────────────────────────────────────────────

class NoteDialog:
    """添加/编辑笔记对话框，包含标题和内容两个输入框"""

    def __init__(self, parent, title_text, title="", content=""):
        self.result = None

        self.dlg = tk.Toplevel(parent)
        self.dlg.title(title_text)
        self.dlg.geometry("320x220")
        self.dlg.resizable(False, False)
        self.dlg.transient(parent)
        self.dlg.grab_set()

        frame = tk.Frame(self.dlg, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="标题：").grid(row=0, column=0, sticky="w")
        self.title_entry = tk.Entry(frame, width=30)
        self.title_entry.grid(row=0, column=1, padx=5, pady=5)
        self.title_entry.insert(0, title)

        tk.Label(frame, text="内容：").grid(row=1, column=0, sticky="nw")
        self.content_text = tk.Text(frame, width=30, height=6)
        self.content_text.grid(row=1, column=1, padx=5, pady=5)
        self.content_text.insert("1.0", content)

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        tk.Button(btn_frame, text="确定", width=8, command=self._ok).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", width=8, command=self.dlg.destroy).pack(side=tk.LEFT, padx=5)

        self.title_entry.focus_set()
        self.dlg.wait_window()

    def _ok(self):
        title = self.title_entry.get().strip()
        content = self.content_text.get("1.0", tk.END).strip()
        if title:
            self.result = (title, content)
            self.dlg.destroy()


class TimeDialog:
    """设置专注和休息时长"""

    def __init__(self, parent, focus_min, break_min):
        self.result = None

        self.dlg = tk.Toplevel(parent)
        self.dlg.title("设置时间")
        self.dlg.geometry("240x140")
        self.dlg.resizable(False, False)
        self.dlg.transient(parent)
        self.dlg.grab_set()

        frame = tk.Frame(self.dlg, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="专注（分钟）：").grid(row=0, column=0, sticky="w")
        self.focus_entry = tk.Entry(frame, width=8)
        self.focus_entry.grid(row=0, column=1, padx=5, pady=5)
        self.focus_entry.insert(0, str(focus_min))

        tk.Label(frame, text="休息（分钟）：").grid(row=1, column=0, sticky="w")
        self.break_entry = tk.Entry(frame, width=8)
        self.break_entry.grid(row=1, column=1, padx=5, pady=5)
        self.break_entry.insert(0, str(break_min))

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        tk.Button(btn_frame, text="确定", width=8, command=self._ok).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", width=8, command=self.dlg.destroy).pack(side=tk.LEFT, padx=5)

        self.focus_entry.focus_set()
        self.dlg.wait_window()

    def _ok(self):
        try:
            f = int(self.focus_entry.get())
            b = int(self.break_entry.get())
            if f > 0 and b > 0:
                self.result = (f, b)
                self.dlg.destroy()
        except ValueError:
            pass
