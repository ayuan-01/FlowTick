# FlowTick

一个基于 Python + tkinter 的 Windows 桌面番茄钟应用，支持专注倒计时和事件记录。

## 功能

- **当前时间** — 实时显示，点击可切换显示秒
- **番茄钟** — 专注/休息倒计时，专注结束后自动切换到休息
- **控制按钮** — 设置时长、开始、暂停、重置
- **事件记录** — 添加带时间戳的笔记

## 运行

```bash
python main.py
```

## 打包

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name FlowTick main.py
```

生成的可执行文件在 `dist/FlowTick.exe`。

## 项目结构

```
main.py        # 程序入口
app.py         # 主窗口 UI
timer.py       # 倒计时逻辑
config.py      # 配置常量
```
