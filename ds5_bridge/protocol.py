# -*- coding: utf-8 -*-
"""DS5Dongle (Pico2W DualSense bridge) host protocol.

The receiver enumerates as a Sony DualSense / DualSense Edge gamepad and
exposes the bridge configuration through HID feature reports 0xF6..0xF9.
This module deliberately implements only the official config-v5 layout
(19-byte body, firmware v0.7.2): the fork-specific 30-byte layout is not
compatible and must not be mixed in.
"""
from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field
from typing import Any, Iterable

VID = 0x054C
PIDS = (0x0CE6, 0x0DF2)
USAGE_PAGE_GENERIC_DESKTOP = 0x01
USAGE_GAMEPAD = 0x05

REPORT_SET = 0xF6
REPORT_CONFIG = 0xF7
REPORT_VERSION = 0xF8
REPORT_STATUS = 0xF9
REPORT_INPUT = 0x01

# Standard DualSense USB input report: report id + 63-byte payload.
# Battery capacity/status share byte 53; see Linux hid-playstation.c.
BATTERY_BYTE = 53
BATTERY_NAMES = {
    0x00: "使用中",
    0x01: "充电中",
    0x02: "已充满",
    0x0A: "电压异常",
    0x0B: "温度异常",
    0x0F: "充电异常",
}

FUNC_UPDATE = 0x01
FUNC_SAVE = 0x02
FUNC_RECONNECT = 0x03

CONFIG_VERSION = 5
CONFIG_SIZE = 19
FEATURE_REPORT_LEN = 64
SET_DATA_LEN = 63
HID_SET_REPORT_DELAY = 0.05

# Order MUST match src/config.h Config_body in official firmware v0.7.2.
FIELD_ORDER: tuple[str, ...] = (
    "config_version",
    "haptics_gain",
    "speaker_volume",
    "headset_volume",
    "speaker_gain",
    "inactive_time",
    "disable_pico_led",
    "polling_rate_mode",
    "audio_buffer_length",
    "controller_mode",
    "enable_usb_sn",
    "ps_shortcut_enabled",
    "disable_mic",
    "disable_speaker",
    "enable_wake",
    "trigger_reduce",
)

BOOL_FIELDS = {
    "disable_pico_led",
    "enable_usb_sn",
    "ps_shortcut_enabled",
    "disable_mic",
    "disable_speaker",
    "enable_wake",
}

# These fields are read while the USB device enumerates. A running receiver
# keeps the old values until it is re-enumerated, so changing one requires a
# reconnect; audio and haptics fields apply immediately.
RECONNECT_KEYS: tuple[str, ...] = (
    "polling_rate_mode",
    "controller_mode",
    "enable_usb_sn",
    "ps_shortcut_enabled",
    "enable_wake",
)


def requires_reconnect(before: dict[str, Any] | None, after: dict[str, Any] | None) -> bool:
    if before is None or after is None:
        return False
    return any(before.get(key) != after.get(key) for key in RECONNECT_KEYS)

INT_RANGES: dict[str, tuple[int, int]] = {
    "speaker_volume": (0, 127),
    "headset_volume": (0, 127),
    "speaker_gain": (0, 7),
    "inactive_time": (0, 60),
    "polling_rate_mode": (0, 2),
    "audio_buffer_length": (16, 127),
    "controller_mode": (0, 2),
    "trigger_reduce": (0, 10),
}

DEFAULTS: dict[str, Any] = {
    "config_version": CONFIG_VERSION,
    "haptics_gain": 1.0,
    "speaker_volume": 100,
    "headset_volume": 100,
    "speaker_gain": 2,
    "inactive_time": 30,
    "disable_pico_led": False,
    "polling_rate_mode": 0,
    "audio_buffer_length": 64,
    "controller_mode": 2,
    "enable_usb_sn": False,
    "ps_shortcut_enabled": False,
    "disable_mic": False,
    "disable_speaker": False,
    "enable_wake": False,
    "trigger_reduce": 0,
}

# Little-endian, packed: version + float + 14 bytes.
CONFIG_STRUCT = struct.Struct("<Bf14B")


class Ds5Error(RuntimeError):
    """Base error shown directly in the UI."""


class DeviceNotFound(Ds5Error):
    pass


class ConfigReadError(Ds5Error):
    pass


class ConfigVersionError(Ds5Error):
    pass


@dataclass(slots=True)
class DeviceInfo:
    path: bytes
    product_id: int
    product: str
    serial: str = ""
    interface: int | None = None
    firmware: str = ""
    supported: bool = False
    error: str = ""

    @property
    def title(self) -> str:
        name = self.product or "DualSense"
        return f"{name} · {self.firmware}" if self.firmware else name

    @property
    def path_text(self) -> str:
        return self.path.decode("utf-8", "replace") if isinstance(self.path, bytes) else str(self.path)


def _clamp_int(value: Any, lo: int, hi: int) -> int:
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        number = lo
    return max(lo, min(hi, number))


