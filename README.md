# FlowTick

<div align="center">
<img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/tkinter-builtin-green?logo=python&logoColor=white" alt="tkinter">
<img src="https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows&logoColor=white" alt="Windows">
<img src="https://img.shields.io/github/license/ayuan-01/FlowTick" alt="License">
<img src="https://img.shields.io/github/v/release/ayuan-01/FlowTick" alt="Release">

**一个简洁美观的 Windows 桌面番茄钟应用**

专注于时间管理，帮助你高效工作与休息

[下载最新版](https://github.com/ayuan-01/FlowTick/releases/latest) · [报告问题](https://github.com/ayuan-01/FlowTick/issues)

---

## 功能特性

- **模拟时钟** — 实时时钟显示，带时针、分针、秒针，下方同步显示数字时间
- **番茄钟** — 专注 / 短休息倒计时，专注结束后自动切换休息模式
- **长休息** — 每完成 N 个番茄钟自动触发长休息（可配置间隔和时长）
- **专注事项** — 设置时长时可填写本次要做的事情，倒计时过程中持续显示
- **图标控制** — ⏱ 设置时长、▶/⏸ 开始暂停切换、↺ 重置、📊 统计面板、⚙ 设置
- **鼠标悬停提示** — 悬停按钮显示功能说明和快捷键
- **事件** — 专注结束后自动记录，显示时间 / 事项 / 时长，支持删除
- **笔记** — 手动添加笔记，支持标题 + 内容，双击编辑，右键菜单删除
- **历史统计** — 总体 / 本周 / 本月汇总，按天查看专注次数、分钟数和专注事项
- **数据导出** — 一键导出专注统计为 CSV 文件，方便外部分析
- **设置面板** — 声音提醒、窗口置顶、关闭时最小化到托盘、休息后自动开始、长休息配置、每日目标、闲置检测
- **闲置检测** — 超过设定时间无鼠标键盘操作自动暂停计时器，专注数据更真实
- **每日目标** — 设定每日番茄目标，实时显示完成进度（如"专注 3/8"）
- **系统托盘** — 关闭窗口最小化到系统托盘，后台计时不中断，托盘菜单恢复或退出
- **单实例** — 程序运行时再次打开会提示已在运行
- **键盘快捷键** — 空格（开始/暂停）、R（重置）、N（添加笔记）
- **休息提醒** — 专注结束弹出遮罩提醒休息，按回车或点击关闭
- **圆角 UI** — 圆角卡片、柔和阴影、Noto Sans SC 统一字体，界面简洁现代

## 截图

![image-20260505021541997](https://cdn.jsdelivr.net/gh/ayuan-01/image-bed/fig/image-20260505021541997.png)

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
pyinstaller --onefile --windowed --name FlowTick main.py
```

生成的可执行文件位于 `dist/FlowTick.exe`。

## 项目结构

```
FlowTick/
├── main.py          # 程序入口，单实例检测（TCP 端口绑定）
├── app.py           # 主窗口 UI、对话框、系统托盘、闲置检测
├── timer.py         # 倒计时状态机（IDLE/RUNNING/PAUSED）
├── config.py        # 配置常量、颜色、默认设置
├── events.json      # 专注事件记录（运行时自动生成）
├── notes.json       # 笔记数据（运行时自动生成）
├── stats.json       # 专注统计数据（运行时自动生成）
├── settings.json    # 用户设置（运行时自动生成）
└── requirements.txt # 依赖
```

## 技术栈

- **Python 3** + **tkinter** — 零运行时依赖，Python 内置 GUI
- **pystray** + **Pillow** — 系统托盘图标
- **PyInstaller** — 打包为单文件 exe

## License

[MIT](LICENSE)
