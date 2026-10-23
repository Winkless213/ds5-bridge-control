# DS5 Bridge Control / DSE Control

Windows 桌面控制台：DualSense Edge（DSE）+ 谷粒 悟空2 无线接收器，以及官方 DS5Dongle（Pico2W DualSense Bridge）的配置与状态工具。

## 已实现

- **电量**：实时显示电量百分比、充电状态，数据来自标准 DualSense 输入报文 0x01。
- **震动**：左右马达独立强度滑块、轻/中/强/最大预设、1 秒测试、按住持续震动。
- **背键映射检测**：两步向导（按左背键 → 按右背键），记录接收器最终上报的按键组合，结果保存到本地配置。
- **接收器设置引导**：把震动强度、左右摇杆、左右扳机、设置键的组合键做成分步引导；一键打开，自动识别按下的组合键，并记录你确认过的档位。
- **设备信息**：接收器枚举出的型号、固件构建日期、MAC、VID/PID。
- **扬声器诊断**：显示 Windows 音频端点结论，提供 1kHz 提示音测试和音量写入。
- **实时输入**：双摇杆、L2/R2、当前按键。

## 重要边界

1. **只读监测**：程序不会向接收器写入厂商配置，不会改动手柄/接收器里已有的组合键。
2. **背键映射来源**：接收器会把背键转换成普通按键后再上报，DSE 原始背键位不会出现在 HID 报文里。因此程序用“检测向导”还原当前生效的映射，而不是直接读取接收器 flash。
3. **扬声器**：Windows 已枚举 `扬声器 (DualSense Edge Wireless Controller)` 端点（4ch/48kHz）。首轮测试漏发 `audio_control`，结论作废；复测已发送内部扬声器路由（`audio_control=0x03`）、音量 `0x64`、预放 `+6dB`（`audio_control2=0x02`），用户握持时仍然无声，同一轮震动正常。结论：该接收器只转发触觉声道，不转发扬声器声道。
4. **接收器内置调节**：接收器支持原生组合键调节，但没有主机侧配置写入接口；程序在“接收器”页把组合键做成引导，自动识别按键并记录用户确认的档位，不会伪造“一键写入成功”。当前档位主机读不到，换手柄/重置后需要重新引导。这页主要给 DS5 用；DSE 在 PlayStation Accessories 里已有按键/摇杆/扳机/档位设置，接收器再调会叠加，建议 DSE 优先用官方应用。

## 运行

源码运行（Python 3.14，依赖见 `requirements.txt`）：

```bat
pip install -r requirements.txt
python app.py
```

打包版：`dist\DSE Control\DSE Control.exe`。

## DS5 Bridge 控制台（独立应用）

针对官方 DS5Dongle（Pico2W DualSense Bridge）的桌面端，不走网页、不依赖网络，直接通过 HID Feature Report 读写官方 config v5（v0.7.2 / v0.7.2-hotfix，19 字节）。协议保留网页版全部配置字段：触觉增益、扬声器/耳机音量、扬声器增益、扳机反馈削减、音频缓冲、闲置断开、Pico LED、麦克风/扬声器禁用、USB 唤醒、轮询率、控制器模式、USB 序列号、PS 键快捷。音量字段仍会原样读写，但 v0.7.2 官方已改为系统音量控制，界面不再显示两个滑杆。

源码运行（QML 界面）：

```bat
python ds5_qml_app.py
```

旧版 QWidget 界面保留作回退：

```bat
python ds5_app.py
```

打包：

```bat
python -m PyInstaller "DS5 Bridge Control.spec" --noconfirm
```

输出：`dist\DS5 Bridge Control\DS5 Bridge Control.exe`。UI 截图在 `output/frontend-qa/ds5-qml-*.png`。

界面使用 Qt Quick / QML 重做：顶部导航 + 双栏卡片布局，窗口 1080–1280 宽都能保持结构；展开/收起只改变卡片高度，内容固定高度由卡片裁切，实测同一行文字在动画全程坐标不变。动效只服务状态反馈：页面切换 200ms 淡入 + 8px 上移，卡片展开 280ms `OutCubic`，箭头 220ms 旋转，Tab 指示条 240ms 滑动，滑块手柄/开关旋钮有短促缩放；没有循环、弹跳或自动播放。Windows 下使用 GDI ClearType 字体渲染，避免 DirectWrite 灰阶抗锯齿让中文发虚。顶部状态条实时显示连接、固件与电量，电量来自标准 DualSense 0x01 输入报文，约每秒刷新一次。

“设备”页新增输入回报率卡片：只在设备页打开时用独立 HID 句柄读取 0x01 输入报文，按 2 秒窗口统计报告率、p99 间隔和 p99−p50 抖动，并保留最近 10 秒曲线。它测量的是电脑实际收到的 USB 报告，不是手柄内部蓝牙帧率；不新增依赖，也不干扰配置读取和电池监控。实时档当前实测约 721–780 Hz，p99 约 2.1–3.0 ms。日常建议用 500 Hz：稳定在约 2 ms；实时档平均间隔更低，但 p99 抖动更大，只适合对比。

窗口关闭后会隐藏到系统托盘，程序继续在后台保持连接；托盘菜单提供“显示控制台”“重新检测/读取接收器”和“退出”，双击托盘图标也能恢复窗口。首次隐藏会弹出一次提示，避免误以为程序已退出。托盘不可用时退回普通的关闭即退出行为；截图模式不创建托盘。隐藏或最小化时回报率采集会自动停止，恢复窗口后按当前页重新开始。

