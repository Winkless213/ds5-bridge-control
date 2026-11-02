# -*- coding: utf-8 -*-
"""QML-facing view model for the DS5 Bridge console.

The HID protocol and worker threads stay in ``service``/``protocol``; this
module only holds the UI state (draft config, connection, battery, status)
and exposes it to QML as properties and slots.

Config edits work in two layers: fields the firmware applies immediately are
written to the receiver's RAM as the user adjusts them (``preview``), so the
effect can be felt right away; "保存更改" writes everything to flash, and
"撤销" or quitting restores the saved values.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from datetime import datetime
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from . import applog
from .protocol import (
    BASE_FIELDS,
    DEFAULTS,
    FIELD_ORDER,
    LIVE_KEYS,
    VIB_LEGACY_RUMBLE,
    DeviceInfo,
    changed_keys,
    configs_equal,
    firmware_block_reason,
    firmware_has_vib,
    firmware_writable,
    idle_drop_risk,
    live_config,
    normalize_config,
    pack_config,
    requires_reconnect,
)
from .rate import RateStats
from .service import ApplyResult, DeviceService
from .theme import (
    ACCENT,
    ACCENT_2,
    AMBER,
    BG,
    BORDER,
    BORDER_SOFT,
    GREEN,
    MUTED,
    MUTED_2,
    RED,
    SURFACE,
    SURFACE_2,
    SURFACE_3,
    TEXT,
    TEXT_SOFT,
)

APP_VERSION = "1.6.0"
POLL_NAMES = ("250 Hz", "500 Hz", "实时")
MODE_NAMES = ("DS5", "DSE", "自动")

# Two failed 5 s status polls in a row mean the receiver is gone.
LOST_AFTER_FAILURES = 2
PREVIEW_DELAY_MS = 160
# A loss this soon after saving a riskier idle timeout is that timeout firing.
IDLE_DROP_WINDOW_S = 15.0

# The receiver only enumerates while a controller is connected over Bluetooth.
LOST_DETAIL = "接收器已离线。手柄断开（关机、闲置、没电）时它也会从电脑上消失；按 PS 键连上手柄或插好接收器后会自动恢复。"
IDLE_DROP_DETAIL = "手柄因闲置断开而离线；按 PS 键重新连接即可。"

log = logging.getLogger("ds5.ui")

_CONFIG_FIELDS = {
    "hapticsGain": "haptics_gain",
    "speakerGain": "speaker_gain",
    "triggerReduce": "trigger_reduce",
    "audioBuffer": "audio_buffer_length",
    "inactiveTime": "inactive_time",
    "disableLed": "disable_pico_led",
    "disableMic": "disable_mic",
    "disableSpeaker": "disable_speaker",
    "enableWake": "enable_wake",
    "polling": "polling_rate_mode",
    "mode": "controller_mode",
    "usbSn": "enable_usb_sn",
    "psShortcut": "ps_shortcut_enabled",
    "rumbleGain": "rumble_gain",
}
_FIELD_NAMES = {field: name for name, field in _CONFIG_FIELDS.items()}
_VIB_FLAGS = {
    "legacyRumble": VIB_LEGACY_RUMBLE,
}

_UNKNOWN_BATTERY: dict[str, Any] = {
    "percent": None,
    "label": "电量未知",
    "kind": "unknown",
    "charging": False,
    "plugged": False,
    "note": "",
}


def _signal_text(rssi: Any) -> str:
    if not isinstance(rssi, int) or rssi == 0:
        return "信号未知"
    if rssi >= -60:
        return "信号良好"
    if rssi >= -75:
        return "信号一般"
    return "信号较弱"


def audio_activity_text(status: dict[str, Any], config: dict[str, Any] | None) -> str:
    """Live audio state from report 0xF9, worded so it cannot be mistaken for
    the on/off settings: the firmware only sets these flags while Windows has
    the playback / recording stream open and the feature is not disabled."""
    speaker = status.get("speaker_active")
    mic = status.get("mic_active")
    if speaker is None and mic is None:
        return "未知"
    cfg = config or {}
    if cfg.get("disable_speaker"):
        speaker_text = "已关闭"
    else:
        speaker_text = "播放中" if speaker else "空闲"
    if cfg.get("disable_mic"):
        mic_text = "已关闭"
    else:
        mic_text = "录音中" if mic else "空闲"
    return f"声音{speaker_text} · 麦克风{mic_text}"


def _default_label(field: str, value: Any) -> str:
    """The factory value as the row itself words it."""
    if field == "inactive_time":
        return "不断开" if value == 0 else f"{value} 分钟"
    if field in ("speaker_gain", "trigger_reduce"):
        return "自动" if value == 0 else str(value)
    if field == "rumble_gain":
        return "100%" if value == 0 else f"{int(value) * 10}%"
    if field == "polling_rate_mode":
        return POLL_NAMES[int(value)]
    if field == "controller_mode":
        return MODE_NAMES[int(value)]
    if isinstance(value, bool):
        return "开" if value else "关"
    return str(value)


def vibration_path(status: dict[str, Any]) -> tuple[str, str]:
    """Which of the controller's two vibration systems a game is driving.

    The pad has ERM motors (ordinary rumble, a strength byte in output report
    0x02) and LRA actuators (HD haptics, a waveform on audio channels 3-4).
    A game picks one by which API it uses, so the strength each one needs is a
    separate setting; this tells the user which one their game is on.
    """
    rumble = status.get("rumble_active")
    if rumble is None:
        return "unknown", "固件不支持"
    if rumble:
        return "rumble", "普通震动"
    if status.get("speaker_active"):
        return "haptics", "HD 触觉"
    return "idle", "暂无震动"


def vibration_path_hint(status: dict[str, Any]) -> str:
    """Which slider the live path corresponds to, for the card's footnote."""
    kind = vibration_path(status)[0]
    if kind == "rumble":
        return "正走普通震动 → 调「普通震动强度」"
    if kind == "haptics":
        return "正走 HD 触觉 → 调「触觉强度」"
    if kind == "unknown":
        return "震动通路 = 游戏在用哪套震动硬件"
    return "震动通路 = 游戏在用哪套震动硬件"


