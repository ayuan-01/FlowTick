import tkinter as tk
import tkinter.font as tkfont
import json
import os
import math
from datetime import datetime
from timer import Timer
from config import (
    DEFAULT_FOCUS_MIN, DEFAULT_BREAK_MIN,
    WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR,
)

FONT = "Helvetica"


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


class FlowTickApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FlowTick")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg=BG_COLOR)

        self.focus_min = DEFAULT_FOCUS_MIN
        self.break_min = DEFAULT_BREAK_MIN

        # 事件记录数据
        self.data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.json")
        self.events = self._load_events()

        self._build_ui()
        self._refresh_log()
        self._init_timer()
        self._update_clock()

    # ── UI ─────────────────────────────────────────────

    def _build_ui(self):
        main = tk.Frame(self.root, bg=BG_COLOR)
        main.pack(fill=tk.BOTH, expand=True)

        # ── 上半区：左右分栏 ──
        top = tk.Frame(main, bg=BG_COLOR)
        top.pack(fill=tk.BOTH, padx=10, pady=(5, 0))

        # 左侧：模拟时钟 + 数字时间
        left = tk.Frame(top, bg=BG_COLOR)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.clock_size = 160
        self.clock_canvas = tk.Canvas(
            left, width=self.clock_size, height=self.clock_size,
            bg=BG_COLOR, highlightthickness=0,
        )
        self.clock_canvas.pack(pady=(8, 2))

        self.clock_label = tk.Label(
            left, text="--:--:--", font=(FONT, 18),
            bg=BG_COLOR, fg="#333333",
        )
        self.clock_label.pack()

        # 中间竖线分隔
        tk.Frame(top, width=1, bg="#c0d8f0").pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        # 右侧：倒计时 + 图标按钮
        right = tk.Frame(top, bg=BG_COLOR)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.mode_label = tk.Label(
            right, text="专注", font=(FONT, 18, "bold"),
            bg=BG_COLOR, fg="#555555",
        )
        self.mode_label.pack(pady=(20, 0))

        # 倒计时圆角框
        timer_box = tk.Canvas(
            right, width=180, height=60,
            bg=BG_COLOR, highlightthickness=0,
        )
        timer_box.pack(pady=(15, 0))
        _round_rect(timer_box, 2, 2, 180, 60, r=14, fill="white", outline="#d0d8e0", width=1.5)

        self.timer_label = tk.Label(
            timer_box, text="25:00", font=(FONT, 30),
            bg="white", fg="#333333",
        )
        timer_box.create_window(91, 31, window=self.timer_label)

        btn_row = tk.Frame(right, bg=BG_COLOR)
        btn_row.pack(pady=(15, 10))

        icon_btn_style = dict(
            font=("黑体", 15), bg=BG_COLOR, bd=0,
            activebackground=BG_COLOR, cursor="hand2",
        )
        tk.Button(
            btn_row, text="🕐", font=("Segoe UI Emoji", 13),
            bg=BG_COLOR, bd=0, cursor="hand2",
            command=self._on_set_time,
        ).pack(side=tk.LEFT, padx=8)
        self.toggle_btn = tk.Button(btn_row, text="▶", width=2, command=self._on_toggle, **icon_btn_style)
        self.toggle_btn.pack(side=tk.LEFT, padx=8)
        tk.Button(btn_row, text="↺", font=("黑体", 15, "bold"), bg=BG_COLOR, bd=0, cursor="hand2", command=self._on_reset).pack(side=tk.LEFT, padx=8)

        # ── 分隔线 ──
        tk.Frame(main, height=1, bg="#c0d8f0").pack(fill=tk.X, padx=10, pady=5)

        # ── 下半区：事件记录卡片 ──
        card_container = tk.Frame(main, bg=BG_COLOR)
        card_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.card_canvas = tk.Canvas(
            card_container, bg=BG_COLOR, highlightthickness=0,
        )
        self.card_canvas.pack(fill=tk.BOTH, expand=True)

        # 可滚动事件列表
        list_outer = tk.Frame(self.card_canvas, bg="white")

        self.log_canvas = tk.Canvas(list_outer, bg="white", highlightthickness=0)
        scrollbar = tk.Scrollbar(list_outer, command=self.log_canvas.yview)
        self.log_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_canvas.configure(yscrollcommand=scrollbar.set)

        self.log_inner = tk.Frame(self.log_canvas, bg="white")
        self.log_canvas.create_window((0, 0), window=self.log_inner, anchor="nw")

        self.log_inner.bind("<Configure>",
                            lambda e: self.log_canvas.configure(scrollregion=self.log_canvas.bbox("all")))

        # 滚轮支持
        self.log_canvas.bind("<MouseWheel>", self._on_log_scroll)

        # 动态重绘（窗口缩放时）
        self._plus_btn = tk.Button(
            self.card_canvas, text="+", font=(FONT, 18),
            bg="white", bd=0, cursor="hand2",
            command=self._add_note, fg="#333333",
            activebackground="white",
        )
        self._list_outer = list_outer
        self.card_canvas.bind("<Configure>", self._on_card_resize)

    def _load_events(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def _save_events(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.events, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _on_log_scroll(self, event):
        self.log_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_card_resize(self, event):
        c = self.card_canvas
        w, h = event.width, event.height
        if w < 60 or h < 80:
            return
        c.delete("card_bg")

        # 阴影
        _round_rect(c, 4, 4, w - 2, h - 2, r=12, fill="#c8d8e8", outline="", tags="card_bg")
        # 卡片背景
        _round_rect(c, 2, 2, w - 4, h - 4, r=12, fill="white", outline="#d0d8e0", width=1, tags="card_bg")

        # 标题
        c.create_text(16, 22, text="事件记录", font=(FONT, 15, "bold"),
                      fill="#333333", anchor="w", tags="card_bg")
        # + 按钮
        c.create_window(w - 16, 22, window=self._plus_btn, anchor="e", tags="card_bg")

        # 分隔线
        c.create_line(12, 40, w - 12, 40, fill="#d0d8e0", width=1, tags="card_bg")

        # 列表
        c.create_window(10, 46, window=self._list_outer, anchor="nw",
                        width=w - 20, height=h - 50, tags="card_bg")

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
        self.clock_label.config(text=now.strftime("%H:%M:%S"))
        self._draw_analog_clock(now)
        self.root.after(1000, self._update_clock)

    def _draw_analog_clock(self, now):
        c = self.clock_canvas
        c.delete("all")
        s = self.clock_size
        cx, cy = s // 2, s // 2
        r = s // 2 - 8

        # 表盘背景（白色圆 + 外圈阴影）
        c.create_oval(cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2, fill="#d0d0d0", outline="")
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#f8f8f8", outline="#555555", width=1.5)

        # 内圈装饰
        c.create_oval(cx - r + 6, cy - r + 6, cx + r - 6, cy + r - 6, outline="#e0e0e0", width=0.5)

        # 整点刻度和数字
        for i in range(1, 13):
            angle = math.radians(i * 30 - 90)
            cos_a, sin_a = math.cos(angle), math.sin(angle)
            ix = cx + (r - 10) * cos_a
            iy = cy + (r - 10) * sin_a
            ox = cx + (r - 3) * cos_a
            oy = cy + (r - 3) * sin_a
            c.create_line(ix, iy, ox, oy, fill="#333333", width=2.5, capstyle=tk.ROUND)
            tx = cx + (r - 22) * cos_a
            ty = cy + (r - 22) * sin_a
            c.create_text(tx, ty, text=str(i), font=(FONT, 9, "bold"), fill="#333333")

        # 分钟刻度
        for i in range(60):
            if i % 5 != 0:
                angle = math.radians(i * 6 - 90)
                cos_a, sin_a = math.cos(angle), math.sin(angle)
                ix = cx + (r - 5) * cos_a
                iy = cy + (r - 5) * sin_a
                ox = cx + (r - 3) * cos_a
                oy = cy + (r - 3) * sin_a
                c.create_line(ix, iy, ox, oy, fill="#aaaaaa", width=0.8)

        h = now.hour % 12
        m = now.minute
        s_now = now.second

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

        # 时针
        h_angle = (h + m / 60) * 30
        pts = _hand_points(h_angle, r - 38, 10, 7)
        c.create_polygon(pts, fill="#333333", outline="#222222", smooth=True)

        # 分针
        m_angle = (m + s_now / 60) * 6
        pts = _hand_points(m_angle, r - 22, 14, 4.5)
        c.create_polygon(pts, fill="#555555", outline="#444444", smooth=True)

        # 秒针
        s_angle = s_now * 6
        sa = math.radians(s_angle - 90)
        cos_sa, sin_sa = math.cos(sa), math.sin(sa)
        tail_x = cx - 16 * cos_sa
        tail_y = cy - 16 * sin_sa
        c.create_line(tail_x, tail_y, cx, cy, fill="#e04040", width=1)
        tip_x = cx + (r - 14) * cos_sa
        tip_y = cy + (r - 14) * sin_sa
        c.create_line(cx, cy, tip_x, tip_y, fill="#e04040", width=1.5, capstyle=tk.ROUND)
        c.create_oval(tip_x - 2, tip_y - 2, tip_x + 2, tip_y + 2, fill="#e04040", outline="")

        # 中心轴
        c.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill="#555555", outline="#444444")
        c.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill="#e04040", outline="#cc3030")
        c.create_oval(cx - 1, cy - 1, cx + 1, cy + 1, fill="#ff6060", outline="")

    # ── 事件记录 ───────────────────────────────────────

    def _truncate(self, text, font_spec, max_width):
        """截断文本到指定像素宽度，末尾加省略号"""
        f = tkfont.Font(font=font_spec)
        if f.measure(text) <= max_width:
            return text
        while len(text) > 1 and f.measure(text + "…") > max_width:
            text = text[:-1]
        return text + "…"

    def _refresh_log(self):
        for w in self.log_inner.winfo_children():
            w.destroy()

        for idx, ev in enumerate(self.events):
            # 分隔线
            if idx > 0:
                tk.Frame(self.log_inner, height=1, bg="#e8e8e8").pack(fill=tk.X, padx=8, pady=(4, 0))

            # 条目容器（支持高亮和右键）
            item = tk.Frame(self.log_inner, bg="white")
            item.pack(fill=tk.X, padx=8, pady=2)

            title_lbl = tk.Label(
                item, text=ev["title"], font=("宋体", 12, "bold"),
                fg="#222222", bg="white", anchor="w",
            )
            title_lbl.pack(fill=tk.X, padx=4, pady=(4, 0))

            if ev["content"]:
                font_spec = ("宋体", 10)
                display = self._truncate(ev["content"], font_spec, 420)
                content_lbl = tk.Label(
                    item, text=display, font=font_spec,
                    fg="#666666", bg="white", anchor="w",
                )
                content_lbl.pack(fill=tk.X, padx=4, pady=(0, 4))

            # 绑定事件
            for widget in (item, title_lbl):
                widget.bind("<Double-1>", lambda e, i=idx: self._edit_note_at(i))
                widget.bind("<Button-3>", lambda e, i=idx: self._show_ctx_at(e, i))
            if ev["content"]:
                content_lbl.bind("<Double-1>", lambda e, i=idx: self._edit_note_at(i))
                content_lbl.bind("<Button-3>", lambda e, i=idx: self._show_ctx_at(e, i))

        # 更新滚动区域
        self.log_inner.update_idletasks()
        self.log_canvas.configure(scrollregion=self.log_canvas.bbox("all"))

    def _add_note(self):
        dlg = NoteDialog(self.root, "添加笔记")
        if dlg.result:
            title, content = dlg.result
            self.events.append({"title": title, "content": content})
            self._save_events()
            self._refresh_log()
            self.log_canvas.yview_moveto(1.0)

    def _edit_note_at(self, idx):
        ev = self.events[idx]
        dlg = NoteDialog(self.root, "编辑笔记", title=ev["title"], content=ev["content"])
        if dlg.result:
            title, content = dlg.result
            self.events[idx] = {"title": title, "content": content}
            self._save_events()
            self._refresh_log()

    def _delete_note_at(self, idx):
        self.events.pop(idx)
        self._save_events()
        self._refresh_log()

    def _show_ctx_at(self, event, idx):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="删除", command=lambda: self._delete_note_at(idx))
        menu.post(event.x_root, event.y_root)


