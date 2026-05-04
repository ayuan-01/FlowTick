import tkinter as tk
import tkinter.font as tkfont
import json
import os
import sys
import math
import threading
from datetime import datetime
from timer import Timer
from config import (
    DEFAULT_FOCUS_MIN, DEFAULT_BREAK_MIN,
    WINDOW_WIDTH, WINDOW_HEIGHT, BG_COLOR,
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

# 统一色系（冷灰蓝，色温一致）
_C = {
    "bg":      "#eef1f5",   # 页面背景
    "card":    "#ffffff",   # 卡片背景
    "shadow":  "#d5dce6",   # 阴影（比旧 #c8d8e8 更柔和）
    "border":  "#e4e8ee",   # 边框（比旧 #d0d8e0 更浅）
    "pri":     "#2a2a2a",   # 主文字
    "sec":     "#6b7280",   # �要文字
    "mute":    "#9ca3af",   # 辅助文字
    "accent":  "#e04040",   # 强调色（秒针、删除）
    "hover":   "#e8ecf1",   # 按钮 hover
    "active":  "#d8dee6",   # 按钮 active
    "item_bg": "#f7f9fb",   # 事件条目底色
}


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


def _canvas_btn(parent, text, command, card_bg=_C["card"]):
    """带圆角背景的按钮 Canvas，hover 变色、点击闪烁"""
    cv = tk.Canvas(parent, width=46, height=36,
                   bg=card_bg, highlightthickness=0, cursor="hand2")
    rect = _round_rect(cv, 2, 2, 44, 34, r=10,
                       fill=card_bg, outline=_C["border"])
    cv.create_text(23, 18, text=text, font=(FTK, 14), fill=_C["pri"])
    cv._rect = rect
    cv._cmd = command

    def hover(_):
        cv.itemconfig(rect, fill=_C["hover"])
    def leave(_):
        cv.itemconfig(rect, fill=card_bg)
    def click(_):
        cv.itemconfig(rect, fill=_C["active"])
        cv.after(100, lambda: cv.itemconfig(rect, fill=_C["hover"]))
        cv.after(120, cv._cmd)

    cv.bind("<Enter>", hover)
    cv.bind("<Leave>", leave)
    cv.bind("<Button-1>", click)
    return cv


class FlowTickApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FlowTick")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.configure(bg=_C["bg"])

        self.focus_min = DEFAULT_FOCUS_MIN
        self.break_min = DEFAULT_BREAK_MIN

        # 事件记录数据
        base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        self.data_file = os.path.join(base_dir, "events.json")
        self.stats_file = os.path.join(base_dir, "stats.json")
        self.events = self._load_events()
        self.stats = self._load_stats()

        self._build_ui()
        self._refresh_log()
        self._init_timer()
        self._update_clock()
        self._init_tray()

        # 拦截关闭按钮，最小化到托盘
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

    # ── UI ─────────────────────────────────────────────

    def _build_ui(self):
        main = tk.Frame(self.root, bg=_C["bg"])
        main.pack(fill=tk.BOTH, expand=True)

        # ── 上半区：白色圆角卡片 ──
        top_container = tk.Frame(main, bg=_C["bg"])
        top_container.pack(fill=tk.BOTH, padx=12, pady=(8, 0))

        self.top_canvas = tk.Canvas(
            top_container, bg=_C["bg"], highlightthickness=0,
        )
        self.top_canvas.pack(fill=tk.BOTH, expand=True)

        # 左侧：模拟时钟 + 数字时间
        left = tk.Frame(self.top_canvas, bg=_C["card"])
        self.clock_size = 150
        self.clock_canvas = tk.Canvas(
            left, width=self.clock_size, height=self.clock_size,
            bg=_C["card"], highlightthickness=0,
        )
        self.clock_canvas.pack(pady=(12, 2))
        self.clock_label = tk.Label(
            left, text="--:--:--", font=(FTK, 16),
            bg=_C["card"], fg=_C["sec"],
        )
        self.clock_label.pack(pady=(0, 12))

        # 右侧：模式 + 倒计时 + 按钮
        right = tk.Frame(self.top_canvas, bg=_C["card"])

        self.focus_topic = ""

        self.mode_label = tk.Label(
            right, text="专注", font=(FTK, 16, "bold"),
            bg=_C["card"], fg=_C["sec"],
        )
        self.mode_label.pack(pady=(16, 0))

        self.topic_label = tk.Label(
            right, text="", font=(FTK, 10),
            bg=_C["card"], fg=_C["mute"],
        )
        self.topic_label.pack(pady=(2, 0))

        # 倒计时圆角框
        timer_box = tk.Canvas(
            right, width=180, height=65,
            bg=_C["card"], highlightthickness=0,
        )
        timer_box.pack(pady=(12, 0))
        _round_rect(timer_box, 2, 2, 180, 65, r=14,
                    fill=_C["bg"], outline=_C["border"], width=1.5)
        self.timer_label = tk.Label(
            timer_box, text="25:00", font=(FTK, 36, "bold"),
            bg=_C["bg"], fg=_C["pri"],
        )
        timer_box.create_window(91, 34, window=self.timer_label)

        # 按钮行
        btn_row = tk.Frame(right, bg=_C["card"])
        btn_row.pack(pady=(14, 14))

        self.time_btn = _canvas_btn(btn_row, "⏱", self._on_set_time)
        self.time_btn.pack(side=tk.LEFT, padx=8)
        self.toggle_btn = _canvas_btn(btn_row, "▶", self._on_toggle)
        self.toggle_btn.pack(side=tk.LEFT, padx=8)
        self.reset_btn = _canvas_btn(btn_row, "↺", self._on_reset)
        self.reset_btn.pack(side=tk.LEFT, padx=8)
        self.stats_btn = _canvas_btn(btn_row, "📊", self._on_stats)
        self.stats_btn.pack(side=tk.LEFT, padx=8)

        self._left_frame = left
        self._right_frame = right
        self.top_canvas.bind("<Configure>", self._on_top_resize)

        # ── 下半区：事件记录卡片 ──
        card_container = tk.Frame(main, bg=_C["bg"])
        card_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(6, 10))

        self.card_canvas = tk.Canvas(
            card_container, bg=_C["bg"], highlightthickness=0,
        )
        self.card_canvas.pack(fill=tk.BOTH, expand=True)

        # 可滚动事件列表
        list_outer = tk.Frame(self.card_canvas, bg=_C["card"])

        self.log_canvas = tk.Canvas(list_outer, bg=_C["card"], highlightthickness=0)
        scrollbar = tk.Scrollbar(list_outer, command=self.log_canvas.yview)
        self.log_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_canvas.configure(yscrollcommand=scrollbar.set)

        self.log_inner = tk.Frame(self.log_canvas, bg=_C["card"])
        self.log_canvas.create_window((0, 0), window=self.log_inner, anchor="nw")

        self.log_inner.bind("<Configure>",
                            lambda e: self.log_canvas.configure(scrollregion=self.log_canvas.bbox("all")))

        # 滚轮支持
        self.log_canvas.bind("<MouseWheel>", self._on_log_scroll)

        # 动态重绘（窗口缩放时）
        plus_canvas = tk.Canvas(
            self.card_canvas, width=32, height=32,
            bg=_C["card"], highlightthickness=0,
        )
        plus_canvas.create_oval(2, 2, 30, 30, fill=_C["bg"], outline=_C["border"])
        plus_canvas.create_text(16, 16, text="+", font=(FTK, 16, "bold"), fill=_C["sec"])
        plus_canvas.bind("<Button-1>", lambda e: self._add_note())
        self._plus_btn = plus_canvas
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

    def _on_log_scroll(self, event):
        self.log_canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_top_resize(self, event):
        c = self.top_canvas
        w, h = event.width, event.height
        if w < 100 or h < 80:
            return
        c.delete("top_bg")

        # 阴影
        _round_rect(c, 4, 4, w - 2, h - 2, r=14,
                    fill=_C["shadow"], outline="", tags="top_bg")
        # 卡片背景
        _round_rect(c, 2, 2, w - 4, h - 4, r=14,
                    fill=_C["card"], outline=_C["border"], width=1, tags="top_bg")

        mid = w // 2

        # 左右帧
        c.create_window(2, 2, window=self._left_frame, anchor="nw",
                        width=mid - 2, height=h - 4, tags="top_bg")
        c.create_window(mid + 1, 2, window=self._right_frame, anchor="nw",
                        width=w - mid - 3, height=h - 4, tags="top_bg")

        # 中间分隔线
        c.create_line(mid, 18, mid, h - 18,
                      fill="#eef0f3", width=1, tags="top_bg")

    def _on_card_resize(self, event):
        c = self.card_canvas
        w, h = event.width, event.height
        if w < 60 or h < 80:
            return
        c.delete("card_bg")

        # 阴影
        _round_rect(c, 4, 4, w - 2, h - 2, r=14,
                    fill=_C["shadow"], outline="", tags="card_bg")
        # 卡片背景
        _round_rect(c, 2, 2, w - 4, h - 4, r=14,
                    fill=_C["card"], outline=_C["border"], width=1, tags="card_bg")

        # 标题
        c.create_text(16, 22, text="事件记录", font=(FTK, 15, "bold"),
                      fill=_C["pri"], anchor="w", tags="card_bg")
        # + 按钮
        c.create_window(w - 16, 22, window=self._plus_btn, anchor="e", tags="card_bg")

        # 分隔线
        c.create_line(12, 40, w - 12, 40, fill=_C["border"], width=1, tags="card_bg")

        # 列表
        c.create_window(10, 46, window=self._list_outer, anchor="nw",
                        width=w - 20, height=h - 50, tags="card_bg")

    # ── 系统托盘 ──────────────────────────────────────────

    def _make_tray_icon(self):
        """生成一个简单的时钟托盘图标"""
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # 外圆
        draw.ellipse([2, 2, 62, 62], fill="#4A90D9", outline="#2C5F8A", width=2)
        # 时针
        draw.line([(32, 32), (32, 16)], fill="white", width=3)
        # 分针
        draw.line([(32, 32), (46, 38)], fill="white", width=2)
        # 中心点
        draw.ellipse([29, 29, 35, 35], fill="white")
        return img

    def _init_tray(self):
        """初始化系统托盘图标（不显示）"""
        import pystray
        icon_image = self._make_tray_icon()
        menu = pystray.Menu(
            pystray.MenuItem("显示", self._show_from_tray, default=True),
            pystray.MenuItem("退出", self._quit_from_tray),
        )
        self._tray_icon = pystray.Icon("FlowTick", icon_image, "FlowTick", menu)
        self._tray_running = False

    def _hide_to_tray(self):
        """隐藏窗口到系统托盘"""
        self.root.withdraw()
        if not self._tray_running:
            self._tray_running = True
            threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _show_from_tray(self, icon=None, item=None):
        """从托盘恢复窗口"""
        self.root.after(0, self._restore_window)

    def _restore_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit_from_tray(self, icon=None, item=None):
        """从托盘退出程序"""
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

    def _on_mode_change(self, mode):
        if mode == Timer.BREAK:
            self._record_focus()
            self.topic_label.config(text="")
            self.focus_topic = ""
        text = "专注" if mode == Timer.FOCUS else "休息"
        self.mode_label.config(text=text)

    def _update_timer_display(self, seconds):
        m, s = divmod(seconds, 60)
        self.timer_label.config(text=f"{m:02d}:{s:02d}")

    # ── 按钮事件 ───────────────────────────────────────

    def _on_toggle(self):
        if self.timer.state in (Timer.IDLE, Timer.PAUSED):
            self.timer.start() if self.timer.state == Timer.IDLE else self.timer.resume()
            self.toggle_btn.itemconfig(self.toggle_btn._rect, fill=_C["card"])
            self.toggle_btn.delete("all")
            self.toggle_btn._rect = _round_rect(
                self.toggle_btn, 2, 2, 44, 34, r=10,
                fill=_C["card"], outline=_C["border"])
            self.toggle_btn.create_text(
                23, 18, text="⏸", font=(FTK, 14), fill=_C["pri"])
        elif self.timer.state == Timer.RUNNING:
            self.timer.pause()
            self.toggle_btn.delete("all")
            self.toggle_btn._rect = _round_rect(
                self.toggle_btn, 2, 2, 44, 34, r=10,
                fill=_C["card"], outline=_C["border"])
            self.toggle_btn.create_text(
                23, 18, text="▶", font=(FTK, 14), fill=_C["pri"])

    def _on_reset(self):
        self.timer.reset()
        self._update_timer_display(self.timer.focus_sec)
        self.mode_label.config(text="专注")
        self.topic_label.config(text="")
        self.focus_topic = ""
        self.toggle_btn.delete("all")
        self.toggle_btn._rect = _round_rect(
            self.toggle_btn, 2, 2, 44, 34, r=10,
            fill=_C["card"], outline=_C["border"])
        self.toggle_btn.create_text(
            23, 18, text="▶", font=(FTK, 14), fill=_C["pri"])

    def _on_set_time(self):
        dlg = TimeDialog(self.root, self.focus_min, self.break_min)
        if dlg.result:
            self.focus_min, self.break_min, self.focus_topic = dlg.result
            self.timer.set_durations(self.focus_min * 60, self.break_min * 60)
            if self.focus_topic:
                self.topic_label.config(text=self.focus_topic)

    def _on_stats(self):
        StatsDialog(self.root, self.stats)

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
        c.create_oval(cx - r - 2, cy - r - 2, cx + r + 2, cy + r + 2,
                      fill="#d0d0d0", outline="")
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                      fill="#f8f8f8", outline="#555555", width=1.5)

        # 内圈装饰
        c.create_oval(cx - r + 6, cy - r + 6, cx + r - 6, cy + r - 6,
                      outline="#e0e0e0", width=0.5)

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
            c.create_text(tx, ty, text=str(i), font=(FTK, 9, "bold"), fill="#333333")

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
        c.create_line(tail_x, tail_y, cx, cy, fill=_C["accent"], width=1)
        tip_x = cx + (r - 14) * cos_sa
        tip_y = cy + (r - 14) * sin_sa
        c.create_line(cx, cy, tip_x, tip_y, fill=_C["accent"], width=1.5, capstyle=tk.ROUND)
        c.create_oval(tip_x - 2, tip_y - 2, tip_x + 2, tip_y + 2,
                      fill=_C["accent"], outline="")

        # 中心轴
        c.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill="#555555", outline="#444444")
        c.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=_C["accent"], outline="#cc3030")
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

        if not self.events:
            tk.Label(
                self.log_inner, text="暂无记录，点击 + 添加",
                font=(FTK, 11), fg=_C["mute"], bg=_C["card"],
            ).pack(expand=True, pady=40)
            self.log_inner.update_idletasks()
            self.log_canvas.configure(scrollregion=self.log_canvas.bbox("all"))
            return

        for idx, ev in enumerate(self.events):
            # 条目容器（浅底色小卡片）
            item = tk.Frame(self.log_inner, bg=_C["item_bg"])
            item.pack(fill=tk.X, padx=6, pady=3)

            # 顶行：标题 + 时间 + 删除按钮
            top_row = tk.Frame(item, bg=_C["item_bg"])
            top_row.pack(fill=tk.X, padx=8, pady=(6, 0))

            title_lbl = tk.Label(
                top_row, text=ev["title"], font=(FTK, 12, "bold"),
                fg=_C["pri"], bg=_C["item_bg"], anchor="w",
            )
            title_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

            # 时间戳
            if ev.get("time"):
                tk.Label(
                    top_row, text=ev["time"], font=(FTK, 9),
                    fg=_C["mute"], bg=_C["item_bg"],
                ).pack(side=tk.LEFT, padx=(4, 0))

            # 删除按钮
            del_btn = tk.Label(
                top_row, text="×", font=(FTK, 14),
                fg="#cccccc", bg=_C["item_bg"], cursor="hand2",
            )
            del_btn.pack(side=tk.RIGHT, padx=(4, 0))
            del_btn.bind("<Button-1>", lambda e, i=idx: self._delete_note_at(i))
            del_btn.bind("<Enter>", lambda e: e.widget.config(fg=_C["accent"]))
            del_btn.bind("<Leave>", lambda e: e.widget.config(fg="#cccccc"))

            # 内容
            content_lbl = None
            if ev["content"]:
                font_spec = (FTK, 10)
                display = self._truncate(ev["content"], font_spec, 420)
                content_lbl = tk.Label(
                    item, text=display, font=font_spec,
                    fg=_C["sec"], bg=_C["item_bg"], anchor="w",
                )
                content_lbl.pack(fill=tk.X, padx=8, pady=(0, 6))
            else:
                tk.Frame(item, bg=_C["item_bg"], height=4).pack()

            # 双击编辑、右键菜单
            widgets = [item, title_lbl]
            if content_lbl:
                widgets.append(content_lbl)
            for widget in widgets:
                widget.bind("<Double-1>", lambda e, i=idx: self._edit_note_at(i))
                widget.bind("<Button-3>", lambda e, i=idx: self._show_ctx_at(e, i))

        # 更新滚动区域
        self.log_inner.update_idletasks()
        self.log_canvas.configure(scrollregion=self.log_canvas.bbox("all"))

    def _add_note(self):
        dlg = NoteDialog(self.root, "添加笔记")
        if dlg.result:
            title, content = dlg.result
            now = datetime.now().strftime("%m-%d %H:%M")
            self.events.append({"title": title, "content": content, "time": now})
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

        tk.Label(frame, text="标题：", font=(FTK, 11), fg=_C["pri"]).grid(row=0, column=0, sticky="w")
        self.title_entry = tk.Entry(frame, width=30, font=(FTK, 11))
        self.title_entry.grid(row=0, column=1, padx=5, pady=5)
        self.title_entry.insert(0, title)

        tk.Label(frame, text="内容：", font=(FTK, 11), fg=_C["pri"]).grid(row=1, column=0, sticky="nw")
        self.content_text = tk.Text(frame, width=30, height=6, font=(FTK, 11))
        self.content_text.grid(row=1, column=1, padx=5, pady=5)
        self.content_text.insert("1.0", content)

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        tk.Button(btn_frame, text="确定", width=8, font=(FTK, 10), command=self._ok).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", width=8, font=(FTK, 10), command=self.dlg.destroy).pack(side=tk.LEFT, padx=5)

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
        self.dlg.geometry(f"260x180+{x - 130}+{y - 90}")

        frame = tk.Frame(self.dlg, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="专注（分钟）：", font=(FTK, 11), fg=_C["pri"]).grid(row=0, column=0, sticky="w")
        self.focus_entry = tk.Entry(frame, width=10, font=(FTK, 11))
        self.focus_entry.grid(row=0, column=1, padx=5, pady=5)
        self.focus_entry.insert(0, str(focus_min))

        tk.Label(frame, text="休息（分钟）：", font=(FTK, 11), fg=_C["pri"]).grid(row=1, column=0, sticky="w")
        self.break_entry = tk.Entry(frame, width=10, font=(FTK, 11))
        self.break_entry.grid(row=1, column=1, padx=5, pady=5)
        self.break_entry.insert(0, str(break_min))

        tk.Label(frame, text="事项：", font=(FTK, 11), fg=_C["pri"]).grid(row=2, column=0, sticky="w")
        self.topic_entry = tk.Entry(frame, width=10, font=(FTK, 11))
        self.topic_entry.grid(row=2, column=1, padx=5, pady=5)

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        tk.Button(btn_frame, text="确定", width=8, font=(FTK, 10), command=self._ok).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="取消", width=8, font=(FTK, 10), command=self.dlg.destroy).pack(side=tk.LEFT, padx=5)

        self.focus_entry.focus_set()
        self.dlg.wait_window()

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


