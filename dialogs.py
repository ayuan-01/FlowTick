import tkinter as tk
from widgets import FTK, _C, _canvas_btn, _rounded_entry, _rounded_text, _rounded_spinbox


def _dismiss_focus(event, dlg):
    w = event.widget
    while w:
        try:
            if w.winfo_toplevel() == w:
                break
            if str(w.cget("takefocus")) == "1":
                return
        except tk.TclError:
            pass
        w = w.master
    dlg.focus_set()


class NoteDialog:
    def __init__(self, parent, title_text, title="", content="", folders=None, folder_id=""):
        self.result = None

        self.dlg = tk.Toplevel(parent)
        self.dlg.withdraw()
        self.dlg.update()
        self.dlg.title(title_text)
        self.dlg.resizable(True, True)
        self.dlg.transient(parent)
        self.dlg.grab_set()
        self.dlg.configure(bg=_C["bg"])
        self.dlg.minsize(380, 320)

        card = tk.Frame(self.dlg, bg=_C["card"], padx=16, pady=14)
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(card, text=title_text, font=(FTK, 13, "bold"),
                 fg=_C["pri"], bg=_C["card"]).pack(anchor="w", pady=(0, 10))

        tk.Label(card, text="标题", font=(FTK, 10),
                 fg=_C["sec"], bg=_C["card"]).pack(anchor="w")
        self.title_entry_wrap, self.title_entry = _rounded_entry(card, (FTK, 11))
        self.title_entry_wrap.pack(fill=tk.X, pady=(2, 8))
        self.title_entry.insert(0, title)

        # 文件夹下拉
        tk.Label(card, text="文件夹", font=(FTK, 10),
                 fg=_C["sec"], bg=_C["card"]).pack(anchor="w")
        folder_names = ["未分类"]
        folder_ids = [""]
        if folders:
            for f in folders:
                folder_names.append(f["name"])
                folder_ids.append(f["id"])
        self._folder_ids = folder_ids
        self._folder_names = folder_names

        current_name = "未分类"
        if folder_id in folder_ids:
            idx = folder_ids.index(folder_id)
            current_name = folder_names[idx]

        self._folder_var = tk.StringVar(value=current_name)
        opt = tk.OptionMenu(card, self._folder_var, *folder_names)
        opt.config(font=(FTK, 10), bg=_C["card"], fg=_C["pri"],
                   activebackground=_C["hover"], relief="solid", bd=1,
                   highlightthickness=1, highlightbackground=_C["border"])
        opt["menu"].config(font=(FTK, 10))
        opt.pack(fill=tk.X, pady=(2, 8))

        tk.Label(card, text="内容", font=(FTK, 10),
                 fg=_C["sec"], bg=_C["card"]).pack(anchor="w")
        self.content_text_wrap, self.content_text = _rounded_text(card, (FTK, 11), height=5)
        self.content_text_wrap.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        self.content_text.insert("1.0", content)

        btn_row = tk.Frame(card, bg=_C["card"])
        btn_row.pack(fill=tk.X, pady=(10, 0))
        _canvas_btn(btn_row, "确定", self._ok, w=70).pack(side=tk.LEFT, padx=(0, 6))
        _canvas_btn(btn_row, "取消", self.dlg.destroy, w=70).pack(side=tk.LEFT)

        w = max(440, self.dlg.winfo_reqwidth())
        h = max(380, self.dlg.winfo_reqheight())
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.dlg.geometry(f"{w}x{h}+{px}+{py}")
        self.dlg.deiconify()

        self.title_entry.focus_set()
        self.dlg.bind("<Button-1>", lambda e: _dismiss_focus(e, self.dlg))
        self.dlg.wait_window()

    def _ok(self):
        title = self.title_entry.get().strip()
        content = self.content_text.get("1.0", tk.END).strip()
        if title:
            selected_name = self._folder_var.get()
            folder_id = ""
            if selected_name in self._folder_names:
                folder_id = self._folder_ids[self._folder_names.index(selected_name)]
            self.result = (title, content, folder_id)
            self.dlg.destroy()


