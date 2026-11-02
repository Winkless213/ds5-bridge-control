# -*- coding: utf-8 -*-
"""DS5Dongle (Pico2W DualSense bridge) host protocol.

The receiver enumerates as a Sony DualSense / DualSense Edge gamepad and
exposes the bridge configuration through HID feature reports 0xF6..0xF9.
This module deliberately implements only the official config-v5 layout
(19-byte body, firmware v0.7.2): the fork-specific 30-byte layout is not
compatible and must not be mixed in.
"""
from __future__ import annotations

import math
import re
import struct
import time
from array import array
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

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
# Byte 53: battery level (low nibble, 10% steps) + power state (high nibble).
# Byte 54: plug flags. See Linux hid-playstation.c and USBGetStateData in the
# DS5Dongle firmware (src/utils.h).
BATTERY_BYTE = 53
PLUG_BYTE = 54
PLUG_USB_DATA = 0x08
PLUG_USB_POWER = 0x10
PLUG_USB_POWER_ON_BT = 0x20
PLUG_ANY_POWER = PLUG_USB_DATA | PLUG_USB_POWER | PLUG_USB_POWER_ON_BT

POWER_DISCHARGING = 0x00
POWER_CHARGING = 0x01
POWER_COMPLETE = 0x02
POWER_ABNORMAL_VOLTAGE = 0x0A
POWER_ABNORMAL_TEMPERATURE = 0x0B
POWER_CHARGING_ERROR = 0x0F
LOW_BATTERY_LEVEL = 1  # level 0/1 = 5%/15%

BATTERY_NAMES = {
    POWER_DISCHARGING: "使用中",
    POWER_CHARGING: "充电中",
    POWER_COMPLETE: "已充满",
    POWER_ABNORMAL_VOLTAGE: "电压异常",
    POWER_ABNORMAL_TEMPERATURE: "温度异常",
    POWER_CHARGING_ERROR: "充电异常",
}

FUNC_UPDATE = 0x01
FUNC_SAVE = 0x02
FUNC_RECONNECT = 0x03

CONFIG_VERSION = 5
CONFIG_SIZE = 19
# The vibration build of v0.7.2 (firmware "v0.7.2-hotfix-vib.N") appends
# rumble_gain and vib_flags; official v0.7.2 ignores bytes past 19.
VIB_CONFIG_SIZE = 21
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
    "rumble_gain",
    "vib_flags",
)
BASE_FIELDS = FIELD_ORDER[:16]

# vib_flags bits, see src/vib.h in the vib firmware.
VIB_LEGACY_RUMBLE = 0x01
VIB_HAPTIC_LPF = 0x02
VIB_HARD_CLIP = 0x04

# Status report 0xF9 byte 1, added by the vib.2 firmware.
STATUS_RUMBLE_ACTIVE = 0x04  # a game drove the motors in the last ~400 ms
STATUS_REPORTS_RUMBLE = 0x08  # this build sets bit2 at all

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


# Windows (USB Audio volume) and games (SetState) change these in the
# receiver's RAM at any time; the console never edits them, so writes keep the
# receiver's current values instead of replaying the ones read at connect.
HOST_OWNED_KEYS: tuple[str, ...] = ("speaker_volume", "headset_volume")

# bt.cpp only refreshes its idle timestamp while idle disconnect is on, so a
# new value tried from RAM can drop the controller at once. Write it on save.
SAVE_ONLY_KEYS: tuple[str, ...] = ("inactive_time",)

# Fields the firmware applies as soon as an update (0xF6/0x01) lands, so the
# console can let the user try them before saving to flash.
LIVE_KEYS: tuple[str, ...] = tuple(
    key
    for key in FIELD_ORDER
    if key != "config_version"
    and key not in RECONNECT_KEYS
    and key not in HOST_OWNED_KEYS
    and key not in SAVE_ONLY_KEYS
)


def idle_drop_risk(saved: dict[str, Any] | None, draft: dict[str, Any] | None) -> str:
    """Why saving draft may disconnect an idle controller right away.

    "enable": the timer starts from the connect time, not from the save.
    "shorten": an idle stretch longer than the new limit already counts.
    """
    if saved is None or draft is None:
        return ""
    old = int(saved.get("inactive_time") or 0)
    new = int(draft.get("inactive_time") or 0)
    if new == 0 or new == old:
        return ""
    if old == 0:
        return "enable"
    return "shorten" if new < old else ""


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
    "rumble_gain": (0, 40),
    "vib_flags": (0, 7),
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
    "rumble_gain": 0,
    "vib_flags": 0,
}

# Little-endian, packed: version + float + 14 bytes (+ 2 on the vib firmware).
CONFIG_STRUCT = struct.Struct("<Bf14B")
VIB_CONFIG_STRUCT = struct.Struct("<Bf16B")


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


