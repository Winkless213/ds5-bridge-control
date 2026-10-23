# -*- coding: utf-8 -*-
"""QML-facing view model for the DS5 Bridge console.

The HID protocol and worker threads stay in ``service``/``protocol``; this
module only holds the UI state (draft config, connection, battery, status)
and exposes it to QML as properties and slots.
"""
from __future__ import annotations

from datetime import datetime
from collections import deque
from typing import Any

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from .protocol import (
    DEFAULTS,
    FIELD_ORDER,
    DeviceInfo,
    configs_equal,
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

POLL_NAMES = ("250 Hz", "500 Hz", "实时")
MODE_NAMES = ("DS5", "DSE", "自动")

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
}


def _signal_text(rssi: Any) -> str:
    if not isinstance(rssi, int) or rssi == 0:
        return "信号未知"
    if rssi >= -60:
        return "信号良好"
    if rssi >= -75:
        return "信号一般"
    return "信号较弱"


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
        return "1.5.0"


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
        self.service.battery_changed.connect(self._on_battery)
        self.service.rate_sample.connect(self._on_rate_sample)
        self.service.applied.connect(self._on_applied)
        self.service.error.connect(self._on_error)
        self.service.busy_changed.connect(self._on_busy)

        self._info: DeviceInfo | None = None
        self._device_config: dict[str, Any] | None = None
        self._firmware = ""
        self._draft = normalize_config(DEFAULTS)
        self._saved = False
        self._needs_reconnect = False
        self._empty_detail = ""
        self._probing = False
        self._status: dict[str, Any] = {
            "rssi": None,
            "speaker_active": None,
            "mic_active": None,
        }
        self._battery: dict[str, Any] = {
            "percent": None,
            "label": "电量未知",
            "charging": False,
        }
        self._timestamp = "—"
        self._started = False
        self._rate_active = False
        self._rate_stats: RateStats | None = None
        self._rate_error = False
        self._rate_samples: deque[float] = deque(maxlen=40)
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(5000)
        self._status_timer.timeout.connect(self._poll_status)

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
    def dirty(self) -> bool:
        return self.connected and not configs_equal(self._draft, self._device_config)

    @Property(bool, notify=stateChanged)
    def saved(self) -> bool:
        return self._saved

    @Property(bool, notify=stateChanged)
    def needsReconnect(self) -> bool:
        return self._needs_reconnect

    @Property(bool, notify=stateChanged)
    def canSave(self) -> bool:
        return self.connected and not self.service.busy and self.dirty

    @Property(bool, notify=stateChanged)
    def canRead(self) -> bool:
        return self.connected and not self.service.busy

    @Property(bool, notify=stateChanged)
    def canReset(self) -> bool:
        return self.connected and not self.service.busy

    @Property(str, notify=stateChanged)
    def statusText(self) -> str:
        if not self.connected:
            return "正在检测接收器…" if self._probing else "未连接"
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
        if self.service.busy:
            return "请稍候，不要拔掉接收器。"
        if self.dirty:
            return "点“保存更改”一次完成；需要时会自动重连。"
        if self._needs_reconnect:
            return "设置已保存，但自动重连没完成；请到“设备”页手动重连。"
        if self._saved:
            return "已写入接收器，断电后仍保留。"
        return "改完点“保存更改”就行，需要时会自动重连。"

    @Property(str, notify=stateChanged)
    def statusKind(self) -> str:
        if not self.connected:
            return "off"
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

    @Property(int, notify=stateChanged)
    def triggerReduce(self) -> int:
        return int(self._draft["trigger_reduce"])

    @Property(int, notify=stateChanged)
    def audioBuffer(self) -> int:
        return int(self._draft["audio_buffer_length"])

    @Property(int, notify=stateChanged)
    def inactiveTime(self) -> int:
        return int(self._draft["inactive_time"])

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

    @Property(str, notify=stateChanged)
    def gainLabel(self) -> str:
        return f"{self._draft['haptics_gain']:.2f}×"

    @Property(str, notify=stateChanged)
    def pollingLabel(self) -> str:
        return POLL_NAMES[int(self._draft["polling_rate_mode"])]

    @Property(str, notify=stateChanged)
    def modeLabel(self) -> str:
        return MODE_NAMES[int(self._draft["controller_mode"])]

    @Property(str, notify=stateChanged)
    def bufferLabel(self) -> str:
        return str(self._draft["audio_buffer_length"])

    @Property(str, notify=stateChanged)
    def audioSummary(self) -> str:
        gain = "自动" if self._draft["speaker_gain"] == 0 else str(self._draft["speaker_gain"])
        return f"增益 {gain} · 缓冲 {self._draft['audio_buffer_length']}"

    @Property(str, notify=stateChanged)
    def powerSummary(self) -> str:
        inactive = (
            "关闭" if self._draft["inactive_time"] == 0 else f"{self._draft['inactive_time']} 分钟"
        )
        led = "关" if self._draft["disable_pico_led"] else "开"
        mic = "关" if self._draft["disable_mic"] else "开"
        return f"{inactive} · 灯{led} · 麦克风{mic}"

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
        speaker = self._status.get("speaker_active")
        mic = self._status.get("mic_active")
        if speaker is None and mic is None:
            return "未知"
        return f"外放{'开' if speaker else '关'} · 麦克风{'开' if mic else '关'}"

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
        return "官方 v5 · 19 字节"

    @Property(str, notify=stateChanged)
    def timestampText(self) -> str:
        return self._timestamp

    @Property(str, notify=stateChanged)
    def rawText(self) -> str:
        config = self._device_config if self.connected else None
        if config is None:
            return "—"
        return " ".join(f"{byte:02X}" for byte in pack_config(config))

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

    @Property(bool, notify=batteryChanged)
    def batteryCharging(self) -> bool:
        return bool(self._battery.get("charging"))

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
            return "切到设备页后自动开始"
        if self._rate_error:
            return "无法读取 0x01 输入报文"
        if self._rate_stats is None:
            return "正在采样…"
        stats = self._rate_stats
        return f"p99 {stats.p99_ms:.1f} ms · 抖动 {stats.jitter_ms:.1f} ms · {stats.samples} 帧"

    @Property("QVariantList", notify=rateChanged)
    def reportRateSamples(self) -> list[float]:
        return list(self._rate_samples)

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
            self.service.connect(self._info)
        else:
            self.probe()

    @Slot()
    def save(self) -> None:
        if not self.connected or self.service.busy:
            return
        self.service.apply(
            dict(self._draft),
            save=True,
            reconnect=requires_reconnect(self._device_config, self._draft),
        )

    @Slot()
    def reload(self) -> None:
        if self._info and not self.service.busy:
            self.service.connect(self._info)

    @Slot()
    def resetDefaults(self) -> None:
        if not self.connected or self.service.busy:
            return
        defaults = normalize_config(DEFAULTS)
        self.service.apply(
            defaults,
            save=True,
            reconnect=requires_reconnect(self._device_config, defaults),
        )

    @Slot()
    def reconnectUsb(self) -> None:
        if self._info and not self.service.busy:
            self.service.reconnect()

    @Slot()
    def refreshStatus(self) -> None:
        if self._info and not self.service.busy:
            self.service.refresh_status()

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
        if self._info and not self.service.busy:
            self.service.refresh_status()

    @Slot(str, "QVariant")
    def setValue(self, name: str, value: Any) -> None:
        field = _CONFIG_FIELDS.get(name, name)
        if field not in FIELD_ORDER:
            return
        candidate = dict(self._draft)
        candidate[field] = value
        self._draft = normalize_config(candidate)
        self.stateChanged.emit()

    @Slot()
    def shutdown(self) -> None:
        self._status_timer.stop()
        self.service.shutdown()

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
    def _on_probe_done(self, infos: list[DeviceInfo]) -> None:
        self._probing = False
        supported = [info for info in infos if info.supported]
        if supported:
            self._empty_detail = ""
            self.stateChanged.emit()
            QTimer.singleShot(0, lambda info=supported[0]: self.service.connect(info))
            return
        if infos:
            self._empty_detail = (
                "检测到 Sony 手柄接口，但它没有响应 DS5Dongle 的 0xF8 固件报文。"
            )
        else:
            self._empty_detail = (
                "没有找到官方 DS5Dongle。请确认接收器已插好，手柄已开机并完成首次配对。"
            )
        self._info = None
        self._device_config = None
        self._firmware = ""
        self.service.watch_battery(None)
        self._battery = {"percent": None, "label": "电量未知", "charging": False}
        self.service.stop_rate()
        self._clear_rate()
        self.stateChanged.emit()
        self.batteryChanged.emit()
        self.rateChanged.emit()

    def _on_connected(
        self,
        info: DeviceInfo,
        config: dict[str, Any],
        firmware: str,
        status: dict[str, Any],
    ) -> None:
        self._info = info
        self._device_config = normalize_config(config)
        self._draft = dict(self._device_config)
        self._firmware = firmware or info.firmware
        self._saved = False
        self._needs_reconnect = False
        self._empty_detail = ""
        self._status = status or {}
        self._timestamp = datetime.now().strftime("%H:%M:%S")
        self.stateChanged.emit()
        self._start_rate()

    def _on_status(self, status: dict[str, Any]) -> None:
        self._status = status or {}
        self._timestamp = datetime.now().strftime("%H:%M:%S")
        self.stateChanged.emit()

    def _on_battery(self, state: dict[str, Any] | None) -> None:
        if state:
            self._battery = {
                "percent": state.get("percent"),
                "label": state.get("label") or "电量未知",
                "charging": bool(state.get("charging")),
            }
        else:
            self._battery = {"percent": None, "label": "电量未知", "charging": False}
        self.batteryChanged.emit()

    def _on_applied(self, result: ApplyResult) -> None:
        self._info = result.info
        self._device_config = normalize_config(result.config)
        self._draft = dict(self._device_config)
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
        self.toastRequested.emit("error", "操作失败", message)
        if not self._info:
            self._empty_detail = message
            self.service.watch_battery(None)
            self.service.stop_rate()
            self._battery = {"percent": None, "label": "电量未知", "charging": False}
            self._clear_rate()
            self.stateChanged.emit()
            self.batteryChanged.emit()
            self.rateChanged.emit()

    def _on_busy(self, busy: bool) -> None:
        self.stateChanged.emit()