class SessionDialog:
    """设置总专注时长"""

    def __init__(self, parent, current_total, topic=""):
        self.result = None

        self.dlg = tk.Toplevel(parent)
        self.dlg.withdraw()
        self.dlg.update()
        self.dlg.title("设置专注时长")
        self.dlg.resizable(True, True)
        self.dlg.transient(parent)
        self.dlg.grab_set()
        self.dlg.configure(bg=_C["bg"])
        self.dlg.minsize(340, 240)

        card = tk.Frame(self.dlg, bg=_C["card"], padx=16, pady=14)
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(card, text="总专注时长（分钟）", font=(FTK, 13, "bold"),
                 fg=_C["pri"], bg=_C["card"]).pack(anchor="w", pady=(0, 6))

        tk.Label(card, text="休息时间自动插入，不占专注额度",
                 font=(FTK, 9), fg=_C["mute"], bg=_C["card"]).pack(anchor="w", pady=(0, 10))

        row = tk.Frame(card, bg=_C["card"])
        row.pack(fill=tk.X, pady=(0, 10))
        var = tk.StringVar(value=str(current_total))
        spin_wrap, spin = _rounded_spinbox(row, (FTK, 14), 15, 480, var)
        spin_wrap.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(row, text=" 分钟", font=(FTK, 12),
                 fg=_C["sec"], bg=_C["card"]).pack(side=tk.LEFT, padx=(4, 0))
        self._var = var

        tk.Label(card, text="事项（可选）", font=(FTK, 10),
                 fg=_C["sec"], bg=_C["card"]).pack(anchor="w", pady=(4, 0))
        self._topic_entry_wrap, self._topic_entry = _rounded_entry(card, (FTK, 11))
        self._topic_entry_wrap.pack(fill=tk.X, pady=(2, 8))
        if topic:
            self._topic_entry.insert(0, topic)

        btn_row = tk.Frame(card, bg=_C["card"])
        btn_row.pack(fill=tk.X, pady=(6, 0))
        _canvas_btn(btn_row, "确定", self._ok, w=70).pack(side=tk.LEFT, padx=(0, 6))
        _canvas_btn(btn_row, "取消", self.dlg.destroy, w=70).pack(side=tk.LEFT)

        w = max(380, self.dlg.winfo_reqwidth())
        h = max(280, self.dlg.winfo_reqheight())
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.dlg.geometry(f"{w}x{h}+{px}+{py}")
        self.dlg.deiconify()

        spin.focus_set()
        spin.selection_range(0, tk.END)
        self.dlg.bind("<Button-1>", lambda e: _dismiss_focus(e, self.dlg))
        self.dlg.wait_window()

    def _ok(self):
        try:
            val = int(self._var.get())
            if 15 <= val <= 480:
                topic = self._topic_entry.get().strip()
                self.result = (val, topic)
                self.dlg.destroy()
        except ValueError:
            pass


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


class FolderDialog:
    """新建/重命名文件夹"""

    def __init__(self, parent, title_text, initial=""):
        self.result = None

        self.dlg = tk.Toplevel(parent)
        self.dlg.withdraw()
        self.dlg.update()
        self.dlg.title(title_text)
        self.dlg.resizable(False, False)
        self.dlg.transient(parent)
        self.dlg.grab_set()
        self.dlg.configure(bg=_C["bg"])

        card = tk.Frame(self.dlg, bg=_C["card"], padx=16, pady=14)
        card.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(card, text=title_text, font=(FTK, 13, "bold"),
                 fg=_C["pri"], bg=_C["card"]).pack(anchor="w", pady=(0, 10))

        tk.Label(card, text="名称", font=(FTK, 10),
                 fg=_C["sec"], bg=_C["card"]).pack(anchor="w")
        self._entry_wrap, self._entry = _rounded_entry(card, (FTK, 11))
        self._entry_wrap.pack(fill=tk.X, pady=(2, 12))
        if initial:
            self._entry.insert(0, initial)

        btn_row = tk.Frame(card, bg=_C["card"])
        btn_row.pack(fill=tk.X)
        _canvas_btn(btn_row, "确定", self._ok, w=70).pack(side=tk.LEFT, padx=(0, 6))
        _canvas_btn(btn_row, "取消", self.dlg.destroy, w=70).pack(side=tk.LEFT)

        w = max(320, self.dlg.winfo_reqwidth())
        h = max(200, self.dlg.winfo_reqheight())
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.dlg.geometry(f"{w}x{h}+{px}+{py}")
        self.dlg.deiconify()

        self._entry.focus_set()
        self.dlg.bind("<Button-1>", lambda e: _dismiss_focus(e, self.dlg))
        self.dlg.wait_window()

    def _ok(self):
        name = self._entry.get().strip()
        if name:
            self.result = name
            self.dlg.destroy()