“电源与指示灯 → 闲置自动断开”设为“关闭”后，接收器不会因为闲置主动断开车柄；手柄自身固件的省电行为仍由手柄决定，主机侧无法强制覆盖。

操作只有“保存更改”一个主入口：一次完成写入接收器、写入断电保留的存储，以及必要时的自动重连。轮询率、控制器模式、设备身份、USB 唤醒等影响 USB 识别的设置会自动重连；音量、触觉等设置立即生效。只有自动重连失败时，才需要到“设备”页手动点“重连 USB”。协议只支持官方 19 字节布局，不兼容 fork 的 30 字节布局。

与 Sony `PlayStation Accessories` 共存：本程序只向接收器发送配置 HID Feature Report，不修改手柄配置文件、不安装驱动、不写入 Sony 安装目录；已实测在官方应用运行时同时读取和保存配置。切换“手柄识别方式 / 固定设备身份 / USB 唤醒”会触发约 1 秒的重连，官方应用会短暂掉线后自动恢复。

## 测试

```bat
python -m pytest tests -q
```

UI 截图在 `output/frontend-qa/`。

## 真机验证（2026-10-21）

- 电量：DSE 经接收器上报 95%，充电中；25 分钟内从 75% 升到 95%，数值随时间变化。
- 震动：左 100 / 右 100 / 双 160 / 双 60 四段，用户确认全部清楚。
- 背键映射向导：用户按提示操作，程序记录 左=L3、右=圆圈，写入 `%APPDATA%\DSEControl\config.json`。
- 扬声器：修正 `audio_control` 后复测，用户握持时仍无声；震动同轮正常。

## QML 界面验证（2026-10-22）

- 源版与打包版都生成了 `output/frontend-qa/ds5-qml-*.png`（配置、设备、关于、收起、紧凑宽度、展开控件、弹窗、Toast）。
- 展开/收起稳定性：以“声音增益”行标题为基准，动画全程窗口坐标 `y=506.00`，`delta=0.00`；卡片高度 `84 → 328 → 84`。
- 保存回读：声音缓冲 `64 → 65 →（恢复）64`，`inactive_time` 由 `30` 改为 `0` 后回读确认；当前接收器不会因闲置主动断开车柄。
- 打包版 Qt Quick 依赖正常，裁剪 WebEngine/Quick3D/Pdf 二进制后约 188 MB。
- 输入回报率：设备页实时显示 721–780 Hz、p99 2.1–3.0 ms；图表与数值在源版/打包版均正常。

## 逆向记录

对接收器固件 `NS36_v3.7.bin` 做了 Ghidra / REA 分析（载荷 0x1000 起，基址 0x10000000，ARM Cortex-M Thumb）：

- 控制器配置块：`global + 0x38`，0x54 字节，`FUN_1000a628` 分支处理保存/打印。
- 映射/学习配置：0x1c 字节，保存到 flash `0x7b000`，结构包含 auto key、study、mode mask；`FUN_1000bacc` 负责写入。
- 接收器侧配置：`global + 0x8c` 起，包含 `rumble_sens`、`joys_sens_l/r`、`l2_sens`、`r2_sens`。
- 找到 USB 控制请求分发 `FUN_1001a894`（HID GET_REPORT/GET_IDLE/GET_PROTOCOL 路径），未发现可直接读写上述配置块的厂商 HID 命令。
- HID 报告描述符只有标准 DualSense 输入 0x01、输出 0x02 和特性报文；PnP 只枚举出 MI_00 音频与 MI_03 HID，没有厂商配置接口。官方固件说明中这些档位同样只由手柄组合键触发。

结论：映射的“最终生效结果”可以通过只读方式检测；接收器档位只能通过手柄组合键写入，主机侧做不了真正的一键写入。程序提供引导和本地记录，不冒写 flash 的风险。

## 文件

```
app.py                 入口
ds5_qml_app.py         DS5 Bridge QML 入口
ds5_bridge/qml_bridge.py  QML 视图模型（连接/电量/草稿配置）
ds5_bridge/qml/        QML 页面与组件
ds5_bridge/theme.py    深色主题 token
ds5_bridge/service.py  后台 HID 任务与电量线程
ds5_bridge/tray.py     系统托盘：关闭到托盘、菜单与退出
ds5_bridge/protocol.py DS5Dongle HID 协议
dse_panel/protocol.py  HID 报文解析/构造
dse_panel/device.py    后台读取/写入线程
dse_panel/mapping.py   映射检测
dse_panel/config.py    本地配置
dse_panel/ui.py        Fluent 界面
tests/                 单元测试
tools/screenshot.py    UI 截图脚本
tools/screenshot_receiver_coach.py  接收器引导/弹窗截图脚本
```

## 许可证与免责声明

本项目采用 GNU General Public License v3.0，详见根目录 [`LICENSE`](LICENSE)。Copyright (C) 2026 Winkless213 and contributors。

第三方依赖、传递依赖及参考项目的许可证见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。

本项目与 Sony Interactive Entertainment 无关联。“PlayStation”“DualSense”“DualSense Edge”是 Sony Interactive Entertainment Inc. 的商标。仓库不包含 Sony 固件、PlayStation 系统软件、官方驱动或 DualSense/DualSense Edge 的专有二进制资源；接收器协议和逆向记录仅用于互操作性研究。

