# 第三方组件与许可证

本项目整体按 GNU General Public License v3.0 发布，详见根目录 `LICENSE`。
以下列出主要运行时依赖和参考项目；完整许可证文本以各上游项目为准。

| 组件 | 版本 | 许可证 | 用途 / 链接 |
| --- | --- | --- | --- |
| PySide6 | 6.12.0 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | Qt/QML 运行时；https://pypi.org/project/PySide6/ |
| PySide6-Fluent-Widgets | 1.11.3 | GPL-3.0 | 旧版 QWidget 界面的控件库；https://github.com/zhiyiYo/PyQt-Fluent-Widgets/tree/PySide6 |
| PySideSix-Frameless-Window | 0.8.2 | LGPL-3.0 | Fluent Widgets 的传递依赖；https://pypi.org/project/PySideSix-Frameless-Window/ |
| hidapi (cython-hidapi) | 0.15.0 | GPL-3.0 / BSD-3-Clause / 原 cython-hidapi 许可证三选一 | HID 访问；本项目按 GPL-3.0 使用；https://github.com/trezor/cython-hidapi |
| numpy | 2.5.4 | BSD-3-Clause（另含 0BSD、MIT、Zlib、CC0-1.0 组件） | 数值计算；https://numpy.org/ |
| sounddevice | 0.5.6 | MIT | 音频诊断；https://python-sounddevice.readthedocs.io/ |
| darkdetect | 0.8.0 | BSD-3-Clause | Fluent Widgets 的传递依赖；https://pypi.org/project/darkdetect/ |
| PyInstaller | 6.22.3 | GPL-2.0-or-later，含打包分发例外 | 构建 Windows 可执行文件；https://pyinstaller.org/ |
| DS5Dongle | 官方固件 / 协议参考 | MIT | 硬件协议与配置格式参考；https://github.com/awalol/DS5Dongle |

## 说明

- 本项目不包含 Sony 固件、PlayStation 系统软件、Sony 官方驱动或 DualSense/DualSense Edge 的专有二进制资源。
- “PlayStation”“DualSense”“DualSense Edge”是 Sony Interactive Entertainment Inc. 的商标；本项目与 Sony 无关联。
- `work/DS5DongleTray` 是第三方 MIT 参考项目，不随本仓库发布。
- 如果修改依赖版本或引入新库，请同步更新本文件。
