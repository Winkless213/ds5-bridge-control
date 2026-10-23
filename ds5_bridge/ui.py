# -*- coding: utf-8 -*-
"""DS5 Bridge console UI."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import InfoBar, InfoBarPosition, SmoothScrollArea, Theme, setTheme, setThemeColor

from .protocol import (
    DEFAULTS,
    DeviceInfo,
    configs_equal,
    normalize_config,
    pack_config,
    requires_reconnect,
)
from .service import ApplyResult, DeviceService
from .theme import (
    ACCENT,
    ACCENT_2,
    AMBER,
    APP_QSS,
    BG,
    BORDER,
    GREEN,
    MUTED,
    MUTED_2,
    RED,
    SURFACE,
    SURFACE_3,
    TEXT,
    TEXT_SOFT,
)
from .widgets import (
    BatteryPill,
    BrandMark,
    Card,
    CollapsibleCard,
    HeroCard,
    Metric,
    NavButton,
    PillSelector,
    SectionHeader,
    SettingRow,
    SliderControl,
    StatusPill,
    ToggleControl,
)

APP_NAME = "DS5 Bridge 控制台"
APP_VERSION = "1.4.0"

PAGE_META = [
    ("配置", "调整声音、震动和连接方式"),
    ("设备", "连接状态、电量、固件版本与实时信号"),
    ("关于", "版本与协议信息"),
]

MODE_NAMES = ("DS5", "DSE", "自动")
POLL_NAMES = ("250 Hz", "500 Hz", "实时")


def _label(text: str, object_name: str = "Muted") -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    return label


def _card(title: str, subtitle: str = "") -> Card:
    card = Card()
    card.body.addWidget(SectionHeader(title, subtitle))
    return card


def _row(title: str, description: str, control: QWidget) -> SettingRow:
    return SettingRow(title, description, control)


def _signal_text(rssi: Any) -> str:
    if not isinstance(rssi, int) or rssi == 0:
        return "信号未知"
    if rssi >= -60:
        return "信号良好"
    if rssi >= -75:
        return "信号一般"
    return "信号较弱"


class EmptyState(QWidget):
    def __init__(self, on_probe, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 40, 0, 40)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        mark = BrandMark()
        mark.setFixedSize(56, 56)
        layout.addWidget(mark, 0, Qt.AlignCenter)
        title = QLabel("没有找到 DS5 Bridge")
        title.setStyleSheet(f"color: {TEXT}; font-size: 22px; font-weight: 600;")
        layout.addWidget(title, 0, Qt.AlignCenter)
        self.detail = QLabel("请确认接收器已插好，手柄已开机并完成首次配对。")
        self.detail.setObjectName("Muted")
        self.detail.setAlignment(Qt.AlignCenter)
        self.detail.setWordWrap(True)
        self.detail.setMaximumWidth(480)
        layout.addWidget(self.detail, 0, Qt.AlignCenter)
        button = QPushButton("重新检测")
        button.setObjectName("PrimaryButton")
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedWidth(148)
        button.clicked.connect(on_probe)
        layout.addWidget(button, 0, Qt.AlignCenter)

    def set_detail(self, text: str) -> None:
        self.detail.setText(text)


class ConfigPage(QWidget):
    def __init__(self, service: DeviceService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.info: DeviceInfo | None = None
        self.device_config: dict[str, Any] | None = None
        self.draft: dict[str, Any] = normalize_config(DEFAULTS)
        self._speaker_volume = int(self.draft["speaker_volume"])
        self._headset_volume = int(self.draft["headset_volume"])
        self.saved = False
        self.needs_reconnect = False
        self.status: dict[str, Any] = {}
        self._loading = False
        self._busy = False
        self._build()
        self._wire()
        self._load_controls(self.draft)
        self._set_enabled(False)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self.empty = EmptyState(lambda: self.service.probe())
        self.stack.addWidget(self.empty)

        scroll = SmoothScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        body = QVBoxLayout(content)
        body.setContentsMargins(0, 0, 12, 24)
        body.setSpacing(18)
        self.content = content

        # Hero: haptics gain is the one control that deserves headline treatment.
        hero = HeroCard()
        hero_row = QHBoxLayout()
        hero_row.setSpacing(34)
        left = QVBoxLayout()
        left.setSpacing(6)
        kicker = QLabel("触觉强度")
        kicker.setStyleSheet(
            f"color: {ACCENT}; font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )
        left.addWidget(kicker)
        self.gain_value = QLabel("1.00×")
        self.gain_value.setStyleSheet(
            f"color: {TEXT}; font-family: 'Bahnschrift'; font-size: 42px; font-weight: 600;"
        )
        left.addWidget(self.gain_value)
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setRange(100, 200)
        self.gain_slider.setFixedWidth(380)
        left.addWidget(self.gain_slider)
        left.addWidget(_label("震动和扳机反馈的整体强度；默认即可。", "Description"))
        hero_row.addLayout(left, 1)

        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet(f"background: {BORDER};")
        hero_row.addWidget(divider)

        right = QGridLayout()
        right.setHorizontalSpacing(26)
        right.setVerticalSpacing(16)
        self.hero_polling = Metric("上报速度")
        self.hero_mode = Metric("控制器模式")
        self.hero_buffer = Metric("声音缓冲")
        right.addWidget(self.hero_polling, 0, 0)
        right.addWidget(self.hero_mode, 0, 1)
        right.addWidget(self.hero_buffer, 0, 2)
        hero_row.addLayout(right, 0)
        hero.body.addLayout(hero_row)
        body.addWidget(hero)

        self.audio_card = CollapsibleCard(
            "音频与触觉", "声音和触觉反馈", expanded=True
        )
        self.volume_hint = _label(
            "音量请用 Windows 音量面板调节。", "Description"
        )
        self.volume_hint.setWordWrap(True)
        self.volume_hint.setContentsMargins(0, 0, 0, 8)
        self.audio_card.add_widget(self.volume_hint)
        self.speaker_gain = QComboBox()
        self.speaker_gain.addItems(["自动"] + [str(i) for i in range(1, 8)])
        self.speaker_gain.setFixedWidth(112)
        self.trigger_reduce = SliderControl(
            0, 10, 0, lambda v: "自动" if v == 0 else str(v)
        )
        self.audio_buffer = SliderControl(16, 127, 64)
        self.audio_card.add_row(_row("声音增益", "声音偏小时调高；自动即可", self.speaker_gain))
        self.audio_card.add_row(_row("扳机反馈减弱", "反馈太强时调高；自动即可", self.trigger_reduce))
        self.audio_card.add_row(_row("声音缓冲", "越小延迟越低，但可能断续；默认即可", self.audio_buffer))
        body.addWidget(self.audio_card)

        self.power_card = CollapsibleCard(
            "电源与指示灯", "省电、指示灯和音频开关", expanded=False
        )
        self.inactive_time = SliderControl(
            0, 60, 30, lambda v: "关闭" if v == 0 else f"{v} 分钟"
        )
        self.disable_led = ToggleControl()
        self.disable_mic = ToggleControl()
        self.disable_speaker = ToggleControl()
        self.enable_wake = ToggleControl()
        self.power_card.add_row(_row("闲置自动断开", "一段时间不用就断开，省电", self.inactive_time))
        self.power_card.add_row(_row("关闭指示灯", "关掉接收器上的灯", self.disable_led))
        self.power_card.add_row(_row("关闭麦克风", "关掉手柄麦克风", self.disable_mic))
        self.power_card.add_row(_row("关闭外放和耳机", "关掉手柄的声音输出", self.disable_speaker))
        self.power_card.add_row(_row("PS 键唤醒电脑", "按 PS 键把电脑从睡眠唤醒", self.enable_wake))
        body.addWidget(self.power_card)

        self.compat_card = CollapsibleCard(
            "性能与兼容性", "影响电脑如何识别手柄；保存后自动重连", expanded=False
        )
        self.polling = PillSelector(POLL_NAMES, 0)
        self.mode = PillSelector(MODE_NAMES, 2)
        self.usb_sn = ToggleControl()
        self.ps_shortcut = ToggleControl()
        self.compat_card.add_row(_row("上报速度", "越高越跟手，但可能抖动；推荐中间档", self.polling))
        self.compat_card.add_row(_row("手柄识别方式", "影响电脑和官方应用识别到的手柄型号；自动即可", self.mode))
        self.compat_card.add_row(_row("固定设备身份", "换 USB 口后仍认作同一手柄；一般不用开", self.usb_sn))
        self.compat_card.add_row(_row("PS 键打开 Game Bar", "按 PS 键打开 Xbox Game Bar", self.ps_shortcut))
        body.addWidget(self.compat_card)

        self.device_card = CollapsibleCard(
            "设备状态", "接收器和手柄的实时状态", expanded=False
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(26)
        grid.setVerticalSpacing(14)
        self.device_name = Metric("设备")
        self.device_rssi = Metric("信号")
        self.device_audio = Metric("音频")
        grid.addWidget(self.device_name, 0, 0)
        grid.addWidget(self.device_rssi, 0, 1)
        grid.addWidget(self.device_audio, 0, 2)
        self.device_card.content_layout.addLayout(grid)
        self.device_hint = _label("等待读取设备状态…", "Description")
        self.device_card.content_layout.addWidget(self.device_hint)
        body.addWidget(self.device_card)

        body.addStretch(1)

        scroll.setWidget(content)
        self.stack.addWidget(scroll)
        self.scroll = scroll

        # Actions stay outside the scroll area so saving is always reachable.
        self.footer = Card()
        self.footer.body.setContentsMargins(20, 14, 20, 14)
        footer_row = QHBoxLayout()
        footer_row.setSpacing(24)
        state_box = QVBoxLayout()
        state_box.setSpacing(4)
        self.state_label = QLabel("未连接")
        self.state_label.setStyleSheet(f"color: {TEXT}; font-size: 16px; font-weight: 600;")
        state_box.addWidget(self.state_label)
        self.state_hint = _label("连接接收器后可以读取和修改设置。", "Description")
        self.state_hint.setWordWrap(True)
        state_box.addWidget(self.state_hint)
        self.reconnect_warning = QLabel(
            "自动重连没有完成。请到“设备”页点“重连 USB”，再试一次。"
        )
        self.reconnect_warning.setWordWrap(True)
        self.reconnect_warning.setStyleSheet(
            f"color: {AMBER}; font-size: 12.5px; background: rgba(245,183,78,0.07);"
            "border: 1px solid rgba(245,183,78,0.18); border-radius: 8px; padding: 8px 10px;"
        )
        self.reconnect_warning.hide()
        state_box.addWidget(self.reconnect_warning)
        footer_row.addLayout(state_box, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.save_btn = QPushButton("保存更改")
        self.save_btn.setObjectName("PrimaryButton")
        self.save_btn.setMinimumWidth(132)
        self.save_btn.setToolTip("写入接收器，断电后仍保留；必要时会自动重连。")
        self.read_btn = QPushButton("重新读取")
        self.read_btn.setObjectName("GhostButton")
        self.read_btn.setMinimumWidth(108)
        self.reset_btn = QPushButton("恢复默认值")
        self.reset_btn.setObjectName("DangerButton")
        self.reset_btn.setMinimumWidth(116)
        for button in (self.save_btn, self.read_btn, self.reset_btn):
            button.setCursor(Qt.PointingHandCursor)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.read_btn)
        buttons.addWidget(self.reset_btn)
        footer_row.addLayout(buttons, 0)
        self.footer.body.addLayout(footer_row)
        self.footer.hide()
        root.addWidget(self.footer)

    def _wire(self) -> None:
        self.gain_slider.valueChanged.connect(self._on_gain)
        for control in (
            self.trigger_reduce,
            self.audio_buffer,
            self.inactive_time,
        ):
            control.value_changed.connect(self._on_edit)
        self.speaker_gain.currentIndexChanged.connect(self._on_edit)
        for toggle in (
            self.disable_led,
            self.disable_mic,
            self.disable_speaker,
            self.enable_wake,
            self.usb_sn,
            self.ps_shortcut,
        ):
            toggle.checked_changed.connect(self._on_edit)
        self.polling.changed.connect(self._on_edit)
        self.mode.changed.connect(self._on_edit)
        self.save_btn.clicked.connect(self._commit)
        self.read_btn.clicked.connect(lambda: self.service.connect(self.info) if self.info else None)
        self.reset_btn.clicked.connect(self._reset)

    def _commit(self) -> None:
        if not self.info or self._busy:
            return
        self.service.apply(
            self.draft,
            save=True,
            reconnect=requires_reconnect(self.device_config, self.draft),
        )

    def _on_gain(self, value: int) -> None:
        self.gain_value.setText(f"{value / 100:.2f}×")
        self._on_edit()

    def _on_edit(self, *_args) -> None:
        if self._loading:
            return
        self.draft = self._collect()
        self._update_summaries()
        self._update_state()

    def _collect(self) -> dict[str, Any]:
        return normalize_config(
            {
                "haptics_gain": self.gain_slider.value() / 100,
                "speaker_volume": self._speaker_volume,
                "headset_volume": self._headset_volume,
                "speaker_gain": self.speaker_gain.currentIndex(),
                "inactive_time": self.inactive_time.value(),
                "disable_pico_led": self.disable_led.is_checked(),
                "polling_rate_mode": self.polling.value(),
                "audio_buffer_length": self.audio_buffer.value(),
                "controller_mode": self.mode.value(),
                "enable_usb_sn": self.usb_sn.is_checked(),
                "ps_shortcut_enabled": self.ps_shortcut.is_checked(),
                "disable_mic": self.disable_mic.is_checked(),
                "disable_speaker": self.disable_speaker.is_checked(),
                "enable_wake": self.enable_wake.is_checked(),
                "trigger_reduce": self.trigger_reduce.value(),
            }
        )

    def _load_controls(self, config: dict[str, Any]) -> None:
        cfg = normalize_config(config)
        self._loading = True
        self.gain_slider.setValue(int(round(cfg["haptics_gain"] * 100)))
        self.gain_value.setText(f"{self.gain_slider.value() / 100:.2f}×")
        self._speaker_volume = int(cfg["speaker_volume"])
        self._headset_volume = int(cfg["headset_volume"])
        self.speaker_gain.setCurrentIndex(cfg["speaker_gain"])
        self.trigger_reduce.set_value(cfg["trigger_reduce"])
        self.audio_buffer.set_value(cfg["audio_buffer_length"])
        self.inactive_time.set_value(cfg["inactive_time"])
        self.disable_led.set_checked(cfg["disable_pico_led"])
        self.disable_mic.set_checked(cfg["disable_mic"])
        self.disable_speaker.set_checked(cfg["disable_speaker"])
        self.enable_wake.set_checked(cfg["enable_wake"])
        self.polling.set_value(cfg["polling_rate_mode"])
        self.mode.set_value(cfg["controller_mode"])
        self.usb_sn.set_checked(cfg["enable_usb_sn"])
        self.ps_shortcut.set_checked(cfg["ps_shortcut_enabled"])
        self._loading = False
        self.draft = cfg
        self._update_metrics()
        self._update_state()

    def _update_metrics(self) -> None:
        cfg = self.draft
        self.hero_polling.set_value(POLL_NAMES[cfg["polling_rate_mode"]])
        self.hero_mode.set_value(MODE_NAMES[cfg["controller_mode"]])
        self.hero_buffer.set_value(str(cfg["audio_buffer_length"]))
        if self.info:
            self.device_name.set_value(self.info.product.replace(" Wireless Controller", ""))
            self.device_hint.setText(
                f"固件 {self.info.firmware}" if self.info.firmware else "固件未知"
            )
        self.device_audio.set_value("—")
        self._update_summaries()

    def _update_summaries(self) -> None:
        cfg = self.draft
        gain = "自动" if cfg["speaker_gain"] == 0 else str(cfg["speaker_gain"])
        self.audio_card.set_summary(f"增益 {gain} · 缓冲 {cfg['audio_buffer_length']}")
        inactive = "关闭" if cfg["inactive_time"] == 0 else f"{cfg['inactive_time']} 分钟"
        self.power_card.set_summary(
            f"{inactive} · 灯{'关' if cfg['disable_pico_led'] else '开'}"
            f" · 麦克风{'关' if cfg['disable_mic'] else '开'}"
        )
        self.compat_card.set_summary(
            f"{POLL_NAMES[cfg['polling_rate_mode']]} · {MODE_NAMES[cfg['controller_mode']]}"
        )
        if self.info:
            self.device_card.set_summary(
                f"{_signal_text(self.status.get('rssi'))} · 固件 {self.info.firmware or '未知'}"
            )
        else:
            self.device_card.set_summary("等待连接")

    def _update_state(self) -> None:
        connected = self.info is not None and self.device_config is not None
        dirty = connected and not configs_equal(self.draft, self.device_config)
        self.save_btn.setEnabled(connected and not self._busy and dirty)
        self.read_btn.setEnabled(connected and not self._busy)
        self.reset_btn.setEnabled(connected and not self._busy)
        self.reconnect_warning.setVisible(connected and self.needs_reconnect)

        if not connected:
            self.state_label.setText("未连接")
            self.state_label.setStyleSheet(f"color: {MUTED}; font-size: 16px; font-weight: 600;")
            self.state_hint.setText("连接接收器后可以读取和修改设置。")
            return
        if self._busy:
            self.state_label.setText("正在与接收器通信…")
            self.state_label.setStyleSheet(f"color: {AMBER}; font-size: 16px; font-weight: 600;")
            self.state_hint.setText("请稍候，不要拔掉接收器。")
            return
        if dirty:
            self.state_label.setText("有未保存的修改")
            self.state_label.setStyleSheet(f"color: {AMBER}; font-size: 16px; font-weight: 600;")
            self.state_hint.setText("点“保存更改”一次完成；需要时会自动重连。")
        elif self.needs_reconnect:
            self.state_label.setText("等待重新连接")
            self.state_label.setStyleSheet(f"color: {AMBER}; font-size: 16px; font-weight: 600;")
            self.state_hint.setText("设置已保存，但自动重连没完成；请到“设备”页手动重连。")
        elif self.saved:
            self.state_label.setText("已保存")
            self.state_label.setStyleSheet(f"color: {GREEN}; font-size: 16px; font-weight: 600;")
            self.state_hint.setText("已写入接收器，断电后仍保留。")
        else:
            self.state_label.setText("设置与接收器一致")
            self.state_label.setStyleSheet(f"color: {TEXT_SOFT}; font-size: 16px; font-weight: 600;")
            self.state_hint.setText("改完点“保存更改”就行，需要时会自动重连。")

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_state()

    def set_connected(
        self,
        info: DeviceInfo,
        config: dict[str, Any],
        firmware: str,
        status: dict[str, Any],
    ) -> None:
        self.info = info
        self.device_config = config
        self.saved = False
        self.needs_reconnect = False
        self._load_controls(config)
        self._set_enabled(True)
        self.footer.show()
        self.stack.setCurrentIndex(1)
        self.set_status(status)
        self._update_state()

    def set_status(self, status: dict[str, Any]) -> None:
        self.status = status
        self.device_rssi.set_value(_signal_text(status.get("rssi")))
        speaker = status.get("speaker_active")
        mic = status.get("mic_active")
        if speaker is None and mic is None:
            self.device_audio.set_value("未知")
        else:
            self.device_audio.set_value(
                f"外放{'开' if speaker else '关'} · 麦克风{'开' if mic else '关'}"
            )
        self._update_summaries()

    def on_applied(self, result: ApplyResult) -> None:
        self.info = result.info
        self.device_config = result.config
        self.draft = result.config
        self.saved = result.saved
        self.needs_reconnect = bool(result.reconnect_error)
        self._load_controls(result.config)
        if result.status is not None:
            self.set_status(result.status)
        self._update_state()

        if result.reconnect_error:
            InfoBar.warning(
                "设置已保存，但重连没完成",
                "请到“设备”页点“重连 USB”，新设置才会完全生效。",
                parent=self.window(),
                position=InfoBarPosition.TOP_RIGHT,
                duration=5000,
            )
        elif result.reconnected:
            InfoBar.info(
                "已保存并生效",
                "接收器已重新连接，新设置已经生效。",
                parent=self.window(),
                position=InfoBarPosition.TOP_RIGHT,
                duration=2800,
            )
        elif result.saved:
            InfoBar.info(
                "已保存",
                "设置已写入接收器，断电后仍保留。",
                parent=self.window(),
                position=InfoBarPosition.TOP_RIGHT,
                duration=2800,
            )
        else:
            InfoBar.info(
                "已应用",
                "设置已经生效。",
                parent=self.window(),
                position=InfoBarPosition.TOP_RIGHT,
                duration=2800,
            )

    def show_empty(self, detail: str) -> None:
        self.info = None
        self.device_config = None
        self.needs_reconnect = False
        self.empty.set_detail(detail)
        self.footer.hide()
        self.stack.setCurrentIndex(0)
        self._set_enabled(False)
        self._update_state()

    def _set_enabled(self, enabled: bool) -> None:
        self.content.setEnabled(enabled)
        if not enabled:
            self.state_label.setText("未连接")
            self.state_label.setStyleSheet(f"color: {MUTED}; font-size: 16px; font-weight: 600;")
            self.state_hint.setText("连接接收器后可以读取和修改设置。")

    def _reset(self) -> None:
        result = QMessageBox.question(
            self,
            "恢复默认设置",
            "会恢复默认设置并立即写入接收器，必要时自动重连。\n是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            defaults = normalize_config(DEFAULTS)
            self.service.apply(
                defaults,
                save=True,
                reconnect=requires_reconnect(self.device_config, defaults),
            )


class DevicePage(QWidget):
    def __init__(self, service: DeviceService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.info: DeviceInfo | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(16)

        hero = HeroCard()
        hero_top = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(4)
        self.name = QLabel("等待连接")
        self.name.setStyleSheet(f"color: {TEXT}; font-size: 28px; font-weight: 600;")
        left.addWidget(self.name)
        self.subtitle = _label("DS5Dongle 无线接收器")
        left.addWidget(self.subtitle)
        hero_top.addLayout(left, 1)
        hero.body.addLayout(hero_top)
        hero.body.addSpacing(14)

        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(14)
        self.firmware = Metric("固件版本")
        self.rssi = Metric("信号")
        self.audio = Metric("音频输出")
        self.mode = Metric("控制器模式")
        self.vid = Metric("USB 型号")
        self.config_version = Metric("配置格式")
        self.interface = Metric("连接接口")
        self.timestamp = Metric("更新时间")
        self.battery = Metric("电量")
        grid.addWidget(self.firmware, 0, 0)
        grid.addWidget(self.rssi, 0, 1)
        grid.addWidget(self.audio, 0, 2)
        grid.addWidget(self.mode, 1, 0)
        grid.addWidget(self.vid, 1, 1)
        grid.addWidget(self.config_version, 1, 2)
        grid.addWidget(self.interface, 2, 0)
        grid.addWidget(self.timestamp, 2, 1)
        grid.addWidget(self.battery, 2, 2)
        hero.body.addLayout(grid)
        layout.addWidget(hero)

        raw_card = _card("高级信息", "排查问题时使用")
        self.raw = QLabel("—")
        self.raw.setWordWrap(True)
        self.raw.setStyleSheet(
            f"color: {TEXT_SOFT}; font-family: 'Cascadia Mono', 'Consolas';"
            "font-size: 13px; background: #0A1016; border: 1px solid #17232C;"
            "border-radius: 8px; padding: 14px;"
        )
        self.raw.setTextInteractionFlags(Qt.TextSelectableByMouse)
        raw_card.body.addWidget(self.raw)
        layout.addWidget(raw_card)

        actions = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新状态")
        self.refresh_btn.setObjectName("GhostButton")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.service.refresh_status)
        self.reconnect_btn = QPushButton("重连 USB")
        self.reconnect_btn.setObjectName("GhostButton")
        self.reconnect_btn.setCursor(Qt.PointingHandCursor)
        self.reconnect_btn.clicked.connect(self.service.reconnect)
        actions.addWidget(self.refresh_btn)
        actions.addWidget(self.reconnect_btn)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addStretch(1)

    def set_connected(
        self,
        info: DeviceInfo,
        config: dict[str, Any],
        firmware: str,
        status: dict[str, Any],
    ) -> None:
        self.info = info
        self.name.setText(info.product)
        self.subtitle.setText("DS5Dongle 无线接收器")
        self.firmware.set_value(firmware or "未知")
        self.vid.set_value("054C:0DF2" if info.product_id == 0x0DF2 else "054C:0CE6")
        self.interface.set_value(str(info.interface) if info.interface is not None else "—")
        self.config_version.set_value("官方格式")
        self.mode.set_value(MODE_NAMES[config["controller_mode"]])
        self.raw.setText(" ".join(f"{byte:02X}" for byte in pack_config(config)))
        self.battery.set_value("—")
        self.set_status(status)

    def set_battery(self, state: dict[str, Any] | None) -> None:
        if not state:
            self.battery.set_value("—")
        elif state.get("percent") is None:
            self.battery.set_value(str(state.get("label") or "电量未知"))
        else:
            self.battery.set_value(f"{state['percent']}% · {state['label']}")

    def set_status(self, status: dict[str, Any]) -> None:
        self.rssi.set_value(_signal_text(status.get("rssi")))
        speaker = status.get("speaker_active")
        mic = status.get("mic_active")
        if speaker is None and mic is None:
            self.audio.set_value("未知")
        else:
            self.audio.set_value(f"外放{'开' if speaker else '关'} · 麦克风{'开' if mic else '关'}")
        from datetime import datetime

        self.timestamp.set_value(datetime.now().strftime("%H:%M:%S"))

    def set_busy(self, busy: bool) -> None:
        self.refresh_btn.setEnabled(not busy and self.info is not None)
        self.reconnect_btn.setEnabled(not busy and self.info is not None)

    def show_empty(self, detail: str) -> None:
        self.info = None
        self.name.setText("未连接")
        self.subtitle.setText(detail)
        for metric in (
            self.firmware,
            self.rssi,
            self.audio,
            self.mode,
            self.vid,
            self.config_version,
            self.interface,
            self.timestamp,
            self.battery,
        ):
            metric.set_value("—")
        self.raw.setText("—")
        self.refresh_btn.setEnabled(False)
        self.reconnect_btn.setEnabled(False)


class AboutPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(16)

        hero = HeroCard()
        row = QHBoxLayout()
        mark = BrandMark()
        mark.setFixedSize(54, 54)
        row.addWidget(mark, 0, Qt.AlignTop)
        text = QVBoxLayout()
        text.setSpacing(4)
        title = QLabel("DS5 Bridge 控制台")
        title.setStyleSheet(f"color: {TEXT}; font-size: 28px; font-weight: 600;")
        text.addWidget(title)
        text.addWidget(_label("DS5Dongle 接收器 · 本地配置工具"))
        row.addLayout(text, 1)
        hero.body.addLayout(row)
        hero.body.addSpacing(10)
        desc = _label(
            "直接修改接收器设置，不经过浏览器，也不需要联网。不会修改固件。",
            "Muted",
        )
        desc.setWordWrap(True)
        hero.body.addWidget(desc)
        layout.addWidget(hero)

        protocol = _card("技术信息", "排查问题或核对版本时使用")
        protocol_text = _label(
            "配置读写使用 0xF6 / 0xF7，固件版本使用 0xF8，RSSI 与音频状态使用 0xF9，"
            "电量使用标准 DualSense 0x01 输入报文。"
            "配置体严格按官方固件 v0.7.2 的 19 字节布局打包；不兼容 fork 的 30 字节布局。",
            "Muted",
        )
        protocol_text.setWordWrap(True)
        protocol.body.addWidget(protocol_text)
        link = QLabel(
            '<a href="https://github.com/awalol/DS5Dongle" style="color:#6FA8FF;">'
            "github.com/awalol/DS5Dongle</a>"
        )
        link.setOpenExternalLinks(True)
        protocol.body.addWidget(link)
        protocol.body.addWidget(
            _label(
                "独立项目，与 Sony、Flydigi、awalol 无隶属关系；DualSense 是 Sony 的商标。",
                "Caption",
            )
        )
        layout.addWidget(protocol)

        about = _card("版本", "")
        about.body.addWidget(_label(f"应用版本 {APP_VERSION}", "Muted"))
        about.body.addWidget(_label("可与 PlayStation Accessories 同时使用；只改接收器设置，不改手柄配置。", "Muted"))
        about.body.addWidget(_label("适用固件：官方 v0.7.2 / v0.7.2-hotfix（config v5，19 字节）", "Muted"))
        about.body.addWidget(_label("平台：Windows 10/11 · Python / PySide6 / hidapi", "Muted"))
        layout.addWidget(about)
        layout.addStretch(1)


class Sidebar(QWidget):
    nav_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(248)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 24, 20, 20)
        layout.setSpacing(9)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        brand_row.addWidget(BrandMark())
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        title = QLabel("DS5 BRIDGE")
        title.setStyleSheet(
            f"color: {TEXT}; font-size: 15px; font-weight: 700; letter-spacing: 1.4px;"
        )
        subtitle = QLabel("PICO 2W 控制台")
        subtitle.setStyleSheet(
            f"color: {MUTED_2}; font-size: 10px; font-weight: 600; letter-spacing: 1px;"
        )
        brand_text.addWidget(title)
        brand_text.addWidget(subtitle)
        brand_row.addLayout(brand_text, 1)
        layout.addLayout(brand_row)
        layout.addSpacing(22)

        nav_label = QLabel("功能")
        nav_label.setStyleSheet(
            f"color: {MUTED_2}; font-size: 10.5px; font-weight: 700; letter-spacing: 1.4px;"
        )
        layout.addWidget(nav_label)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: list[NavButton] = []
        for index, (label, _) in enumerate(PAGE_META):
            button = NavButton(f"0{index + 1}    {label}")
            self.nav_group.addButton(button, index)
            button.clicked.connect(lambda _=False, i=index: self.nav_requested.emit(i))
            self.nav_buttons.append(button)
            layout.addWidget(button)
        layout.addStretch(1)

        version = QLabel(f"v{APP_VERSION}  ·  本地工具")
        version.setStyleSheet(f"color: {MUTED_2}; font-size: 10.5px; letter-spacing: 0.4px;")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)

    def set_active(self, index: int) -> None:
        if 0 <= index < len(self.nav_buttons):
            self.nav_buttons[index].setChecked(True)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 820)
        self.setMinimumSize(1080, 720)
        self.setStyleSheet(APP_QSS)
        setTheme(Theme.DARK)
        setThemeColor(ACCENT)

        self.service = DeviceService(self)
        self.info: DeviceInfo | None = None
        self._page_index = 0
        self._page_anim: QPropertyAnimation | None = None
        self._fade_page: QWidget | None = None

        root = QWidget()
        root.setObjectName("Root")
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.sidebar = Sidebar()
        root_layout.addWidget(self.sidebar)

        content = QWidget()
        content.setObjectName("Content")
        content.setAttribute(Qt.WA_StyledBackground, True)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(36, 26, 36, 24)
        content_layout.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(16)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        self.title = QLabel(PAGE_META[0][0])
        self.title.setObjectName("PageTitle")
        self.subtitle = QLabel(PAGE_META[0][1])
        self.subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(self.title)
        title_box.addWidget(self.subtitle)
        header.addLayout(title_box, 1)
        self.status_pill = StatusPill()
        self.status_pill.set_status("off", "未连接")
        header.addWidget(self.status_pill, 0, Qt.AlignVCenter)
        self.battery_pill = BatteryPill()
        header.addWidget(self.battery_pill, 0, Qt.AlignVCenter)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setObjectName("GhostButton")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn, 0, Qt.AlignVCenter)
        content_layout.addLayout(header)

        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        content_layout.addWidget(divider)

        self.pages = QStackedWidget()
        self.config_page = ConfigPage(self.service)
        self.device_page = DevicePage(self.service)
        self.about_page = AboutPage()
        self.pages.addWidget(self.config_page)
        self.pages.addWidget(self.device_page)
        self.pages.addWidget(self.about_page)
        content_layout.addWidget(self.pages, 1)

        root_layout.addWidget(content, 1)
        self.setCentralWidget(root)

        self.sidebar.nav_requested.connect(self.switch_page)
        self.sidebar.set_active(0)

        self.service.probe_done.connect(self._on_probe_done)
        self.service.connected.connect(self._on_connected)
        self.service.status_read.connect(self._on_status)
        self.service.battery_changed.connect(self._on_battery)
        self.service.applied.connect(self._on_applied)
        self.service.error.connect(self._on_error)
        self.service.busy_changed.connect(self._on_busy)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(5000)
        self.status_timer.timeout.connect(self._poll_status)
        self.status_timer.start()
        QTimer.singleShot(120, self.service.probe)

    def switch_page(self, index: int) -> None:
        if not 0 <= index < self.pages.count():
            return
        if index == self.pages.currentIndex():
            self.sidebar.set_active(index)
            return
        if self._page_anim is not None:
            self._page_anim.stop()
        if self._fade_page is not None:
            self._fade_page.setGraphicsEffect(None)

        self._page_index = index
        self.pages.setCurrentIndex(index)
        self.sidebar.set_active(index)
        self.title.setText(PAGE_META[index][0])
        self.subtitle.setText(PAGE_META[index][1])

        # A short ease-out fade keeps page switches soft without feeling animated.
        page = self.pages.currentWidget()
        effect = QGraphicsOpacityEffect(page)
        page.setGraphicsEffect(effect)
        effect.setOpacity(0.0)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(170)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda p=page: p.setGraphicsEffect(None))
        self._page_anim = anim
        self._fade_page = page
        anim.start()

    def refresh(self) -> None:
        if self.info:
            self.service.connect(self.info)
        else:
            self.service.probe()

    def _on_probe_done(self, infos: list[DeviceInfo]) -> None:
        supported = [info for info in infos if info.supported]
        if supported:
            # Let the probe task release the single-I/O slot before connecting.
            QTimer.singleShot(0, lambda info=supported[0]: self.service.connect(info))
            return
        detail = "没有找到官方 DS5Dongle。请确认接收器已插好，手柄已开机并完成首次配对。"
        if infos:
            detail = "检测到 Sony 手柄接口，但它没有响应 DS5Dongle 的 0xF8 固件报文。"
        self.info = None
        self.service.watch_battery(None)
        self._on_battery(None)
        self.status_pill.set_status("off", "未连接")
        self.config_page.show_empty(detail)
        self.device_page.show_empty(detail)
        InfoBar.warning(
            "未找到 DS5Dongle",
            detail,
            parent=self,
            position=InfoBarPosition.TOP_RIGHT,
            duration=4200,
        )

    def _on_connected(
        self,
        info: DeviceInfo,
        config: dict[str, Any],
        firmware: str,
        status: dict[str, Any],
    ) -> None:
        self.info = info
        self.status_pill.set_status("ok", f"已连接 · {firmware or '固件未知'}")
        self.config_page.set_connected(info, config, firmware, status)
        self.device_page.set_connected(info, config, firmware, status)
        self.config_page.set_busy(False)
        self.device_page.set_busy(False)

    def _on_status(self, status: dict[str, Any]) -> None:
        self.device_page.set_status(status)
        self.config_page.set_status(status)

    def _on_battery(self, state: dict[str, Any] | None) -> None:
        if state:
            self.battery_pill.set_battery(
                state.get("percent"),
                str(state.get("label") or "电量未知"),
                bool(state.get("charging")),
            )
        else:
            self.battery_pill.set_battery(None)
        self.device_page.set_battery(state)

    def _on_applied(self, result: ApplyResult) -> None:
        self.config_page.on_applied(result)
        self.info = result.info
        firmware = result.firmware or result.info.firmware
        status = result.status if result.status is not None else self.config_page.status
        self.device_page.set_connected(result.info, result.config, firmware, status)
        if result.reconnect_error:
            self.status_pill.set_status("busy", "已保存 · 待重连")
        elif result.reconnected:
            self.status_pill.set_status("ok", "已保存 · 已生效")
        else:
            self.status_pill.set_status("ok", "已保存")
        QTimer.singleShot(1800, self._restore_status)

    def _restore_status(self) -> None:
        if not self.info:
            return
        if self.config_page.needs_reconnect:
            self.status_pill.set_status("busy", "已连接 · 待重连")
        else:
            self.status_pill.set_status("ok", f"已连接 · {self.info.firmware or '固件未知'}")

    def _on_error(self, message: str) -> None:
        InfoBar.error(
            "操作失败",
            message,
            parent=self,
            position=InfoBarPosition.TOP_RIGHT,
            duration=5000,
        )
        if not self.info:
            self.status_pill.set_status("off", "未连接")
            self.service.watch_battery(None)
            self._on_battery(None)
            self.config_page.show_empty(message)
            self.device_page.show_empty(message)
        else:
            self.status_pill.set_status("ok", f"已连接 · {self.info.firmware or '固件未知'}")

    def _on_busy(self, busy: bool) -> None:
        self.config_page.set_busy(busy)
        self.device_page.set_busy(busy)
        self.refresh_btn.setEnabled(not busy)
        if busy:
            self.status_pill.set_status("busy", "正在通信…")
        elif self.info and self.config_page.needs_reconnect:
            self.status_pill.set_status("busy", "已连接 · 待重连")
        elif self.info:
            self.status_pill.set_status("ok", f"已连接 · {self.info.firmware or '固件未知'}")
        else:
            self.status_pill.set_status("off", "未连接")

    def _poll_status(self) -> None:
        if self.info and not self.service.busy:
            self.service.refresh_status()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.service.shutdown()
        super().closeEvent(event)
