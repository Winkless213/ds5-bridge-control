"""DualSense / DualSense Edge USB HID 协议的最小实现。

报文布局参考 Linux hid-playstation 驱动：
- 输入报文 0x01：64 字节（含 Report ID），payload 与 struct dualsense_input_report 对齐
- 输出报文 0x02：64 字节（含 Report ID），payload 与 struct dualsense_output_report_common 对齐
- 特性报文 0x09：配对信息（MAC），0x20：固件信息
"""

from __future__ import annotations

import re
from dataclasses import dataclass

INPUT_REPORT_ID = 0x01
OUTPUT_REPORT_ID = 0x02
FEATURE_PAIRING = 0x09
FEATURE_FIRMWARE = 0x20

BATTERY_STATUS_NAMES = {
    0x0: "放电中",
    0x1: "充电中",
    0x2: "已充满",
    0xA: "电压/温度异常",
    0xB: "温度异常",
    0xF: "充电错误",
}

BUTTON_NAMES_0 = {
    0x10: "方块",
    0x20: "叉",
    0x40: "圆圈",
    0x80: "三角",
}
BUTTON_NAMES_1 = {
    0x01: "L1",
    0x02: "R1",
    0x04: "L2",
    0x08: "R2",
    0x10: "Create",
    0x20: "Options",
    0x40: "L3",
    0x80: "R3",
}
BUTTON_NAMES_2 = {
    0x01: "PS",
    0x02: "触摸板",
    0x04: "静音",
    0x10: "FN1",
    0x20: "FN2",
    0x40: "左背键",
    0x80: "右背键",
}

# 交叉/圆圈等按键在 UI 层的显示名与手感对应关系保持原样，不做 Xbox 映射。
HAT_NAMES = {
    0: "↑", 1: "↗", 2: "→", 3: "↘", 4: "↓", 5: "↙", 6: "←", 7: "↖", 8: "",
}


def names_from_buttons(buttons: tuple[int, int, int, int]) -> list[str]:
    names: list[str] = []
    hat = buttons[0] & 0x0F
    if hat in HAT_NAMES and HAT_NAMES[hat]:
        names.append(HAT_NAMES[hat])
    for mask, name in BUTTON_NAMES_0.items():
        if buttons[0] & mask:
            names.append(name)
    for mask, name in BUTTON_NAMES_1.items():
        if buttons[1] & mask:
            names.append(name)
    for mask, name in BUTTON_NAMES_2.items():
        if buttons[2] & mask:
            names.append(name)
    return names


@dataclass(frozen=True)
class InputState:
    report: bytes
    lx: int
    ly: int
    rx: int
    ry: int
    l2: int
    r2: int
    seq: int
    buttons: tuple[int, int, int, int]
    battery_raw: int

    @property
    def battery_level(self) -> int:
        return self.battery_raw & 0x0F

    @property
    def battery_status(self) -> int:
        return (self.battery_raw >> 4) & 0x0F

    @property
    def battery_percent(self) -> int:
        if self.battery_status == 0x2:
            return 100
        if self.battery_status in (0xA, 0xB, 0xF):
            return 0
        return min(self.battery_level * 10 + 5, 100)

    @property
    def charging_text(self) -> str:
        return BATTERY_STATUS_NAMES.get(self.battery_status, f"未知(0x{self.battery_status:X})")

    @property
    def is_charging(self) -> bool:
        return self.battery_status == 0x1

    @property
    def edge_bits(self) -> int:
        """DSE 原始背键/Fn 位：bit4 FN1, bit5 FN2, bit6 左背键, bit7 右背键。"""
        return self.buttons[2] & 0xF0

    @property
    def hat(self) -> int:
        return self.buttons[0] & 0x0F

    @property
    def pressed_names(self) -> list[str]:
        return names_from_buttons(self.buttons)

    @property
    def is_idle(self) -> bool:
        return (
            self.buttons[0] == 0x08
            and self.buttons[1] == 0
            and self.buttons[2] == 0
            and self.l2 == 0
            and self.r2 == 0
        )

    def button_mask(self) -> tuple[int, int, int, int]:
        return self.buttons


