import tkinter as tk
import tkinter.font as tkfont
import ctypes
import threading
import time
from config import LIGHT_COLORS

FTK = "Noto Sans SC"
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
                       fg=_C["pri"], bg=_C["card"], relief="solid", bd=1, padx=6, pady=2)
        lbl.pack()
        tip["win"] = win

    def leave(event):
        if tip["win"]:
            tip["win"].destroy()
            tip["win"] = None

    widget.bind("<Enter>", enter, add="+")
    widget.bind("<Leave>", leave, add="+")

    def destroy_tip(e):
        if tip["win"]:
            tip["win"].destroy()
            tip["win"] = None
    widget.bind("<Destroy>", destroy_tip, add="+")


def _win_notify(title, message):
    """Windows 原生气泡通知（Shell_NotifyIconW）"""
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

    def _delayed_remove():
        time.sleep(5.0)
        _remove()

    threading.Thread(target=_delayed_remove, daemon=True).start()


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


def _rounded_entry(parent, font_spec, placeholder=""):
    """圆角输入框，支持 fill=X 自适应宽度"""
    wrapper = tk.Frame(parent, bg=_C["card"])
    cv = tk.Canvas(wrapper, height=32, bg=_C["card"], highlightthickness=0)
    cv.pack(fill=tk.X, expand=True)

    entry = tk.Entry(wrapper, font=font_spec, bd=0, relief="flat",
                     bg=_C["card"], fg=_C["pri"], insertwidth=1,
                     highlightthickness=0)

    def _draw(e):
        cv.delete("all")
        _round_rect(cv, 1, 1, e.width - 1, 31, r=8,
                    fill=_C["card"], outline=_C["border"], width=1)
        cv.delete("entry_win")
        cv.create_window(10, 16, window=entry, anchor="w",
                         width=e.width - 20, height=24, tags="entry_win")

    cv.bind("<Configure>", _draw)
    if placeholder:
        entry.insert(0, placeholder)
        entry.config(fg=_C["mute"])

    def _focus_entry(e):
        entry.focus_set()
        return "break"
    cv.bind("<Button-1>", _focus_entry)

    wrapper._entry = entry
    return wrapper, entry


def _rounded_text(parent, font_spec, height=4):
    """圆角多行文本框，支持 fill=X 自适应宽度"""
    line_h = tkfont.Font(font=font_spec).metrics("linespace")
    inner_h = line_h * height + 16

    wrapper = tk.Frame(parent, bg=_C["card"])
    cv = tk.Canvas(wrapper, height=inner_h, bg=_C["card"], highlightthickness=0)
    cv.pack(fill=tk.BOTH, expand=True)

    text = tk.Text(wrapper, font=font_spec, bd=0, relief="flat",
                   bg=_C["card"], fg=_C["pri"], insertwidth=1,
                   highlightthickness=0, wrap=tk.WORD)
    sb = tk.Scrollbar(wrapper, command=text.yview)
    text.configure(yscrollcommand=sb.set)

    def _draw(e):
        cv.delete("all")
        _round_rect(cv, 1, 1, e.width - 1, inner_h - 1, r=8,
                    fill=_C["card"], outline=_C["border"], width=1)
        cv.delete("text_win")
        cv.create_window(10, inner_h // 2, window=text, anchor="w",
                         width=e.width - 30, height=inner_h - 16, tags="text_win")
        cv.delete("sb_win")
        cv.create_window(e.width - 12, inner_h // 2, window=sb, anchor="w",
                         width=12, height=inner_h - 16, tags="sb_win")

    cv.bind("<Configure>", _draw)

    def _focus_text(e):
        text.focus_set()
        return "break"
    cv.bind("<Button-1>", _focus_text)

    wrapper._text = text
    return wrapper, text


def _rounded_spinbox(parent, font_spec, from_, to_, textvariable):
    """圆角 Spinbox"""
    wrapper = tk.Frame(parent, bg=_C["card"])
    cv = tk.Canvas(wrapper, height=32, bg=_C["card"], highlightthickness=0)
    cv.pack(fill=tk.X, expand=True)

    spin = tk.Spinbox(wrapper, from_=from_, to=to_, font=font_spec,
                      textvariable=textvariable, bd=0, relief="flat",
                      bg=_C["card"], fg=_C["pri"], buttondownrelief="flat",
                      buttonuprelief="flat", highlightthickness=0,
                      insertwidth=1, justify="center")

    def _draw(e):
        cv.delete("all")
        _round_rect(cv, 1, 1, e.width - 1, 31, r=8,
                    fill=_C["card"], outline=_C["border"], width=1)
        cv.delete("spin_win")
        cv.create_window(10, 16, window=spin, anchor="w",
                         width=e.width - 20, height=24, tags="spin_win")

    cv.bind("<Configure>", _draw)

    def _focus_spin(e):
        spin.focus_set()
        return "break"
    cv.bind("<Button-1>", _focus_spin)

    wrapper._spin = spin
    return wrapper, spin


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