def pack_config(config: dict[str, Any], vib: bool = False) -> bytes:
    cfg = normalize_config(config)
    fields = FIELD_ORDER if vib else BASE_FIELDS
    values: list[Any] = [CONFIG_VERSION, float(cfg["haptics_gain"])]
    for name in fields[2:]:
        values.append(int(bool(cfg[name])) if name in BOOL_FIELDS else int(cfg[name]))
    return (VIB_CONFIG_STRUCT if vib else CONFIG_STRUCT).pack(*values)


def _config_body(payload: bytes | bytearray | memoryview) -> bytes:
    raw = bytes(payload)
    if not raw:
        raise ConfigReadError("设备返回了空的配置报文。")
    # WebHID returns the report ID as byte 0; hidapi may return the same.
    body = raw[1:] if raw[0] == REPORT_CONFIG and len(raw) >= CONFIG_SIZE + 1 else raw
    if len(body) < CONFIG_SIZE:
        raise ConfigReadError(
            f"配置报文只有 {len(body)} 字节，期望 {CONFIG_SIZE} 字节；请确认固件为官方 v0.7.2。"
        )
    if body[0] != CONFIG_VERSION:
        raise ConfigVersionError(
            f"配置版本不匹配：网页/本程序支持 v{CONFIG_VERSION}，设备返回 v{body[0]}。"
        )
    return body


def _has_vib_layout(body: bytes) -> bool:
    # hidapi returns only the bytes the receiver sent: 19 on v0.7.2, 21 here.
    return len(body) >= VIB_CONFIG_SIZE


def unpack_config(payload: bytes | bytearray | memoryview) -> dict[str, Any]:
    body = _config_body(payload)
    if _has_vib_layout(body):
        cfg = dict(zip(FIELD_ORDER, VIB_CONFIG_STRUCT.unpack(body[:VIB_CONFIG_SIZE])))
    else:
        cfg = dict(zip(BASE_FIELDS, CONFIG_STRUCT.unpack(body[:CONFIG_SIZE])))
        cfg.update({key: DEFAULTS[key] for key in FIELD_ORDER[len(BASE_FIELDS):]})
    for name in BOOL_FIELDS:
        cfg[name] = bool(cfg[name])
    cfg["config_version"] = int(cfg["config_version"])
    cfg["haptics_gain"] = round(float(cfg["haptics_gain"]), 2)
    return cfg