def parse_input_report(data: bytes | bytearray | list[int]) -> InputState | None:
    """解析 USB 输入报文 0x01；非 0x01 或长度不足时返回 None。"""
    raw = bytes(data)
    if len(raw) < 64 or raw[0] != INPUT_REPORT_ID:
        return None
    return InputState(
        report=raw,
        lx=raw[1],
        ly=raw[2],
        rx=raw[3],
        ry=raw[4],
        l2=raw[5],
        r2=raw[6],
        seq=raw[7],
        buttons=(raw[8], raw[9], raw[10], raw[11]),
        battery_raw=raw[53],
    )


def build_output_report(
    weak: int = 0,
    strong: int = 0,
    *,
    lightbar: tuple[int, int, int] | None = None,
    player_leds: int | None = None,
    speaker_volume: int | None = None,
    audio_control: int | None = None,
    audio_control2: int | None = None,
    haptics: bool = True,
) -> bytes:
    """构造 USB 输出报文 0x02。

    weak 对应右马达，strong 对应左马达，取值 0-255。
    speaker_volume / audio_control / audio_control2 用于内部扬声器通路；
    DualSense 的扬声器音量有效范围约 0x3d-0x64，audio_control=0x03 表示
    把右声道路由到内部扬声器。
    """
    buf = bytearray(64)
    buf[0] = OUTPUT_REPORT_ID
    if haptics:
        buf[1] = 0x03  # COMPATIBLE_VIBRATION | HAPTICS_SELECT
    buf[3] = max(0, min(255, int(weak)))
    buf[4] = max(0, min(255, int(strong)))

    if speaker_volume is not None:
        buf[1] |= 0x20  # SPEAKER_VOLUME_ENABLE
        buf[6] = max(0, min(255, int(speaker_volume)))

    if audio_control is not None:
        buf[1] |= 0x80  # AUDIO_CONTROL_ENABLE
        buf[8] = audio_control & 0xFF

    if audio_control2 is not None:
        buf[2] |= 0x80  # AUDIO_CONTROL2_ENABLE
        buf[38] = audio_control2 & 0xFF

    if lightbar is not None:
        r, g, b = (max(0, min(255, int(v))) for v in lightbar)
        buf[2] |= 0x04  # LIGHTBAR_CONTROL_ENABLE
        buf[45] = r
        buf[46] = g
        buf[47] = b

    if player_leds is not None:
        buf[2] |= 0x10  # PLAYER_INDICATOR_CONTROL_ENABLE
        buf[44] = player_leds & 0x1F

    return bytes(buf)


def parse_firmware_info(data: bytes | bytearray | list[int]) -> dict[str, object]:
    """解析特性报文 0x20：前 20 字节为构建日期，24/28 为版本号。"""
    raw = bytes(data)
    if len(raw) < 32 or raw[0] != FEATURE_FIRMWARE:
        return {}
    build_bytes = bytes(b for b in raw[1:21] if 0x20 <= b < 0x7F)
    build = build_bytes.decode("ascii", "replace").strip()
    # 固件里是 "Jul  4 202510:38:40" 这种紧凑格式，给年份和时间补一个空格。
    build = re.sub(r"(20\d{2})(\d{2}:\d{2}:\d{2})", r"\1 \2", build)
    return {
        "build": build,
        "hw_version": int.from_bytes(raw[24:28], "little"),
        "fw_version": int.from_bytes(raw[28:32], "little"),
    }


def parse_pairing_info(data: bytes | bytearray | list[int]) -> str:
    """解析特性报文 0x09 的 6 字节 MAC（小端）。"""
    raw = bytes(data)
    if len(raw) < 7 or raw[0] != FEATURE_PAIRING:
        return ""
    return ":".join(f"{b:02X}" for b in reversed(raw[1:7]))


def edge_pressed_names(edge_bits: int) -> list[str]:
    return [name for mask, name in BUTTON_NAMES_2.items() if edge_bits & mask]


def format_battery(percent: int, status: str) -> str:
    return f"{percent}% · {status}"
