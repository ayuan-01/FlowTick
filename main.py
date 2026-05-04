import socket
import tkinter as tk
from tkinter import messagebox
from app import FlowTickApp

LOCK_PORT = 54321


def check_single_instance():
    """通过 TCP 端口绑定检测是否已有实例运行"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", LOCK_PORT))
        return sock
    except OSError:
        return None


def main():
    lock_sock = check_single_instance()
    if lock_sock is None:
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning("FlowTick", "程序已在运行中")
        root.destroy()
        return

    root = tk.Tk()
    FlowTickApp(root)
    root.mainloop()
    lock_sock.close()


if __name__ == "__main__":
    main()
