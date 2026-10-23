# 接收器协议与逆向记录

本文记录 DS5Dongle 接收器的只读协议观察和逆向结论，仅用于互操作性研究。
仓库不包含 Sony 固件、PlayStation 系统软件、官方驱动或 DualSense/DualSense Edge 的专有二进制资源。

## 官方 config v5

DS5 Bridge 控制台通过 HID Feature Report 读写官方 config v5（v0.7.2 / v0.7.2-hotfix，19 字节），字段包括触觉增益、扬声器/耳机音量、扬声器增益、扳机反馈削减、音频缓冲、闲置断开、Pico LED、麦克风/扬声器禁用、USB 唤醒、轮询率、控制器模式、USB 序列号和 PS 键快捷。

协议只支持官方 19 字节布局，不兼容 fork 的 30 字节布局。

## 固件分析

对接收器固件 `NS36_v3.7.bin` 做了 Ghidra / REA 分析（载荷 `0x1000` 起，基址 `0x10000000`，ARM Cortex-M Thumb）：

- 控制器配置块：`global + 0x38`，`0x54` 字节，`FUN_1000a628` 分支处理保存/打印。
- 映射/学习配置：`0x1c` 字节，保存到 flash `0x7b000`，结构包含 auto key、study、mode mask；`FUN_1000bacc` 负责写入。
- 接收器侧配置：`global + 0x8c` 起，包含 `rumble_sens`、`joys_sens_l/r`、`l2_sens`、`r2_sens`。
- USB 控制请求分发位于 `FUN_1001a894`（HID GET_REPORT/GET_IDLE/GET_PROTOCOL 路径）；未发现可直接读写上述配置块的厂商 HID 命令。
- HID 报告描述符只有标准 DualSense 输入 `0x01`、输出 `0x02` 和特性报文；PnP 只枚举出 MI_00 音频与 MI_03 HID，没有厂商配置接口。

## 结论

- 映射的“最终生效结果”可以通过只读方式检测；接收器档位只能通过手柄组合键写入，主机侧做不了真正的一键写入。
- 程序提供引导和本地记录，不冒写 flash 的风险。
- 接收器只转发触觉声道，不转发扬声器声道；Windows 虽枚举了音频端点，但握持实测仍无声。
