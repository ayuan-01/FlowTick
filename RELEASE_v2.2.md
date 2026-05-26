# FlowTick V2.2

V2.2 聚焦待办体验优化与多项 Bug 修复，提升稳定性和可用性。

## 改进

- **待办页面重构** — 文字占满整行不再截断，双击弹窗编辑（Enter 确认，Escape 取消），点击圆圈勾选/取消，交互更清晰
- **笔记时间格式统一** — 笔记时间从 `MM-DD HH:MM` 改为 `YYYY-MM-DD HH:MM`，与事件格式一致，解决跨年排序问题
- **托盘退出线程安全** — `_save_session` 包裹在 `root.after(0, ...)` 中，确保从 pystray 子线程退出时数据在主线程安全读取
- **Timer tick 异常保护** — `_tick` 方法改用 `try/finally`，即使回调抛异常也不会导致 `_tick_running` 卡死、计时器停摆
- **文件夹迁移补漏** — 旧路径迁移列表添加 `folders.json`，升级用户不再丢失文件夹数据
- **.gitignore 更新** — 添加 `session.json` 和 `folders.json`，运行时文件不再误提交

## 修复

- **修复计时器跳秒** — `_on_segment_change` 中 `auto_start_focus` 调用 `timer.start()` 重置会话并创建第二条 tick 链，导致每秒 -2。移除多余的 `start()` 调用
- **修复事件不自动记录** — 同一 bug 导致 `focus_accumulated` 被反复清零，永远到不了 `focus_total`，`on_session_end` 不触发
- **修复待办添加占位文字** — 输入框有 placeholder "添加待办..." 时直接点击加号，会创建名为"添加待办..."的条目。添加占位文字判断
- **修复待办双击编辑失焦不消失** — 内联 Entry 的 `<FocusOut>` 事件时序不稳定，改为模态弹窗编辑，彻底解决

## 安装

### 从源码运行

```bash
git clone https://github.com/ayuan-01/FlowTick.git
cd FlowTick
pip install pystray Pillow
python main.py
```

### 打包为 exe

```bash
pip install pyinstaller pystray Pillow
pyinstaller FlowTick.spec
```

生成的可执行文件位于 `dist/FlowTick.exe`。