class ThemeModel(QObject):
    """Static visual tokens; QML reads these as ``theme.accent`` etc."""

    @Property(str, constant=True)
    def bg(self) -> str:
        return BG

    @Property(str, constant=True)
    def surface(self) -> str:
        return SURFACE

    @Property(str, constant=True)
    def surface2(self) -> str:
        return SURFACE_2

    @Property(str, constant=True)
    def surface3(self) -> str:
        return SURFACE_3

    @Property(str, constant=True)
    def card(self) -> str:
        return "#0D151D"

    @Property(str, constant=True)
    def card2(self) -> str:
        return "#101A23"

    @Property(str, constant=True)
    def border(self) -> str:
        return BORDER

    @Property(str, constant=True)
    def borderSoft(self) -> str:
        return BORDER_SOFT

    @Property(str, constant=True)
    def text(self) -> str:
        return TEXT

    @Property(str, constant=True)
    def textSoft(self) -> str:
        return TEXT_SOFT

    @Property(str, constant=True)
    def muted(self) -> str:
        return MUTED

    @Property(str, constant=True)
    def muted2(self) -> str:
        return MUTED_2

    @Property(str, constant=True)
    def accent(self) -> str:
        return ACCENT

    @Property(str, constant=True)
    def accent2(self) -> str:
        return ACCENT_2

    @Property(str, constant=True)
    def green(self) -> str:
        return GREEN

    @Property(str, constant=True)
    def amber(self) -> str:
        return AMBER

    @Property(str, constant=True)
    def red(self) -> str:
        return RED

    @Property(str, constant=True)
    def mono(self) -> str:
        return "Cascadia Mono"

    @Property(str, constant=True)
    def version(self) -> str:
        return APP_VERSION