def normalize_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a complete config with the same clamping rules as the web UI."""
    source = dict(DEFAULTS)
    if config:
        source.update({key: config[key] for key in FIELD_ORDER if key in config})

    out: dict[str, Any] = {"config_version": CONFIG_VERSION}
    try:
        gain = float(source.get("haptics_gain", 1.0))
    except (TypeError, ValueError):
        gain = 1.0
    out["haptics_gain"] = max(1.0, min(2.0, round(gain, 2)))

    for name, (lo, hi) in INT_RANGES.items():
        out[name] = _clamp_int(source.get(name, DEFAULTS[name]), lo, hi)

    for name in BOOL_FIELDS:
        out[name] = bool(source.get(name, DEFAULTS[name]))

    return out


def validate_config(config: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    try:
        gain = float(config.get("haptics_gain"))
    except (TypeError, ValueError):
        gain = float("nan")
    if not (1.0 <= gain <= 2.0):
        issues.append("haptics_gain")

    for name, (lo, hi) in INT_RANGES.items():
        value = config.get(name)
        if not isinstance(value, int) or not (lo <= value <= hi):
            issues.append(name)

    for name in BOOL_FIELDS:
        if not isinstance(config.get(name), bool):
            issues.append(name)
    return issues


def pack_config(config: dict[str, Any]) -> bytes:
    cfg = normalize_config(config)
    values: list[Any] = [CONFIG_VERSION, float(cfg["haptics_gain"])]
    for name in FIELD_ORDER[2:]:
        values.append(int(bool(cfg[name])) if name in BOOL_FIELDS else int(cfg[name]))
    return CONFIG_STRUCT.pack(*values)


def unpack_config(payload: bytes | bytearray | memoryview) -> dict[str, Any]:
    raw = bytes(payload)
    if not raw:
        raise ConfigReadError("设备返回了空的配置报文。")
    # WebHID returns the report ID as byte 0; hidapi may return the same.
    if raw[0] == REPORT_CONFIG and len(raw) >= CONFIG_SIZE + 1:
        body = raw[1 : 1 + CONFIG_SIZE]
    else:
        body = raw[:CONFIG_SIZE]
    if len(body) < CONFIG_SIZE:
        raise ConfigReadError(
            f"配置报文只有 {len(body)} 字节，期望 {CONFIG_SIZE} 字节；请确认固件为官方 v0.7.2。"
        )
    if body[0] != CONFIG_VERSION:
        raise ConfigVersionError(
            f"配置版本不匹配：网页/本程序支持 v{CONFIG_VERSION}，设备返回 v{body[0]}。"
        )
    values = CONFIG_STRUCT.unpack(body)
    cfg = dict(zip(FIELD_ORDER, values))
    for name in BOOL_FIELDS:
        cfg[name] = bool(cfg[name])
    cfg["config_version"] = int(cfg["config_version"])
    cfg["haptics_gain"] = round(float(cfg["haptics_gain"]), 2)
    return cfg


def configs_equal(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    if left is None or right is None:
        return left is right
    return pack_config(left) == pack_config(right)


def read_config(device: Any) -> dict[str, Any]:
    try:
        data = device.get_feature_report(REPORT_CONFIG, FEATURE_REPORT_LEN)
    except OSError as exc:
        raise ConfigReadError(f"读取配置失败（0xF7）：{exc}") from exc
    if not data:
        raise ConfigReadError("设备没有返回配置（0xF7）；请确认固件版本。")
    return unpack_config(data)


def read_firmware(device: Any) -> str:
    try:
        data = bytes(device.get_feature_report(REPORT_VERSION, FEATURE_REPORT_LEN) or b"")
    except OSError:
        return ""
    if data and data[0] == REPORT_VERSION:
        data = data[1:]
    raw = data.split(b"\x00", 1)[0].decode("ascii", "replace").strip()
    return raw


def read_status(device: Any) -> dict[str, Any]:
    """Read cached RSSI and audio activity (report 0xF9)."""
    empty = {"rssi": None, "speaker_active": None, "mic_active": None}
    try:
        data = bytes(device.get_feature_report(REPORT_STATUS, FEATURE_REPORT_LEN) or b"")
    except OSError:
        return empty
    if data and data[0] == REPORT_STATUS:
        data = data[1:]
    if len(data) < 1:
        return empty
    rssi = data[0] - 256 if data[0] > 127 else data[0]
    if not -128 <= rssi <= 0:
        rssi = None
    speaker_active: bool | None = None
    mic_active: bool | None = None
    if len(data) >= 2:
        flags = data[1]
        # The firmware marks a valid audio state with bit7 set and bits 2..6 clear.
        if (flags & 0x80) and (flags & 0x7C) == 0:
            speaker_active = bool(flags & 0x02)
            mic_active = bool(flags & 0x01)
    return {"rssi": rssi, "speaker_active": speaker_active, "mic_active": mic_active}


def parse_battery(report: bytes | bytearray | list[int]) -> dict[str, Any] | None:
    """Parse the battery byte from a standard DualSense 0x01 input report.

    The low nibble is capacity in 10% steps; the high nibble is the power
    state. Linux hid-playstation presents the midpoint (level * 10 + 5),
    which matches Sony's own 5%-step display. Error states carry no useful
    percentage.
    """
    raw = bytes(report)
    if len(raw) <= BATTERY_BYTE or raw[0] != REPORT_INPUT:
        return None
    battery = raw[BATTERY_BYTE]
    level = battery & 0x0F
    state = (battery >> 4) & 0x0F
    if state in (0x0A, 0x0B, 0x0F) or level > 10:
        percent = None
    elif state == 0x02:
        percent = 100
    else:
        percent = min(level * 10 + 5, 100)
    return {
        "percent": percent,
        "level": level,
        "state": state,
        "charging": state == 0x01,
        "label": (
            "电量低"
            if state == 0x00 and percent is not None and percent <= 20
            else BATTERY_NAMES.get(state, "状态未知")
        ),
    }


def _send_feature(device: Any, data: bytes, operation: str) -> None:
    payload = bytes([REPORT_SET]) + bytes(data)
    payload = payload[:FEATURE_REPORT_LEN].ljust(FEATURE_REPORT_LEN, b"\x00")
    try:
        sent = device.send_feature_report(payload)
    except OSError as exc:
        raise Ds5Error(f"{operation}失败：{exc}") from exc
    if sent not in (None, len(payload)):
        raise Ds5Error(f"{operation}失败：只写入 {sent}/{len(payload)} 字节。")
    time.sleep(HID_SET_REPORT_DELAY)


def write_config(device: Any, config: dict[str, Any], save: bool = False) -> dict[str, Any]:
    body = pack_config(config)
    _send_feature(device, bytes([FUNC_UPDATE]) + body, "应用配置")
    # Read-back also acts as a control-transfer barrier before a possible save.
    fresh = read_config(device)
    if save:
        _send_feature(device, bytes([FUNC_SAVE]), "保存设置")
        fresh = read_config(device)
    return fresh


def reconnect_usb(device: Any) -> None:
    _send_feature(device, bytes([FUNC_RECONNECT]), "重连 USB")


def enumerate_gamepads() -> list[dict[str, Any]]:
    try:
        import hid
    except ImportError as exc:
        raise DeviceNotFound("缺少 hidapi，请先安装 requirements.txt。") from exc
    return [
        info
        for info in hid.enumerate(VID)
        if info.get("product_id") in PIDS
        and info.get("usage_page") == USAGE_PAGE_GENERIC_DESKTOP
        and info.get("usage") == USAGE_GAMEPAD
    ]


def open_device(path: bytes) -> Any:
    try:
        import hid
    except ImportError as exc:
        raise DeviceNotFound("缺少 hidapi，请先安装 requirements.txt。") from exc
    device = hid.device()
    try:
        device.open_path(path)
    except OSError as exc:
        raise DeviceNotFound(f"无法打开设备：{exc}") from exc
    return device


def probe_devices() -> list[DeviceInfo]:
    """Probe all Sony gamepad interfaces; only 0xF8 responders are DS5Dongles."""
    infos: list[DeviceInfo] = []
    for raw in enumerate_gamepads():
        info = DeviceInfo(
            path=raw.get("path", b""),
            product_id=int(raw.get("product_id", 0)),
            product=raw.get("product_string") or "DualSense",
            serial=raw.get("serial_number") or "",
            interface=raw.get("interface_number"),
        )
        try:
            device = open_device(info.path)
            try:
                info.firmware = read_firmware(device)
                if not info.firmware:
                    raise ConfigReadError("没有识别到 DS5Dongle 固件（0xF8 无响应）。")
                read_config(device)
                info.supported = True
            finally:
                device.close()
        except Ds5Error as exc:
            info.error = str(exc)
        except OSError as exc:
            info.error = str(exc)
        infos.append(info)
    infos.sort(key=lambda item: (not item.supported, item.title.lower()))
    return infos


def find_supported_device() -> DeviceInfo:
    infos = probe_devices()
    for info in infos:
        if info.supported:
            return info
    detail = "；".join(f"{item.product}: {item.error}" for item in infos) or "没有找到 Sony 手柄接口"
    raise DeviceNotFound(f"没有找到 DS5Dongle（054C:0CE6/0DF2）。{detail}")


def status_text(status: dict[str, Any]) -> str:
    rssi = status.get("rssi")
    rssi_text = f"{rssi} dBm" if isinstance(rssi, int) else "RSSI 未知"
    speaker = status.get("speaker_active")
    mic = status.get("mic_active")
    if speaker is None and mic is None:
        return rssi_text
    return f"{rssi_text} · 扬声器{'开' if speaker else '关'} · 麦克风{'开' if mic else '关'}"
