# FlowTick V2.0

<div align="center">
<img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/tkinter-builtin-green?logo=python&logoColor=white" alt="tkinter">
<img src="https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white" alt="Windows">
<img src="https://img.shields.io/github/license/ayuan-01/FlowTick" alt="License">
<img src="https://img.shields.io/github/v/release/ayuan-01/FlowTick" alt="Release">
</div>

**一个简洁美观的 Windows 桌面番茄钟应用**

专注于时间管理，帮助你高效工作与休息

[下载最新版](https://github.com/ayuan-01/FlowTick/releases/latest) · [报告问题](https://github.com/ayuan-01/FlowTick/issues)

---

## 功能特性

- **会话模式番茄钟** — 设置总专注时长，自动按节奏切换专注 / 短休息 / 长休息，无需手动干预
- **自定义节奏** — 专注时长、短休息、长休息、长休息间隔均可独立配置
- **专注事项** — 设置时长时填写本次要做的事情，事件自动记录事项名称
- **左侧导航** — 首页 / 事件 / 笔记 / 待办 / 统计 / 设置，选中态窄线指示器，页面内切换无弹窗
- **模拟时钟** — 实时时钟显示，带时针、分针、秒针，下方同步显示数字时间
- **图标控制** — ▶/⏸ 开始暂停切换、↺ 重置
- **鼠标悬停提示** — 悬停按钮显示功能说明和快捷键
- **事件** — 专注结束后自动记录，显示时间 / 事项 / 时长，支持搜索过滤、删除
- **笔记** — 手动添加笔记，支持标题 + 内容，双击编辑，右键菜单删除，支持搜索过滤
- **笔记文件夹** — 创建文件夹归类笔记，左侧面板切换筛选，右键重命名 / 删除
- **待办事项** — 带复选框，勾选后划线并记录完成时间，自动排序（未完成优先），支持一键清除已完成
- **历史统计** — 总体 / 本周 / 本月汇总，连续打卡天数，本周每日柱状图，按 ISO 周分组查看专注记录
- **逐条管理** — 统计页展示每条专注记录，支持逐条删除
- **数据导出** — 一键导出专注统计为 CSV 文件，方便外部分析
- **设置面板** — 声音提醒、窗口置顶、关闭时最小化到托盘、休息后自动开始、长休息配置、每日目标、闲置检测
- **闲置检测** — 超过设定时间无鼠标键盘操作自动暂停计时器，专注数据更真实
- **每日目标** — 设定每日番茄目标，实时显示完成进度（如"专注 3/8"）
- **系统托盘** — 关闭窗口最小化到系统托盘，后台计时不中断，托盘图标实时显示倒计时，托盘菜单恢复或退出
- **Windows 通知** — 专注结束和休息结束时弹出系统原生通知，即使最小化到托盘也不会错过
- **单实例** — 程序运行时再次打开会提示已在运行
- **键盘快捷键** — 空格（开始/暂停）、R（重置）、N（添加笔记）
- **休息提醒** — 专注结束弹出遮罩提醒休息，按回车或点击关闭
- **圆角 UI** — 圆角卡片、圆角输入框、柔和阴影、Noto Sans SC 统一字体，界面简洁现代

## 截图

![image-20260508113514126](https://cdn.jsdelivr.net/gh/ayuan-01/image-bed/fig/image-20260508113514126.png)

## 快速开始

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

## 项目结构

```
FlowTick/
├── main.py          # 程序入口，单实例检测（TCP 端口绑定）
├── app.py           # 主窗口 UI、侧边栏导航、系统托盘、闲置检测
├── timer.py         # 会话模式倒计时状态机，预计算专注/休息 segments
├── config.py        # 配置常量、颜色、默认设置
├── dialogs.py       # 对话框（专注设置、笔记、文件夹、休息提醒）
├── widgets.py       # 圆角 UI 组件（按钮、输入框、侧边栏按钮、Windows 通知）
├── fig/             # Logo 和截图
└── %APPDATA%\FlowTick\   # 用户数据（运行时自动生成）
    ├── events.json       # 专注事件记录
    ├── notes.json        # 笔记数据
    ├── stats.json        # 专注统计
    ├── settings.json     # 用户设置
    ├── todos.json        # 待办数据
    └── folders.json      # 笔记文件夹
```

## 技术栈

- **Python 3** + **tkinter** — 零运行时依赖，Python 内置 GUI
- **pystray** + **Pillow** — 系统托盘图标
- **ctypes** — 闲置检测（GetLastInputInfo）、Windows 原生通知（Shell_NotifyIconW）
- **PyInstaller** — 打包为单文件 exe

## 更新日志

### V2.0

详见 [RELEASE_v2.0.md](RELEASE_v2.0.md)

- 新增会话模式：设置总专注时长，自动按节奏切换专注 / 休息
- 新增自定义节奏参数：专注时长、短休息、长休息、长休息间隔均可配置
- 新增专注事项：设置时长时填写事项，自动记录到事件
- 新增笔记文件夹：创建文件夹归类笔记，支持筛选和管理
- 统计升级：连续打卡、本周柱状图、按周分组、逐条删除专注记录
- 对话框升级：圆角输入框，风格统一
- 数据存储迁移至 %APPDATA%\FlowTick\，与程序分离
- 浅灰侧边栏配色升级
- 交互优化：点击外部区域取消输入框焦点

### V1.0

- 首个正式版本，详见 [RELEASE_v1.0.md](RELEASE_v1.0.md)

## License

[MIT](LICENSE)