def configs_equal(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    if left is None or right is None:
        return left is right
    return pack_config(left, vib=True) == pack_config(right, vib=True)


def changed_keys(before: dict[str, Any] | None, after: dict[str, Any] | None) -> list[str]:
    """Fields whose packed value differs, in firmware order."""
    if before is None or after is None:
        return []
    left = normalize_config(before)
    right = normalize_config(after)
    keys: list[str] = []
    for key in FIELD_ORDER[1:]:
        if key == "haptics_gain":
            if struct.pack("<f", left[key]) != struct.pack("<f", right[key]):
                keys.append(key)
        elif left[key] != right[key]:
            keys.append(key)
    return keys


def live_config(saved: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    """The saved config with only the immediately-applied fields from draft."""
    out = normalize_config(saved)
    edited = normalize_config(draft)
    for key in LIVE_KEYS:
        out[key] = edited[key]
    return out


def keep_host_owned(config: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    out = normalize_config(config)
    for key in HOST_OWNED_KEYS:
        if key in current:
            out[key] = current[key]
    return normalize_config(out)


def config_text(config: dict[str, Any] | None) -> str:
    """Compact one-line form for the log."""
    if not config:
        return "-"
    cfg = normalize_config(config)
    parts = [f"haptics_gain={cfg['haptics_gain']:.2f}"]
    parts.extend(f"{key}={int(cfg[key])}" for key in FIELD_ORDER[2:])
    return " ".join(parts)


# Firmware v0.8.0 still reports config_version 5 but moved fields (mic/speaker
# selectors replace the disable flags) and grew the body to 24 bytes. Writing
# the v0.7.2 layout there would corrupt its settings, so only v0.7.2 builds
# are writable; anything else is shown read-only.
_WRITABLE_FIRMWARE = re.compile(r"^v?0\.7\.2(?:[-+._][0-9A-Za-z.+_-]*)?$", re.IGNORECASE)


def firmware_writable(firmware: str | None) -> bool:
    return bool(firmware) and bool(_WRITABLE_FIRMWARE.match(firmware.strip()))


def firmware_has_vib(firmware: str | None) -> bool:
    return firmware_writable(firmware) and "-vib" in (firmware or "").lower()


def firmware_block_reason(firmware: str | None) -> str:
    name = (firmware or "").strip() or "未知版本"
    return (
        f"接收器固件 {name} 的配置格式和本程序支持的 v0.7.2（19 字节）不一致，"
        "为避免写坏设置，本程序只读不写。"
    )


def _read_config_report(device: Any) -> bytes:
    try:
        data = device.get_feature_report(REPORT_CONFIG, FEATURE_REPORT_LEN)
    except OSError as exc:
        raise ConfigReadError(f"读取配置失败（0xF7）：{exc}") from exc
    if not data:
        raise ConfigReadError("设备没有返回配置（0xF7）；请确认固件版本。")
    return bytes(data)


def read_config(device: Any) -> dict[str, Any]:
    return unpack_config(_read_config_report(device))


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
    empty = {"rssi": None, "speaker_active": None, "mic_active": None, "rumble_active": None}
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
    rumble_active: bool | None = None
    if len(data) >= 2:
        flags = data[1]
        # bit7 marks a valid audio state; bits 4..6 stay reserved. Our vib.2
        # build adds bit3 to say it also reports rumble activity in bit2, so a
        # clear bit2 reads as "idle" there and "unknown" on firmware without it.
        if (flags & 0x80) and (flags & 0x70) == 0:
            speaker_active = bool(flags & 0x02)
            mic_active = bool(flags & 0x01)
            if flags & STATUS_REPORTS_RUMBLE:
                rumble_active = bool(flags & STATUS_RUMBLE_ACTIVE)
    return {
        "rssi": rssi,
        "speaker_active": speaker_active,
        "mic_active": mic_active,
        "rumble_active": rumble_active,
    }


def parse_battery(report: bytes | bytearray | list[int]) -> dict[str, Any] | None:
    """Parse the battery bytes of a standard DualSense 0x01 input report.

    The low nibble of byte 53 is the level in 10% steps and the high nibble
    is the power state. Linux hid-playstation presents the midpoint
    (level * 10 + 5); a completed charge reads 100% whatever the level says.
    Error states carry no trustworthy level, so ``percent`` is None there and
    ``BatteryTracker`` decides what to show.
    """
    raw = bytes(report)
    if len(raw) <= PLUG_BYTE or raw[0] != REPORT_INPUT:
        return None
    battery = raw[BATTERY_BYTE]
    flags = raw[PLUG_BYTE]
    level = battery & 0x0F
    state = (battery >> 4) & 0x0F
    if state == POWER_COMPLETE:
        percent: int | None = 100
        kind = "full"
    elif state in (POWER_DISCHARGING, POWER_CHARGING) and level <= 10:
        percent = min(level * 10 + 5, 100)
        if state == POWER_CHARGING:
            kind = "charging"
        else:
            kind = "low" if level <= LOW_BATTERY_LEVEL else "normal"
    else:
        percent = None
        kind = "error"
    if kind == "low":
        label = "电量低"
    elif kind == "error" and state in (POWER_DISCHARGING, POWER_CHARGING):
        label = "状态未知"
    else:
        label = BATTERY_NAMES.get(state, "状态未知")
    return {
        "percent": percent,
        "level": level,
        "state": state,
        "charging": state == POWER_CHARGING,
        "plugged": bool(flags & PLUG_ANY_POWER),
        "raw": battery,
        "flags": flags,
        "kind": kind,
        "label": label,
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
    # Read first: it re-checks the config version right before writing,
    # supplies the live volume values that Windows owns and tells whether the
    # receiver takes the vib layout.
    report = _read_config_report(device)
    current = unpack_config(report)
    body = pack_config(keep_host_owned(config, current), vib=_has_vib_layout(_config_body(report)))
    _send_feature(device, bytes([FUNC_UPDATE]) + body, "应用配置")
    # Read-back also acts as a control-transfer barrier before a possible save.
    fresh = read_config(device)
    if save:
        _send_feature(device, bytes([FUNC_SAVE]), "保存设置")
        fresh = read_config(device)
    return fresh


def reconnect_usb(device: Any) -> None:
    _send_feature(device, bytes([FUNC_RECONNECT]), "重连 USB")


REPORT_OUTPUT = 0x02
# Report id + the 47-byte SetStateData block state_update() needs; hidapi pads
# the write up to the descriptor's output report length.
RUMBLE_REPORT_LEN = 48
TEST_RUMBLE_LEVEL = 96  # ~38%, so boosts up to 250% still stay below 255
TEST_RUMBLE_SECONDS = 0.6

HAPTICS_RATE = 48000
# The waveform is multiplied by the receiver's HD gain (up to 2.0) and again by
# speaker_gain (7 is about twice the factory 2). At 0.4 even 1.0x clipped, so
# 1.0x and 2.0x felt identical; 0.25 keeps the worst case at full scale and no
# further, leaving every step up the range distinguishable.
TEST_HAPTICS_AMPLITUDE = 0.25
TEST_HAPTICS_HZ = 150.0
# Long enough to judge strength: a 0.18 s tap is over before the actuator has
# fully spun up, which flattens the difference between gains.
TEST_HAPTICS_BURST_SECONDS = 0.32


# Steady blue, close to what a console shows an idle player-1 pad.
LIGHTBAR_COLOR = (0, 70, 255)


def claim_lights_report() -> bytes:
    """Output report 0x02 that takes the LEDs off the pad's own control.

    Over Bluetooth the pad runs its "not claimed yet" blink until a host
    pulses ResetLights; colour and player-light writes sent before that are
    accepted but ignored. The receiver also only forwards a report straight
    away when a rumble flag is set, so this carries the same two flags the
    test-rumble report uses, with both motor values left at zero.
    """
    report = bytearray(RUMBLE_REPORT_LEN)
    report[0] = REPORT_OUTPUT
    report[1] = 0x02  # UseRumbleNotHaptics: makes the receiver forward now
    report[39] = 0x04  # EnableImprovedRumbleEmulation, needed by FW >= 2.24
    report[2] = 0x04 | 0x08 | 0x10  # AllowLedColor | ResetLights | AllowPlayerIndicators
    report[44] = 0x04  # player 1: the centre LED
    report[45], report[46], report[47] = LIGHTBAR_COLOR
    return bytes(report)


def rumble_report(level: int) -> bytes:
    """Output report 0x02 that only drives rumble; with every Allow* bit clear
    the receiver keeps the game's lights, triggers and volumes."""
    report = bytearray(RUMBLE_REPORT_LEN)
    report[0] = REPORT_OUTPUT
    if level:
        report[1] = 0x02  # UseRumbleNotHaptics
        report[39] = 0x04  # EnableImprovedRumbleEmulation, as games send to firmware 2.24+
        report[3] = report[4] = level  # light (right) and heavy (left) motor
    return bytes(report)


def play_test_rumble(device: Any, level: int = TEST_RUMBLE_LEVEL, seconds: float = TEST_RUMBLE_SECONDS) -> None:
    try:
        device.write(rumble_report(level))
        time.sleep(seconds)
    finally:
        # All flags clear hands the actuators back to audio haptics.
        device.write(rumble_report(0))


def haptics_test_frames() -> bytes:
    """Three short pulses as 4-channel float32 PCM for the pad's audio endpoint.

    Channels 1-2 feed the speaker and stay silent; 3-4 drive the actuators,
    the path a native game's haptics take, so the receiver's HD gain applies.
    """
    ramp = int(HAPTICS_RATE * 0.01)
    length = int(HAPTICS_RATE * TEST_HAPTICS_BURST_SECONDS)
    burst = [
        TEST_HAPTICS_AMPLITUDE
        * min(1.0, i / ramp, (length - 1 - i) / ramp)
        * math.sin(2 * math.pi * TEST_HAPTICS_HZ * i / HAPTICS_RATE)
        for i in range(length)
    ]
    gap = [0.0] * int(HAPTICS_RATE * 0.12)
    edge = [0.0] * int(HAPTICS_RATE * 0.1)
    samples = array("f")
    for value in edge + burst + gap + burst + gap + burst + edge:
        samples.extend((0.0, 0.0, value, value))
    return samples.tobytes()


def find_haptics_output(devices: Iterable[dict[str, Any]], hostapis: Sequence[dict[str, Any]]) -> int | None:
    """Index of the pad's 4-channel speaker endpoint under WASAPI, if listed."""
    for index, device in enumerate(devices):
        if (
            "DualSense" in device["name"]
            and device["max_output_channels"] >= 4
            and hostapis[device["hostapi"]]["name"] == "Windows WASAPI"
        ):
            return index
    return None


def play_test_haptics(device: Any = None) -> str:
    """Play haptics_test_frames() on the pad and return the endpoint's name.

    ``device`` is an open HID handle. While the pad is in rumble mode the
    actuators belong to the motors and the haptics channels are ignored, so a
    test right after a cold start played silently; it only became audible once
    a rumble test had run, because that test's all-clear report hands the
    actuators back. Send that report first instead of relying on it.
    """
    import sounddevice as sd  # loads PortAudio, so only once a test is asked for

    if device is not None:
        device.write(rumble_report(0))

    # PortAudio lists devices once, and a USB reconnect re-creates the pad's
    # endpoint, so drop the stale list before looking.
    sd._terminate()
    sd._initialize()
    devices = sd.query_devices()
    index = find_haptics_output(devices, sd.query_hostapis())
    if index is None:
        raise DeviceNotFound("没有找到手柄的 4 声道音频设备")
    with sd.RawOutputStream(samplerate=HAPTICS_RATE, channels=4, dtype="float32", device=index) as stream:
        stream.write(haptics_test_frames())
    return devices[index]["name"]


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