# ── 对话框 ─────────────────────────────────────────────

class NoteDialog:
    def __init__(self, parent, title_text, title="", content=""):
        self.result = None

        self.dlg = tk.Toplevel(parent)
        self.dlg.title(title_text)
        self.dlg.resizable(False, False)
        self.dlg.transient(parent)
        self.dlg.grab_set()

        x, y = parent.winfo_pointerxy()
        self.dlg.geometry(f"320x220+{x - 160}+{y - 110}")

        frame = tk.Frame(self.dlg, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="标题：", font=(FONT, 11), fg="#333333").grid(row=0, column=0, sticky="w")
        self.title_entry = tk.Entry(frame, width=30, font=(FONT, 11))
        self.title_entry.grid(row=0, column=1, padx=5, pady=5)
        self.title_entry.insert(0, title)

        tk.Label(frame, text="内容：", font=(FONT, 11), fg="#333333").grid(row=1, column=0, sticky="nw")
        self.content_text = tk.Text(frame, width=30, height=6, font=(FONT, 11))
        self.content_text.grid(row=1, column=1, padx=5, pady=5)
        self.content_text.insert("1.0", content)

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        tk.Button(btn_frame, text="确定", width=8, font=(FONT, 10), command=self._ok).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", width=8, font=(FONT, 10), command=self.dlg.destroy).pack(side=tk.LEFT, padx=5)

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
        self.dlg.title("设置时间")
        self.dlg.resizable(False, False)
        self.dlg.transient(parent)
        self.dlg.grab_set()

        x, y = parent.winfo_pointerxy()
        self.dlg.geometry(f"240x140+{x - 120}+{y - 70}")

        frame = tk.Frame(self.dlg, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="专注（分钟）：", font=(FONT, 11), fg="#333333").grid(row=0, column=0, sticky="w")
        self.focus_entry = tk.Entry(frame, width=8, font=(FONT, 11))
        self.focus_entry.grid(row=0, column=1, padx=5, pady=5)
        self.focus_entry.insert(0, str(focus_min))

        tk.Label(frame, text="休息（分钟）：", font=(FONT, 11), fg="#333333").grid(row=1, column=0, sticky="w")
        self.break_entry = tk.Entry(frame, width=8, font=(FONT, 11))
        self.break_entry.grid(row=1, column=1, padx=5, pady=5)
        self.break_entry.insert(0, str(break_min))

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        tk.Button(btn_frame, text="确定", width=8, font=(FONT, 10), command=self._ok).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", width=8, font=(FONT, 10), command=self.dlg.destroy).pack(side=tk.LEFT, padx=5)

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
