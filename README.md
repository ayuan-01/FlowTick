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
- **番茄钟** — 专注 / 休息倒计时，专注结束后自动切换休息模式
- **专注事项** — 设置专注时可填写本次要做的事情，倒计时过程中持续显示
- **图标控制** — ⏱ 设置时长、▶/⏸ 开始暂停切换、↺ 重置、📊 统计面板
- **事件记录** — 卡片式布局，支持标题 + 内容，带时间戳，双击编辑，右侧 × 按钮删除，右键菜单删除
- **历史统计** — 按天统计专注次数、分钟数和专注事项，可回溯每日记录
- **系统托盘** — 关闭窗口最小化到系统托盘，后台计时不中断，托盘菜单恢复或退出
- **圆角 UI** — 圆角卡片、柔和阴影、Noto Sans SC 统一字体，界面简洁现代

## 截图

![image-20260504173813705](https://cdn.jsdelivr.net/gh/ayuan-01/image-bed/fig/image-20260504173813705.png)

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
├── main.py          # 程序入口
├── app.py           # 主窗口 UI 及交互逻辑
├── timer.py         # 倒计时状态机
├── config.py        # 配置常量
├── events.json      # 事件记录数据（自动生成）
├── stats.json       # 专注统计数据（自动生成）
└── requirements.txt # 依赖
```

## 技术栈

- **Python 3** + **tkinter** — 零运行时依赖，Python 内置 GUI
- **pystray** + **Pillow** — 系统托盘图标
- **PyInstaller** — 打包为单文件 exe

## License

[MIT](LICENSE)