class UiBridge(QObject):
    stateChanged = Signal()
    batteryChanged = Signal()
    rateChanged = Signal()
    toastRequested = Signal(str, str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.service = DeviceService(self)
        self.service.probe_done.connect(self._on_probe_done)
        self.service.connected.connect(self._on_connected)
        self.service.status_read.connect(self._on_status)
        self.service.status_failed.connect(self._on_status_failed)
        self.service.battery_changed.connect(self._on_battery)
        self.service.rate_sample.connect(self._on_rate_sample)
        self.service.applied.connect(self._on_applied)
        self.service.preview_done.connect(self._on_preview_done)
        self.service.preview_failed.connect(self._on_preview_failed)
        self.service.error.connect(self._on_error)
        self.service.busy_changed.connect(self._on_busy)

        self._info: DeviceInfo | None = None
        # Config as saved on the receiver (read at connect, or after a save).
        self._device_config: dict[str, Any] | None = None
        self._firmware = ""
        self._draft = normalize_config(DEFAULTS)
        self._draft_rev = 0
        self._save_rev = -1
        # Last config sent as a preview, and the RAM config read back after
        # it when that differs from the saved one.
        self._requested: dict[str, Any] | None = None
        self._live: dict[str, Any] | None = None
        self._preview_error_shown = False
        self._saved = False
        self._needs_reconnect = False
        self._empty_detail = ""
        self._probing = False
        self._auto_probe = False
        self._lost = False
        self._lost_detail = LOST_DETAIL
        self._idle_drop_until = 0.0
        self._status_failures = 0
        self._status: dict[str, Any] = {
            "rssi": None,
            "speaker_active": None,
            "mic_active": None,
        }
        self._battery: dict[str, Any] = dict(_UNKNOWN_BATTERY)
        self._timestamp = "—"
        self._started = False
        self._rate_active = False
        self._rate_stats: RateStats | None = None
        self._rate_error = False
        self._rate_samples: deque[float] = deque(maxlen=40)
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(5000)
        self._status_timer.timeout.connect(self._poll_status)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DELAY_MS)
        self._preview_timer.timeout.connect(self._push_preview)

    # ------------------------------------------------------------------ state
    @Property(bool, notify=stateChanged)
    def connected(self) -> bool:
        return self._info is not None and self._device_config is not None

    @Property(bool, notify=stateChanged)
    def busy(self) -> bool:
        return self.service.busy

    @Property(bool, notify=stateChanged)
    def probing(self) -> bool:
        return self._probing

    @Property(bool, notify=stateChanged)
    def empty(self) -> bool:
        return bool(self._empty_detail)

    @Property(str, notify=stateChanged)
    def emptyDetail(self) -> str:
        return self._empty_detail

    @Property(bool, notify=stateChanged)
    def writable(self) -> bool:
        return self.connected and firmware_writable(self._firmware)

    @Property(str, notify=stateChanged)
    def readOnlyReason(self) -> str:
        if not self.connected or self.writable:
            return ""
        return firmware_block_reason(self._firmware)

    @Property(bool, notify=stateChanged)
    def dirty(self) -> bool:
        return self.connected and not configs_equal(self._draft, self._device_config)

    @Property("QVariantList", notify=stateChanged)
    def changedKeys(self) -> list[str]:
        if not self.connected:
            return []
        changed = changed_keys(self._device_config, self._draft)
        names = [_FIELD_NAMES[key] for key in changed if key in _FIELD_NAMES]
        if "vib_flags" in changed:
            flipped = int(self._device_config["vib_flags"]) ^ int(self._draft["vib_flags"])
            names.extend(name for name, bit in _VIB_FLAGS.items() if flipped & bit)
        return names

    @Property(bool, notify=stateChanged)
    def liveActive(self) -> bool:
        return self.connected and self._live is not None

    @Property(bool, notify=stateChanged)
    def pendingReconnect(self) -> bool:
        return self.dirty and requires_reconnect(self._device_config, self._draft)

    @Property(bool, notify=stateChanged)
    def saved(self) -> bool:
        return self._saved

    @Property(bool, notify=stateChanged)
    def needsReconnect(self) -> bool:
        return self._needs_reconnect

    @Property(bool, notify=stateChanged)
    def canSave(self) -> bool:
        return self.writable and not self.service.busy and self.dirty

    @Property(bool, notify=stateChanged)
    def canRead(self) -> bool:
        return self.connected and not self.service.busy

    @Property(bool, notify=stateChanged)
    def canRevert(self) -> bool:
        return self.connected and not self.service.busy and (self.dirty or self.liveActive)

    @Property(bool, notify=stateChanged)
    def canReset(self) -> bool:
        return self.writable and not self.service.busy

    @Property(str, notify=stateChanged)
    def statusText(self) -> str:
        if not self.connected:
            return "正在检测接收器…" if self._probing else "未连接"
        if not self.writable:
            return "只读模式"
        if self.service.busy:
            return "正在与接收器通信…"
        if self.dirty:
            return "有未保存的修改"
        if self._needs_reconnect:
            return "等待重新连接"
        if self._saved:
            return "已保存"
        return "设置与接收器一致"

    @Property(str, notify=stateChanged)
    def stateHint(self) -> str:
        if not self.connected:
            return "连接接收器后可以读取和修改设置。"
        if not self.writable:
            return self.readOnlyReason
        if self.service.busy:
            return "请稍候，不要拔掉接收器。"
        if self.dirty:
            changed = changed_keys(self._device_config, self._draft)
            live = any(key in LIVE_KEYS for key in changed)
            if live and self.pendingReconnect:
                return "声音和触觉的改动已在试用；连接相关的改动保存后会自动重连生效。"
            if self.pendingReconnect:
                return "这些改动要保存后自动重连才生效。"
            if not live:
                return "这些改动保存后才生效。"
            return "改动已在试用，可以直接感受；满意点“保存更改”，不满意点“撤销”。"
        if self._needs_reconnect:
            return "设置已保存，但自动重连没完成；请到“设备”页手动重连。"
        if self._saved:
            return "已写入接收器，断电后仍保留。"
        return "调节后马上生效试用；点“保存更改”才会写入接收器。"

    @Property(str, notify=stateChanged)
    def statusKind(self) -> str:
        if not self.connected:
            return "off"
        if not self.writable:
            return "warn"
        if self.service.busy:
            return "busy"
        if self.dirty or self._needs_reconnect:
            return "warn"
        if self._saved:
            return "ok"
        return "idle"

    # ------------------------------------------------------------------ config
    @Property(float, notify=stateChanged)
    def hapticsGain(self) -> float:
        return float(self._draft["haptics_gain"])

    @Property(int, notify=stateChanged)
    def speakerGain(self) -> int:
        return int(self._draft["speaker_gain"])

    @Property(str, notify=stateChanged)
    def speakerGainLabel(self) -> str:
        gain = int(self._draft["speaker_gain"])
        return "自动" if gain == 0 else str(gain)

    @Property(int, notify=stateChanged)
    def triggerReduce(self) -> int:
        return int(self._draft["trigger_reduce"])

    @Property(int, notify=stateChanged)
    def audioBuffer(self) -> int:
        return int(self._draft["audio_buffer_length"])

    @Property(int, notify=stateChanged)
    def inactiveTime(self) -> int:
        return int(self._draft["inactive_time"])

    @Property(str, notify=stateChanged)
    def idleDropHint(self) -> str:
        minutes = int(self._draft["inactive_time"])
        risk = idle_drop_risk(self._device_config, self._draft)
        if risk == "enable":
            return f"从这次手柄连上开始计时：已连上超过 {minutes} 分钟的话，保存时手柄会立刻断开，按 PS 键可重连"
        if risk == "shorten":
            return f"手柄已闲置超过 {minutes} 分钟的话，保存时会立刻断开，按 PS 键可重连"
        return ""

    @Property(bool, notify=stateChanged)
    def disableLed(self) -> bool:
        return bool(self._draft["disable_pico_led"])

    @Property(bool, notify=stateChanged)
    def disableMic(self) -> bool:
        return bool(self._draft["disable_mic"])

    @Property(bool, notify=stateChanged)
    def disableSpeaker(self) -> bool:
        return bool(self._draft["disable_speaker"])

    @Property(bool, notify=stateChanged)
    def enableWake(self) -> bool:
        return bool(self._draft["enable_wake"])

    @Property(int, notify=stateChanged)
    def polling(self) -> int:
        return int(self._draft["polling_rate_mode"])

    @Property(int, notify=stateChanged)
    def mode(self) -> int:
        return int(self._draft["controller_mode"])

    @Property(bool, notify=stateChanged)
    def usbSn(self) -> bool:
        return bool(self._draft["enable_usb_sn"])

    @Property(bool, notify=stateChanged)
    def psShortcut(self) -> bool:
        return bool(self._draft["ps_shortcut_enabled"])

    @Property(bool, notify=stateChanged)
    def vibSupported(self) -> bool:
        return self.connected and firmware_has_vib(self._firmware)

    @Property(int, notify=stateChanged)
    def rumbleGain(self) -> int:
        """Percent of the game's rumble; stored in 10% steps with 0 for 100%."""
        steps = int(self._draft["rumble_gain"])
        return steps * 10 if steps else 100

    @Property(str, notify=stateChanged)
    def rumbleGainLabel(self) -> str:
        return f"{self.rumbleGain}%"

    @Property(str, notify=stateChanged)
    def vibSummary(self) -> str:
        text = f"普通震动 {self.rumbleGainLabel}"
        return f"{text} · 老式换算" if self.legacyRumble else text

    @Property(bool, notify=stateChanged)
    def legacyRumble(self) -> bool:
        return bool(int(self._draft["vib_flags"]) & VIB_LEGACY_RUMBLE)

    @Property(int, notify=stateChanged)
    def vibFlags(self) -> int:
        return int(self._draft["vib_flags"])

    @Property(str, notify=stateChanged)
    def gainLabel(self) -> str:
        return f"{self._draft['haptics_gain']:.2f}×"

    @Property(bool, notify=stateChanged)
    def gainIsDefault(self) -> bool:
        return abs(float(self._draft["haptics_gain"]) - float(DEFAULTS["haptics_gain"])) < 0.005

    @Property(str, notify=stateChanged)
    def pollingLabel(self) -> str:
        return POLL_NAMES[int(self._draft["polling_rate_mode"])]

    @Property(str, notify=stateChanged)
    def modeLabel(self) -> str:
        return MODE_NAMES[int(self._draft["controller_mode"])]

    @Property(str, notify=stateChanged)
    def audioSummary(self) -> str:
        buffer = f"缓冲 {self._draft['audio_buffer_length']}"
        if self._draft["disable_speaker"]:
            return f"手柄声音已关闭 · {buffer}"
        return f"声音增益 {self.speakerGainLabel} · {buffer}"

    @Property(str, notify=stateChanged)
    def powerSummary(self) -> str:
        minutes = int(self._draft["inactive_time"])
        inactive = "闲置不断开" if minutes == 0 else f"闲置 {minutes} 分钟断开"
        led = "关" if self._draft["disable_pico_led"] else "开"
        mic = "已关闭" if self._draft["disable_mic"] else "可用"
        return f"{inactive} · 指示灯{led} · 麦克风{mic}"

    @Property(str, notify=stateChanged)
    def compatSummary(self) -> str:
        return f"{self.pollingLabel} · {self.modeLabel}"

    @Property(str, notify=stateChanged)
    def deviceSummary(self) -> str:
        if not self._info:
            return "等待连接"
        return f"{_signal_text(self._status.get('rssi'))} · 固件 {self._firmware or '未知'}"

    # ------------------------------------------------------------------ device
    @Property(str, notify=stateChanged)
    def deviceName(self) -> str:
        return self._info.product if self._info else "等待连接"

    @Property(str, notify=stateChanged)
    def deviceModel(self) -> str:
        return "DS5Dongle 无线接收器"

    @Property(str, notify=stateChanged)
    def firmware(self) -> str:
        return self._firmware or "未知"

    @Property(str, notify=stateChanged)
    def rssiText(self) -> str:
        return _signal_text(self._status.get("rssi"))

    @Property(str, notify=stateChanged)
    def audioText(self) -> str:
        return audio_activity_text(self._status, self._live or self._device_config)

    @Property(str, notify=stateChanged)
    def vibPathText(self) -> str:
        return vibration_path(self._status)[1]

    @Property(str, notify=stateChanged)
    def vibPathKind(self) -> str:
        return vibration_path(self._status)[0]

    @Property(str, notify=stateChanged)
    def vibPathHint(self) -> str:
        return vibration_path_hint(self._status)

    @Property(str, notify=stateChanged)
    def vidText(self) -> str:
        if not self._info:
            return "—"
        return "054C:0DF2" if self._info.product_id == 0x0DF2 else "054C:0CE6"

    @Property(str, notify=stateChanged)
    def interfaceText(self) -> str:
        return str(self._info.interface) if self._info and self._info.interface is not None else "—"

    @Property(str, notify=stateChanged)
    def configVersionText(self) -> str:
        if self.vibSupported:
            return "v5 + 震动扩展 · 21 字节"
        return "官方 v5 · 19 字节" if self.writable or not self.connected else "格式不兼容 · 只读"

    @Property(str, notify=stateChanged)
    def timestampText(self) -> str:
        return self._timestamp

    @Property(str, notify=stateChanged)
    def rawText(self) -> str:
        config = self._device_config if self.connected else None
        if config is None:
            return "—"
        return " ".join(f"{byte:02X}" for byte in pack_config(config, vib=self.vibSupported))

    @Property(str, notify=stateChanged)
    def deviceModeLabel(self) -> str:
        config = self._device_config if self.connected else self._draft
        return MODE_NAMES[int(config["controller_mode"])]

    # ------------------------------------------------------------------ battery
    @Property(int, notify=batteryChanged)
    def batteryPercent(self) -> int:
        value = self._battery.get("percent")
        return int(value) if value is not None else -1

    @Property(str, notify=batteryChanged)
    def batteryLabel(self) -> str:
        return str(self._battery.get("label") or "电量未知")

    @Property(str, notify=batteryChanged)
    def batteryKind(self) -> str:
        return str(self._battery.get("kind") or "unknown")

    @Property(bool, notify=batteryChanged)
    def batteryCharging(self) -> bool:
        return bool(self._battery.get("charging"))

    @Property(str, notify=batteryChanged)
    def batteryNote(self) -> str:
        return str(self._battery.get("note") or "")

    @Property(str, notify=batteryChanged)
    def batteryText(self) -> str:
        value = self._battery.get("percent")
        label = self._battery.get("label") or "电量未知"
        if value is None:
            return label
        return f"{value}% · {label}"

    # ---------------------------------------------------------------- rate
    @Property(str, notify=rateChanged)
    def reportRateValue(self) -> str:
        if not self._rate_active or self._rate_stats is None:
            return "—"
        return str(int(round(self._rate_stats.rate)))

    @Property(str, notify=rateChanged)
    def reportRateState(self) -> str:
        if not self._rate_active:
            return "off"
        if self._rate_error:
            return "error"
        if self._rate_stats is None:
            return "waiting"
        return self._rate_stats.state

    @Property(str, notify=rateChanged)
    def reportRateStateLabel(self) -> str:
        return {
            "off": "已停止",
            "waiting": "检测中",
            "stable": "稳定",
            "jitter": "有抖动",
            "error": "读取失败",
        }.get(self.reportRateState, "检测中")

    @Property(str, notify=rateChanged)
    def reportRateStateKind(self) -> str:
        return {
            "stable": "ok",
            "jitter": "warn",
            "error": "warn",
        }.get(self.reportRateState, "off")

    @Property(str, notify=rateChanged)
    def reportRateDetail(self) -> str:
        if not self._rate_active:
            return "窗口显示时自动开始"
        if self._rate_error:
            return "无法读取 0x01 输入报文"
        if self._rate_stats is None:
            return "正在采样…"
        stats = self._rate_stats
        return f"p99 {stats.p99_ms:.1f} ms · 抖动 {stats.jitter_ms:.1f} ms · {stats.samples} 帧"

    @Property("QVariantList", notify=rateChanged)
    def reportRateSamples(self) -> list[float]:
        return list(self._rate_samples)

    # ------------------------------------------------------------------ log
    @Property(str, constant=True)
    def logDir(self) -> str:
        return str(applog.log_dir())

    # ------------------------------------------------------------------ slots
    @Slot()
    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._probing = True
        self.stateChanged.emit()
        self._status_timer.start()
        QTimer.singleShot(120, self.service.probe)

    @Slot()
    def probe(self) -> None:
        self._probing = True
        self._empty_detail = ""
        self.stateChanged.emit()
        if not self.service.probe():
            self._probing = False
            self.stateChanged.emit()

    @Slot()
    def refresh(self) -> None:
        if self._info:
            self.reload()
        else:
            self.probe()

    @Slot()
    def save(self) -> None:
        if not self.writable or self.service.busy:
            return
        self._preview_timer.stop()
        self._save_rev = self._draft_rev
        reconnect = requires_reconnect(self._device_config, self._draft)
        log.info(
            "点击保存：改动 %s%s",
            ",".join(changed_keys(self._device_config, self._draft)) or "无",
            "（需要重连）" if reconnect else "",
        )
        self._expect_idle_drop(self._draft)
        self.service.apply(dict(self._draft), save=True, reconnect=reconnect)

    @Slot()
    def revert(self) -> None:
        """Drop unsaved edits and put the saved values back into RAM."""
        if not self.connected:
            return
        self._preview_timer.stop()
        log.info("撤销未保存的改动：%s", ",".join(changed_keys(self._device_config, self._draft)) or "无")
        self._draft = dict(self._device_config)
        self._draft_rev += 1
        self._restore_saved_ram()
        self.stateChanged.emit()
        self.toastRequested.emit("info", "已撤销", "设置已恢复为接收器里保存的值。")

    @Slot()
    def reload(self) -> None:
        if not self._info or self.service.busy:
            return
        self._preview_timer.stop()
        self._restore_saved_ram()
        self.service.connect(self._info)

    @Slot()
    def resetDefaults(self) -> None:
        if not self.writable or self.service.busy:
            return
        self._preview_timer.stop()
        defaults = normalize_config(DEFAULTS)
        log.info("恢复默认值")
        self._save_rev = self._draft_rev
        self._expect_idle_drop(defaults)
        self.service.apply(
            defaults,
            save=True,
            reconnect=requires_reconnect(self._device_config, defaults),
        )

    @Slot()
    def reconnectUsb(self) -> None:
        if self._info and not self.service.busy:
            self._restore_saved_ram()
            self.service.reconnect()

    @Slot()
    def refreshStatus(self) -> None:
        if self._info and not self.service.busy:
            self.service.refresh_status()

    @Slot()
    def openLogFolder(self) -> None:
        if not applog.open_log_folder():
            self.toastRequested.emit("warning", "打不开日志目录", self.logDir)

    @Slot(bool)
    def setRateMonitorActive(self, active: bool) -> None:
        active = bool(active)
        if active == self._rate_active:
            return
        self._rate_active = active
        self._clear_rate()
        if active and self._info:
            self.service.start_rate(self._info.path)
        else:
            self.service.stop_rate()
        self.rateChanged.emit()

    def _poll_status(self) -> None:
        if self._info:
            if not self.service.busy:
                self.service.refresh_status()
        elif self._auto_probe and not self._probing and self.service.idle:
            # The receiver went away; look for it again quietly.
            self.service.probe(quiet=True)

    @Slot(str, "QVariant")
    def setValue(self, name: str, value: Any) -> None:
        field = _CONFIG_FIELDS.get(name, name)
        if name in _VIB_FLAGS:
            field = "vib_flags"
            flags = int(self._draft["vib_flags"])
            value = flags | _VIB_FLAGS[name] if value else flags & ~_VIB_FLAGS[name]
        elif field == "rumble_gain":
            percent = int(round(float(value) / 10)) * 10
            value = 0 if percent == 100 else percent // 10
        if field not in FIELD_ORDER:
            return
        if field not in BASE_FIELDS and not self.vibSupported:
            return
        candidate = dict(self._draft)
        candidate[field] = value
        self._draft = normalize_config(candidate)
        self._draft_rev += 1
        self.stateChanged.emit()
        if field in LIVE_KEYS and self.writable:
            self._preview_timer.start()

    @Slot(str, result=str)
    def defaultHint(self, name: str) -> str:
        """"原厂默认 X" for a row that no longer matches it, else "".

        Shown so the user can see what they changed and what it used to be
        without having to remember.
        """
        if not self.connected:
            return ""
        field = _CONFIG_FIELDS.get(name)
        if field is None or field not in DEFAULTS:
            return ""
        default = DEFAULTS[field]
        current = self._draft.get(field)
        if field == "haptics_gain":
            if abs(float(current) - float(default)) < 0.005:
                return ""
            return f"原厂默认 {float(default):.2f}×"
        if current == default:
            return ""
        return f"原厂默认 {_default_label(field, default)}"

    @Slot(str)
    def restoreDefault(self, name: str) -> None:
        """Put one row back to its factory value, as a preview like any edit."""
        field = _CONFIG_FIELDS.get(name)
        if field is None or field not in DEFAULTS:
            return
        self.setValue(name, DEFAULTS[field])

    @Slot()
    def testRumble(self) -> None:
        if not self.vibSupported:
            return
        # Feel the strength just set, even inside the preview delay; the push
        # writes nothing when RAM already has it.
        self._preview_timer.stop()
        self._push_preview()
        self.service.test_rumble()

    @Slot()
    def testHaptics(self) -> None:
        if not self.writable:
            return
        # The pulse is scaled by the HD gain in RAM, so push the one just set.
        self._preview_timer.stop()
        self._push_preview()
        self.service.test_haptics()

    @Slot()
    def shutdown(self) -> None:
        self._status_timer.stop()
        self._preview_timer.stop()
        if self.writable and (self._requested is not None or self._live is not None):
            # Unsaved previews only live in RAM; put the saved values back.
            self.service.write_now(self._device_config)  # type: ignore[arg-type]
        self.service.shutdown()
        log.info("退出")

    # --------------------------------------------------------------- preview
    def _push_preview(self) -> None:
        if not self.writable or self._device_config is None:
            return
        target = live_config(self._device_config, self._draft)
        last = self._requested or self._device_config
        if configs_equal(target, last):
            return
        self._requested = target
        self.service.preview(target)

    def _expect_idle_drop(self, target: dict[str, Any]) -> None:
        if idle_drop_risk(self._device_config, target):
            self._idle_drop_until = time.monotonic() + IDLE_DROP_WINDOW_S

    def _restore_saved_ram(self) -> None:
        if self._device_config is None:
            return
        if self._requested is not None or self._live is not None:
            self._requested = None
            self.service.preview(self._device_config)

    def _on_preview_done(self, fresh: dict[str, Any]) -> None:
        if self._device_config is None:
            return
        fresh = normalize_config(fresh)
        self._live = None if configs_equal(fresh, self._device_config) else fresh
        if self._live is None and configs_equal(self._requested, self._device_config):
            self._requested = None
        self._preview_error_shown = False
        self.stateChanged.emit()

    def _on_preview_failed(self, message: str) -> None:
        if not self._preview_error_shown:
            self._preview_error_shown = True
            self.toastRequested.emit("warning", "试用没有生效", message)
        self.stateChanged.emit()

    def _clear_rate(self) -> None:
        self._rate_stats = None
        self._rate_error = False
        self._rate_samples.clear()

    def _start_rate(self) -> None:
        if not (self._rate_active and self._info):
            return
        self._clear_rate()
        self.service.start_rate(self._info.path)
        self.rateChanged.emit()

    @Slot(object)
    def _on_rate_sample(self, stats: RateStats | None) -> None:
        if not self._rate_active:
            return
        if stats is None:
            self._rate_stats = None
            self._rate_error = True
            self._rate_samples.clear()
        else:
            self._rate_stats = stats
            self._rate_error = False
            self._rate_samples.append(stats.rate)
        self.rateChanged.emit()

    # ------------------------------------------------------------- service in
    def _drop_device(self, detail: str) -> None:
        self._info = None
        self._device_config = None
        self._firmware = ""
        self._requested = None
        self._live = None
        self._status_failures = 0
        self._empty_detail = detail
        self.service.watch_battery(None)
        self._battery = dict(_UNKNOWN_BATTERY)
        self.service.stop_rate()
        self._clear_rate()
        self.stateChanged.emit()
        self.batteryChanged.emit()
        self.rateChanged.emit()

    def _on_probe_done(self, infos: list[DeviceInfo]) -> None:
        was_probing = self._probing
        self._probing = False
        supported = [info for info in infos if info.supported]
        if supported:
            self._empty_detail = ""
            self.stateChanged.emit()
            QTimer.singleShot(0, lambda info=supported[0]: self.service.connect(info))
            return
        if self._lost:
            detail = self._lost_detail
        elif infos:
            detail = "检测到 Sony 手柄接口，但它没有响应 DS5Dongle 的 0xF8 固件报文。"
        else:
            detail = "没有找到官方 DS5Dongle。请确认接收器已插好，手柄已开机并完成首次配对。"
        # Keep looking in the background so plugging it in just works.
        self._auto_probe = True
        if self._info is None and self._empty_detail == detail:
            if was_probing:
                self.stateChanged.emit()
            return
        self._drop_device(detail)

    def _on_connected(
        self,
        info: DeviceInfo,
        config: dict[str, Any],
        firmware: str,
        status: dict[str, Any],
    ) -> None:
        recovered = self._lost
        self._info = info
        self._device_config = normalize_config(config)
        self._draft = dict(self._device_config)
        self._draft_rev += 1
        self._requested = None
        self._live = None
        self._firmware = firmware or info.firmware
        self._saved = False
        self._needs_reconnect = False
        self._empty_detail = ""
        self._lost = False
        self._auto_probe = False
        self._status_failures = 0
        self._status = status or {}
        self._timestamp = datetime.now().strftime("%H:%M:%S")
        if not firmware_writable(self._firmware):
            log.warning("固件 %s 不在可写列表，进入只读模式", self._firmware or "-")
        self.stateChanged.emit()
        self._start_rate()
        # The pad blinks its "unclaimed" animation until some host drives the
        # LEDs; nothing else on PC does it when no game is running.
        self.service.claim_lights()
        if recovered:
            self.toastRequested.emit("info", "接收器已重新连接", "设置已重新读取。")

    def _on_status(self, status: dict[str, Any]) -> None:
        status = status or {}
        if self._status_failures:
            log.info("状态读取恢复")
        self._status_failures = 0
        if status != self._status:
            log.info(
                "状态：RSSI %s · 声音%s · 麦克风%s",
                status.get("rssi"),
                {True: "开流", False: "无流", None: "未知"}[status.get("speaker_active")],
                {True: "开流", False: "无流", None: "未知"}[status.get("mic_active")],
            )
        self._status = status
        self._timestamp = datetime.now().strftime("%H:%M:%S")
        self.stateChanged.emit()

    def _on_status_failed(self, message: str) -> None:
        self._status_failures += 1
        if self._status_failures < LOST_AFTER_FAILURES or not self._info:
            return
        log.warning("接收器连续 %d 次读状态失败，判定为已断开：%s", self._status_failures, message)
        idle_drop = time.monotonic() < self._idle_drop_until
        self._idle_drop_until = 0.0
        self._lost = True
        self._auto_probe = True
        self._lost_detail = IDLE_DROP_DETAIL if idle_drop else LOST_DETAIL
        self._drop_device(self._lost_detail)
        if idle_drop:
            log.info("断开发生在保存闲置断开之后，按闲置断开处理")
            self.toastRequested.emit(
                "warning", "闲置断开已生效", "手柄被判定为闲置，所以马上断开了；按 PS 键重新连接即可。"
            )
        else:
            self.toastRequested.emit("warning", "接收器已离线", "按 PS 键连上手柄，或重新插好接收器。")

    def _on_battery(self, state: dict[str, Any] | None) -> None:
        if state:
            self._battery = {
                "percent": state.get("percent"),
                "label": state.get("label") or "电量未知",
                "kind": state.get("kind") or "unknown",
                "charging": bool(state.get("charging")),
                "plugged": bool(state.get("plugged")),
                "note": state.get("note") or "",
            }
        else:
            self._battery = dict(_UNKNOWN_BATTERY)
        self.batteryChanged.emit()

    def _on_applied(self, result: ApplyResult) -> None:
        self._info = result.info
        self._device_config = normalize_config(result.config)
        self._requested = None
        self._live = None
        if self._draft_rev == self._save_rev:
            self._draft = dict(self._device_config)
        elif self.writable:
            # The user kept adjusting while the save ran; keep those edits
            # and try them on top of the new saved values.
            self._preview_timer.start()
        self._firmware = result.firmware or result.info.firmware or self._firmware
        self._saved = bool(result.saved)
        self._needs_reconnect = bool(result.reconnect_error)
        if result.status is not None:
            self._status = result.status
            self._timestamp = datetime.now().strftime("%H:%M:%S")
        self.stateChanged.emit()
        if result.reconnected:
            self._start_rate()
        elif result.reconnect_error:
            self.service.stop_rate()
            self._clear_rate()
            self.rateChanged.emit()

        if result.reconnect_error:
            self.toastRequested.emit(
                "warning",
                "设置已保存，但重连没完成",
                "请到“设备”页点“重连 USB”，新设置才会完全生效。",
            )
        elif result.reconnected:
            self.toastRequested.emit(
                "info", "已保存并生效", "接收器已重新连接，新设置已经生效。"
            )
        elif result.saved:
            self.toastRequested.emit("info", "已保存", "设置已写入接收器，断电后仍保留。")
        else:
            self.toastRequested.emit("info", "已应用", "设置已经生效。")

    def _on_error(self, message: str) -> None:
        log.warning("操作失败：%s", message)
        self.toastRequested.emit("error", "操作失败", message)
        if not self._info:
            self._probing = False
            self._auto_probe = True
            self._drop_device(message)

    def _on_busy(self, busy: bool) -> None:
        self.stateChanged.emit()
