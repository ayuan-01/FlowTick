# FlowTick v1.0

第一个正式版本，一个简洁美观的 Windows 桌面番茄钟应用。

## 功能亮点

- **模拟时钟** — 实时时钟显示，带时针、分针、秒针，下方同步显示数字时间
- **番茄钟** — 专注 / 短休息 / 长休息倒计时，专注结束后自动切换休息模式
- **左侧导航** — 首页 / 事件 / 笔记 / 待办 / 统计 / 设置，选中态窄线指示器，页面内切换无弹窗
- **待办事项** — 带复选框，勾选后划线并记录完成时间，自动排序，支持一键清除已完成
- **事件与笔记** — 专注自动记录，笔记手动添加，支持搜索过滤、双击编辑、右键删除
- **历史统计** — 总体 / 本周 / 本月汇总，按天查看专注详情，支持导出 CSV
- **系统托盘** — 关闭窗口最小化到托盘，后台计时不中断，托盘图标实时显示倒计时
- **Windows 通知** — 专注结束和休息结束时弹出系统原生通知，即使最小化到托盘也不会错过
- **闲置检测** — 超过设定时间无操作自动暂停计时器
- **设置面板** — 声音提醒、窗口置顶、自动开始、长休息配置、每日目标等

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
