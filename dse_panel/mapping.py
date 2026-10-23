"""背键映射检测。

接收器（GuliKit 悟空2）会把背键转换成普通按键后再上报，原始 DSE 背键位不会出现在
HID 报文里，因此只能用“请用户按一次背键，读取最终上报的按键组合”的方式推断当前映射。
整个过程只读，不写任何设备配置。
"""

from __future__ import annotations

from .protocol import InputState, names_from_buttons

SIDE_NAMES = {"left": "左背键", "right": "右背键"}
ARROWS = {"↑", "↗", "→", "↘", "↓", "↙", "←", "↖"}


def mask_names(buttons: tuple[int, int, int, int]) -> list[str]:
    """把按键掩码转成名称，排除方向帽方向（映射结果通常是普通按键组合）。"""
    return [n for n in names_from_buttons(buttons) if n not in ARROWS]


def describe_buttons(buttons: tuple[int, int, int, int]) -> str:
    names = mask_names(buttons)
    return " + ".join(names) if names else "无按键"


def describe(state: InputState) -> str:
    return describe_buttons(state.buttons)


def union_buttons(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    return (a[0] | b[0], a[1] | b[1], a[2] | b[2], a[3] | b[3])


def is_press(state: InputState, baseline: InputState | None) -> bool:
    """相对基线出现新按键、或方向帽离开中位，视为一次按压。"""
    if baseline is None:
        return not state.is_idle
    return state.button_mask() != baseline.button_mask() and not state.is_idle
