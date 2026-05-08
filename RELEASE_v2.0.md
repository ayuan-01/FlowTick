# FlowTick V2.0

V2.0 在 V1.0 基础上全面升级，新增会话模式、笔记文件夹、统计增强等核心功能。

## 新增功能

- **会话模式番茄钟** — 设置总专注时长，自动按节奏切换专注 / 短休息 / 长休息
- **自定义节奏参数** — 专注时长、短休息、长休息、长休息间隔均可独立配置
- **专注事项** — 设置时长时填写事项，自动记录到事件
- **笔记文件夹** — 创建文件夹归类笔记，左侧面板切换筛选，右键重命名 / 删除
- **连续打卡** — 统计页显示连续专注天数
- **本周柱状图** — 统计页可视化本周每日专注时长
- **按周分组** — 专注记录按 ISO 周分组，周汇总一目了然
- **逐条管理** — 统计页展示每条专注记录，支持逐条删除

## 改进

- 对话框输入框升级为圆角风格，整体视觉统一
- 用户数据存储迁移至 %APPDATA%\FlowTick\，与程序分离
- 浅灰侧边栏配色，质感提升
- 点击外部区域自动取消输入框焦点

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
pyinstaller --onefile --windowed --name FlowTick main.py
```

生成的可执行文件位于 `dist/FlowTick.exe`。