class StatsDialog:
    """专注统计面板"""

    def __init__(self, parent, stats):
        self.dlg = tk.Toplevel(parent)
        self.dlg.title("专注统计")
        self.dlg.resizable(False, False)
        self.dlg.transient(parent)
        self.dlg.grab_set()

        x, y = parent.winfo_pointerxy()
        self.dlg.geometry(f"320x380+{x - 160}+{y - 190}")

        frame = tk.Frame(self.dlg, padx=15, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # 汇总
        total_count = sum(v["count"] for v in stats.values())
        total_minutes = sum(v["minutes"] for v in stats.values())
        total_days = len(stats)

        tk.Label(frame, text="总体统计", font=(FTK, 14, "bold"), fg=_C["pri"]).pack(anchor="w", pady=(0, 8))

        summary = tk.Frame(frame, bg="#f0f4f8", padx=10, pady=8)
        summary.pack(fill=tk.X, pady=(0, 12))
        tk.Label(summary, text=f"累计专注  {total_count} 次  /  {total_minutes} 分钟  /  {total_days} 天",
                 font=(FTK, 11), fg=_C["pri"], bg="#f0f4f8").pack()

        # 每日记录
        tk.Label(frame, text="每日记录", font=(FTK, 13, "bold"), fg=_C["pri"]).pack(anchor="w", pady=(0, 6))

        # 滚动区域
        list_canvas = tk.Canvas(frame, highlightthickness=0)
        scrollbar = tk.Scrollbar(frame, command=list_canvas.yview)
        list_inner = tk.Frame(list_canvas)

        list_canvas.pack(fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        list_canvas.configure(yscrollcommand=scrollbar.set)
        list_canvas.create_window((0, 0), window=list_inner, anchor="nw")
        list_inner.bind("<Configure>",
                        lambda e: list_canvas.configure(scrollregion=list_canvas.bbox("all")))

        # 按日期倒序显示
        sorted_dates = sorted(stats.keys(), reverse=True)
        for date in sorted_dates:
            s = stats[date]
            row = tk.Frame(list_inner)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=date, font=(FTK, 10), fg=_C["sec"], width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{s['count']} 次", font=(FTK, 10, "bold"), fg=_C["pri"], width=6, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{s['minutes']} 分钟", font=(FTK, 10), fg=_C["pri"], anchor="w").pack(side=tk.LEFT)
            # 事项记录
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
