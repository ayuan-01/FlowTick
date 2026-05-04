# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## 项目概述

FlowTick 是一个 Windows 桌面番茄钟应用，基于 Python + tkinter，零外部运行时依赖。

## 常用命令

```bash
# 运行
python main.py

# 打包为 exe（需要 pyinstaller pystray Pillow）
pip install pyinstaller pystray Pillow
pyinstaller --onefile --windowed --name FlowTick main.py
# 输出: dist/FlowTick.exe
```

## 架构

单类 UI + 状态机定时器模式，无 MVC 框架。

```
main.py          → 入口，单实例检测（TCP 端口绑定），创建 Tk 根窗口
app.py           → FlowTickApp 主窗口类 + NoteDialog/TimeDialog/SettingsDialog + BreakOverlay
timer.py         → Timer 状态机（IDLE/RUNNING/PAUSED，FOCUS/BREAK 模式切换）
config.py        → 常量（时长默认值、窗口尺寸、颜色、默认设置）
events.json      → 运行时生成，自动记录专注事件
notes.json       → 运行时生成，手动笔记
stats.json       → 运行时生成，专注统计
settings.json    → 运行时生成，用户设置
```

**Timer 与 UI 解耦**：Timer 接受 `on_tick(remaining)` 和 `on_mode_change(mode)` 回调，app.py 负责绑定到 UI 更新。

**数据模型**：
- `events.json` — 每次专注结束后自动记录 `{time, topic, minutes}`，只读+删除
- `notes.json` — 手动添加的笔记 `{title, content, time}`，完整 CRUD
- `stats.json` — 按天统计专注次数、分钟数
- `settings.json` — 用户偏好设置，覆盖 config.py 中 DEFAULT_SETTINGS

## 关键实现模式

- **圆角矩形**：`_round_rect()` 用 `create_polygon(smooth=True)` 绘制
- **可滚动区域**：Canvas + Scrollbar + inner Frame，`<Configure>` 更新 scrollregion
- **文本截断**：`_truncate()` 用 `tkfont.Font.measure()` 计算像素宽度后加省略号
- **模态对话框**：`withdraw()` + `update()` + 定位 + `deiconify()` 避免闪烁
- **系统托盘**：`pystray` + `Pillow`，`threading.Thread(daemon=True)` 后台运行
- **长休息**：每 N 个番茄钟后自动触发长休息，通过 `BreakOverlay` 弹窗提示
- **键盘快捷键**：空格（开始/暂停）、r（重置）、n（添加笔记）

## 注意事项

- 用户界面文字全部为中文
- 窗口可自由缩放，事件/笔记卡片通过 `<Configure>` 事件动态重绘
- `import math` 放在 `_draw_analog_clock` 内部
- 底部 UI 分为两个模块："事件"（自动记录专注）和"笔记"（手动 CRUD）
