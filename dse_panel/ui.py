from __future__ import annotations

import math
import time
from datetime import datetime

from PySide6.QtCore import QRectF, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    FluentIcon,
    FluentWindow,
    InfoBar,
    InfoBarPosition,
    NavigationItemPosition,
    PrimaryPushButton,
    ProgressBar,
    PushButton,
    Slider,
    StrongBodyLabel,
    SubtitleLabel,
    TitleLabel,
)

from .config import load_config, record_mapping, record_receiver_setting, save_config
from .device import DeviceInfo, DeviceWorker
from .mapping import SIDE_NAMES, describe_buttons, union_buttons
from .protocol import InputState

BG = "#17181B"
TEXT = "#E8EAED"
MUTED = "#9AA0A6"
ACCENT = "#4F8CFF"
GREEN = "#3DDC97"
AMBER = "#F5B74E"
RED = "#FF6B6B"


def _card(layout, stretch: bool = False) -> CardWidget:
    card = CardWidget()
    card.setLayout(layout)
    if stretch:
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    return card


def _section(text: str) -> SubtitleLabel:
    label = SubtitleLabel(text)
    label.setStyleSheet(f"color: {TEXT};")
    return label


class BatteryRing(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(150, 150)
        self.percent = 0
        self.status = "未连接"
        self.charging = False

    def set_value(self, percent: int, status: str, charging: bool) -> None:
        self.percent = max(0, min(100, percent))
        self.status = status
        self.charging = charging
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(14, 14, self.width() - 28, self.height() - 28)
        painter.setPen(QPen(QColor(255, 255, 255, 26), 11, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 0, 360 * 16)

        if self.charging:
            color = QColor(ACCENT)
        elif self.percent <= 20:
            color = QColor(RED)
        elif self.percent <= 50:
            color = QColor(AMBER)
        else:
            color = QColor(GREEN)
        painter.setPen(QPen(color, 11, Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(rect, 90 * 16, -int(self.percent / 100 * 360 * 16))

        painter.setPen(QColor(TEXT))
        font = QFont("Microsoft YaHei UI", 22, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(0, 42, self.width(), 46), Qt.AlignCenter, f"{self.percent}%")

        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Microsoft YaHei UI", 9))
        painter.drawText(QRectF(0, 92, self.width(), 24), Qt.AlignCenter, self.status)


class StickView(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.title = title
        self.x = 128
        self.y = 128
        self.setFixedSize(150, 176)

    def set_value(self, x: int, y: int) -> None:
        self.x, self.y = x, y
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        center = self.rect().center()
        radius = 58
        painter.setPen(QPen(QColor(255, 255, 255, 34), 2))
        painter.setBrush(QColor(255, 255, 255, 10))
        painter.drawEllipse(center, radius, radius)
        painter.setPen(QPen(QColor(255, 255, 255, 18), 1))
        painter.drawLine(center.x() - radius, center.y(), center.x() + radius, center.y())
        painter.drawLine(center.x(), center.y() - radius, center.x(), center.y() + radius)

        dx = (self.x - 128) / 127 * radius
        dy = (self.y - 128) / 127 * radius
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(ACCENT))
        painter.drawEllipse(center.x() + int(dx), center.y() + int(dy), 12, 12)

        painter.setPen(QColor(MUTED))
        painter.setFont(QFont("Microsoft YaHei UI", 9))
        painter.drawText(QRectF(0, 140, self.width(), 24), Qt.AlignCenter, self.title)


class MetricBar(QWidget):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.value = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {MUTED}; font-size: 12px;")
        self.bar = QProgressBar()
        self.bar.setRange(0, 255)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setStyleSheet(
            "QProgressBar{background: rgba(255,255,255,0.08); border: none; border-radius: 4px;}"
            f"QProgressBar::chunk{{background: {ACCENT}; border-radius: 4px;}}"
        )
        self.value_label = QLabel("0")
        self.value_label.setStyleSheet(f"color: {TEXT}; font-size: 12px;")
        row = QHBoxLayout()
        row.addWidget(self.title_label)
        row.addStretch(1)
        row.addWidget(self.value_label)
        layout.addLayout(row)
        layout.addWidget(self.bar)

    def set_value(self, value: int) -> None:
        self.value = value
        self.bar.setValue(value)
        self.value_label.setText(str(value))


class OverviewPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("OverviewPage")
        self.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background: transparent;} QScrollArea > QWidget > QWidget{background: transparent;}")
        outer.addWidget(scroll)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 28)
        layout.setSpacing(18)
        scroll.setWidget(content)

        layout.addWidget(TitleLabel("设备概览"))
        layout.addWidget(CaptionLabel("读取标准 DualSense 报文；不写入接收器配置。"))

        top = QHBoxLayout()
        top.setSpacing(18)

        battery_layout = QHBoxLayout()
        battery_layout.setContentsMargins(18, 18, 22, 18)
        self.ring = BatteryRing()
        battery_layout.addWidget(self.ring)
        battery_text = QVBoxLayout()
        battery_text.setSpacing(4)
        self.battery_title = StrongBodyLabel("等待手柄")
        self.battery_title.setStyleSheet(f"color: {TEXT}; font-size: 16px;")
        self.battery_sub = CaptionLabel("把接收器插好，手柄开机即可")
        battery_text.addStretch(1)
        battery_text.addWidget(self.battery_title)
        battery_text.addWidget(self.battery_sub)
        battery_text.addStretch(1)
        battery_layout.addLayout(battery_text)
        top.addWidget(_card(battery_layout, True), 1)

        info_layout = QGridLayout()
        info_layout.setContentsMargins(22, 18, 22, 18)
        info_layout.setHorizontalSpacing(18)
        info_layout.setVerticalSpacing(10)
        self.info_values: dict[str, QLabel] = {}
        rows = [
            ("型号", "product"),
            ("固件构建", "firmware"),
            ("硬件 / 固件版本", "versions"),
            ("配对 MAC", "mac"),
            ("设备 ID", "pid"),
            ("连接接口", "path"),
        ]
        for row, (label, key) in enumerate(rows):
            left = CaptionLabel(label)
            left.setStyleSheet(f"color: {MUTED};")
            right = BodyLabel("—")
            right.setStyleSheet(f"color: {TEXT};")
            right.setTextInteractionFlags(Qt.TextSelectableByMouse)
            info_layout.addWidget(left, row, 0)
            info_layout.addWidget(right, row, 1)
            self.info_values[key] = right
        info_layout.setColumnStretch(1, 1)
        top.addWidget(_card(info_layout, True), 1)
        layout.addLayout(top)

        layout.addWidget(_section("实时输入"))
        live_layout = QHBoxLayout()
        live_layout.setContentsMargins(20, 16, 20, 16)
        live_layout.setSpacing(16)
        self.left_stick = StickView("左摇杆")
        self.right_stick = StickView("右摇杆")
        live_layout.addWidget(self.left_stick)
        live_layout.addWidget(self.right_stick)
        bars = QVBoxLayout()
        bars.setSpacing(12)
        self.l2 = MetricBar("L2")
        self.r2 = MetricBar("R2")
        bars.addWidget(self.l2)
        bars.addWidget(self.r2)
        keys_label = CaptionLabel("当前按键")
        keys_label.setStyleSheet(f"color: {MUTED};")
        self.keys_value = BodyLabel("无")
        self.keys_value.setWordWrap(True)
        self.keys_value.setStyleSheet(f"color: {TEXT};")
        bars.addWidget(keys_label)
        bars.addWidget(self.keys_value)
        bars.addStretch(1)
        live_layout.addLayout(bars, 1)
        layout.addWidget(_card(live_layout))

        layout.addStretch(1)

    def update_state(self, state: InputState) -> None:
        self.ring.set_value(state.battery_percent, state.charging_text, state.is_charging)
        self.battery_title.setText(f"{state.battery_percent}% · {state.charging_text}")
        self.battery_sub.setText("接收器已连接" if state.is_charging else "无线连接中")
        self.left_stick.set_value(state.lx, state.ly)
        self.right_stick.set_value(state.rx, state.ry)
        self.l2.set_value(state.l2)
        self.r2.set_value(state.r2)
        names = state.pressed_names
        self.keys_value.setText("  ·  ".join(names) if names else "无")

    def update_info(self, info: DeviceInfo) -> None:
        self.info_values["product"].setText(info.product or "DualSense Edge")
        build = info.firmware_build or "—"
        if info.firmware_fw:
            build += f"  (FW {info.firmware_fw:#06x})"
        self.info_values["firmware"].setText(build)
        self.info_values["versions"].setText(f"{info.firmware_hw:#06x} / {info.firmware_fw:#06x}")
        self.info_values["mac"].setText(info.mac or "—")
        self.info_values["pid"].setText(f"VID_054C&PID_{info.pid:04X}" if info.pid else "—")
        self.info_values["path"].setText("USB HID · 接口 3" if info.path else "—")

    def update_status(self, connected: bool) -> None:
        if not connected:
            self.ring.set_value(0, "未连接", False)
            self.battery_title.setText("等待手柄")
            self.battery_sub.setText("把接收器插好，手柄开机即可")


class RumblePage(QWidget):
    def __init__(self, worker: DeviceWorker, config: dict) -> None:
        super().__init__()
        self.worker = worker
        self.config = config
        self.setObjectName("RumblePage")
        self.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background: transparent;} QScrollArea > QWidget > QWidget{background: transparent;}")
        outer.addWidget(scroll)
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 28)
        layout.setSpacing(18)
        scroll.setWidget(content)

        layout.addWidget(TitleLabel("震动测试"))
        layout.addWidget(CaptionLabel("直接使用手柄原生震动通道；这里只影响本程序发出的测试震动，不拦截游戏。"))

        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(22, 18, 22, 18)
        control_layout.setSpacing(14)
        self.left_slider, self.left_value = self._slider_row(control_layout, "左马达（strong）", int(config["rumble"].get("left", 128)))
        self.right_slider, self.right_value = self._slider_row(control_layout, "右马达（weak）", int(config["rumble"].get("right", 128)))

        presets = QHBoxLayout()
        presets.setSpacing(10)
        for label, value in (("轻", 60), ("中", 120), ("强", 200), ("最大", 255)):
            btn = PushButton(label)
            btn.clicked.connect(lambda _=False, v=value: self._apply_preset(v))
            presets.addWidget(btn)
        presets.addStretch(1)
        control_layout.addLayout(presets)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.test_btn = PrimaryPushButton("测试 1 秒")
        self.test_btn.clicked.connect(self._test_once)
        self.hold_btn = PushButton("按住持续震动")
        self.hold_btn.pressed.connect(self._hold_start)
        self.hold_btn.released.connect(self._hold_stop)
        self.stop_btn = PushButton("停止")
        self.stop_btn.clicked.connect(self._stop)
        actions.addWidget(self.test_btn)
        actions.addWidget(self.hold_btn)
        actions.addWidget(self.stop_btn)
        actions.addStretch(1)
        control_layout.addLayout(actions)
        layout.addWidget(_card(control_layout))

        note_layout = QVBoxLayout()
        note_layout.setContentsMargins(22, 18, 22, 18)
        note_layout.setSpacing(7)
        title = StrongBodyLabel("接收器原生调节（组合键）")
        title.setStyleSheet(f"color: {TEXT};")
        note_layout.addWidget(title)
        guides = [
            "设置键默认关闭：长按 ⚙️（PS5 手柄为 ≡）6 秒切换；长震=开启，短震=关闭。",
            "震动强度：⚙️ + ↑/↓。手柄短震 1 / 2 / 3 次分别对应 1 / 2 / 3 级，默认 2 级。",
            "摇杆灵敏度：⚙️ + L3/R3。短震 1 / 2 / 3 次对应 50% / 100% / 150%。",
            "扳机灵敏度：⚙️ + ←/→（分别对应 L2/R2）。短震=瞬时（增强）开启，长震=恢复默认。",
        ]
        for text in guides:
            label = BodyLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {MUTED};")
            note_layout.addWidget(label)
        hint = CaptionLabel("这些档位保存在接收器里，主机侧读不到当前值；按组合键后用手柄震动次数确认。想按步骤操作，请到左侧“接收器”页。")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {MUTED};")
        note_layout.addWidget(hint)
        layout.addWidget(_card(note_layout))
        layout.addStretch(1)

        self._hold_timer = QTimer(self)
        self._hold_timer.setInterval(500)
        self._hold_timer.timeout.connect(self._hold_tick)

    def _slider_row(self, layout: QVBoxLayout, title: str, value: int) -> tuple[Slider, QLabel]:
        row = QHBoxLayout()
        label = BodyLabel(title)
        label.setStyleSheet(f"color: {TEXT};")
        value_label = BodyLabel(str(value))
        value_label.setStyleSheet(f"color: {MUTED};")
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(value_label)
        layout.addLayout(row)
        slider = Slider(Qt.Horizontal)
        slider.setRange(0, 255)
        slider.setValue(value)
        slider.valueChanged.connect(lambda v: value_label.setText(str(v)))
        layout.addWidget(slider)
        return slider, value_label

    def _apply_preset(self, value: int) -> None:
        self.left_slider.setValue(value)
        self.right_slider.setValue(value)

    def _values(self) -> tuple[int, int]:
        return self.left_slider.value(), self.right_slider.value()

    def _test_once(self) -> None:
        left, right = self._values()
        self.worker.submit_rumble(right, left, 1000)
        self.config["rumble"] = {"left": left, "right": right}
        save_config(self.config)

    def _hold_start(self) -> None:
        left, right = self._values()
        self.worker.submit_rumble(right, left, 10000)
        self._hold_timer.start()

    def _hold_tick(self) -> None:
        left, right = self._values()
        self.worker.submit_rumble(right, left, 1200)

    def _hold_stop(self) -> None:
        self._hold_timer.stop()
        self.worker.stop_rumble()

    def _stop(self) -> None:
        self._hold_timer.stop()
        self.worker.stop_rumble()


RUMBLE_LEVELS = {1: "1 级", 2: "2 级", 3: "3 级"}
STICK_LEVELS = {50: "50%", 100: "100%", 150: "150%"}
TRIGGER_MODES = {"default": "默认", "instant": "瞬时"}
SETTINGS_KEY_MODES = {"on": "开启", "off": "关闭"}


class ReceiverCoachDialog(QDialog):
    """把接收器组合键拆成分步引导；确认只记录到本程序，不写接收器。"""

    def __init__(
        self,
        parent: QWidget,
        worker: DeviceWorker,
        title: str,
        chord: list[str],
        steps: list[str],
        detect_keys: set[str],
        on_confirm,
        hold_seconds: int = 0,
    ) -> None:
        super().__init__(parent)
        self.worker = worker
        self.detect_keys = detect_keys
        self.on_confirm = on_confirm
        self.hold_seconds = hold_seconds
        self._hold_start: float | None = None
        self._hold_done = False
        self._hold_timer = QTimer(self)
        self._hold_timer.setInterval(100)
        self._hold_timer.timeout.connect(self._tick_hold)

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(580, 440)
        self.setStyleSheet("QDialog{background:#17181B;} QLabel{color:#E8EAED;}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(13)

        heading = SubtitleLabel(title)
        heading.setStyleSheet(f"color:{TEXT};")
        layout.addWidget(heading)
        caption = CaptionLabel("接收器没有主机写入接口；请在手柄上完成下面的组合键。")
        caption.setWordWrap(True)
        caption.setStyleSheet(f"color:{MUTED};")
        layout.addWidget(caption)

        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        for i, part in enumerate(chord):
            if i:
                plus = QLabel("+")
                plus.setStyleSheet(f"color:{MUTED}; font-size:18px;")
                key_row.addWidget(plus)
            key_row.addWidget(self._keycap(part))
        key_row.addStretch(1)
        layout.addLayout(key_row)

        for i, step in enumerate(steps, 1):
            label = BodyLabel(f"{i}. {step}")
            label.setWordWrap(True)
            label.setStyleSheet(f"color:{TEXT};")
            layout.addWidget(label)

        panel = QFrame()
        panel.setObjectName("receiverPanel")
        panel.setStyleSheet(
            "QFrame#receiverPanel{background:#202227; border:1px solid #2E3138; border-radius:10px;}"
        )
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 10, 14, 10)
        panel_layout.setSpacing(4)
        live_row = QHBoxLayout()
        live_title = CaptionLabel("当前按键")
        live_title.setStyleSheet(f"color:{MUTED};")
        self.live_label = BodyLabel("等待按键…")
        self.live_label.setStyleSheet(f"color:{TEXT};")
        live_row.addWidget(live_title)
        live_row.addStretch(1)
        live_row.addWidget(self.live_label)
        panel_layout.addLayout(live_row)
        self.detect_label = CaptionLabel("按下组合键后会自动识别（仅供参考）")
        self.detect_label.setWordWrap(True)
        self.detect_label.setStyleSheet(f"color:{MUTED};")
        panel_layout.addWidget(self.detect_label)
        layout.addWidget(panel)

        if hold_seconds:
            self.hold_bar = QProgressBar()
            self.hold_bar.setRange(0, 100)
            self.hold_bar.setTextVisible(False)
            self.hold_bar.setFixedHeight(10)
            self.hold_bar.setStyleSheet(
                "QProgressBar{background: rgba(255,255,255,0.08); border: none; border-radius: 5px;}"
                f"QProgressBar::chunk{{background: {ACCENT}; border-radius: 5px;}}"
            )
            hold_row = QHBoxLayout()
            hold_label = CaptionLabel("6 秒进度")
            hold_label.setStyleSheet(f"color:{MUTED};")
            hold_row.addWidget(hold_label)
            hold_row.addWidget(self.hold_bar, 1)
            layout.addLayout(hold_row)
            start_btn = PushButton("开始 6 秒计时")
            start_btn.clicked.connect(self._start_hold)
            layout.addWidget(start_btn, 0, Qt.AlignLeft)

        hint = CaptionLabel("确认只记录到本程序，不会写入接收器。")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{MUTED};")
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = PushButton("取消")
        cancel.clicked.connect(self.reject)
        confirm = PrimaryPushButton("已听到对应震动，记录")
        confirm.clicked.connect(self._confirm)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        layout.addLayout(buttons)

        self._poll = QTimer(self)
        self._poll.setInterval(100)
        self._poll.timeout.connect(self._refresh_live)
        self._poll.start()

    @staticmethod
    def _keycap(text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        label.setFixedSize(62, 52)
        label.setStyleSheet(
            "QLabel{background:#26282D; border:1px solid #3A3D44; border-radius:10px;"
            f"color:{TEXT}; font-size:18px; font-weight:600;}}"
        )
        return label

    def _refresh_live(self) -> None:
        state = self.worker.latest_state
        names = state.pressed_names if state is not None else []
        self.live_label.setText(" + ".join(names) if names else "等待按键…")
        if self._hold_done:
            return
        pressed = set(names)
        if self.detect_keys and self.detect_keys.issubset(pressed):
            self.detect_label.setText(
                "已检测到设置键，继续按住" if self.hold_seconds else "已检测到组合键"
            )
            self.detect_label.setStyleSheet(f"color:{GREEN};")
        else:
            self.detect_label.setText("按下组合键后会自动识别（仅供参考）")
            self.detect_label.setStyleSheet(f"color:{MUTED};")

    def _start_hold(self) -> None:
        self._hold_start = time.monotonic()
        self._hold_done = False
        self.hold_bar.setValue(0)
        self._hold_timer.start()

    def _tick_hold(self) -> None:
        if self._hold_start is None:
            return
        elapsed = time.monotonic() - self._hold_start
        self.hold_bar.setValue(min(100, int(elapsed / self.hold_seconds * 100)))
        if elapsed >= self.hold_seconds:
            self._hold_timer.stop()
            self._hold_done = True
            self.detect_label.setText("已按住 6 秒，感觉震动后确认")
            self.detect_label.setStyleSheet(f"color:{GREEN};")

    def _confirm(self) -> None:
        self.on_confirm()
        self.accept()


class ReceiverPage(QWidget):
    """接收器档位引导；不伪造主机写入，只记录用户确认值。"""

    VALUE_NAMES = {
        "rumble_level": RUMBLE_LEVELS,
        "stick_left": STICK_LEVELS,
        "stick_right": STICK_LEVELS,
        "trigger_left": TRIGGER_MODES,
        "trigger_right": TRIGGER_MODES,
        "settings_key": SETTINGS_KEY_MODES,
    }

    def __init__(self, worker: DeviceWorker, config: dict) -> None:
        super().__init__()
        self.worker = worker
        self.config = config
        self._status_labels: dict[str, CaptionLabel] = {}
        self.setObjectName("ReceiverPage")
        self.setStyleSheet("background: transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background: transparent;} QScrollArea > QWidget > QWidget{background: transparent;}")
        outer.addWidget(scroll)

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 28)
        layout.setSpacing(18)
        scroll.setWidget(content)

        layout.addWidget(TitleLabel("接收器设置"))
        layout.addWidget(CaptionLabel("把组合键做成一步一步的引导；档位最终以手柄震动为准，程序不写入接收器。"))
        scope = CaptionLabel(
            "DS5 没有官方 PC 配置软件，这一页主要给它用；DSE 建议优先用 PlayStation Accessories，"
            "接收器调节会与官方设置叠加。"
        )
        scope.setWordWrap(True)
        scope.setStyleSheet(f"color:{AMBER};")
        layout.addWidget(scope)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(22, 16, 22, 16)
        info_layout.setSpacing(6)
        info_title = StrongBodyLabel("为什么是引导而不是一键写入")
        info_title.setStyleSheet(f"color:{TEXT};")
        info_body = BodyLabel(
            "接收器只接受手柄上的组合键；USB 侧没有配置写入接口。程序不会伪造“设置成功”，"
            "只记录你确认过的档位，方便下次查看。"
        )
        info_body.setWordWrap(True)
        info_body.setStyleSheet(f"color:{MUTED};")
        info_layout.addWidget(info_title)
        info_layout.addWidget(info_body)
        layout.addWidget(_card(info_layout))

        rumble_row = self._row(
            "rumble_level",
            "档位",
            "短震次数 = 当前档位（1/2/3），默认 2 级。",
            [(1, "1 级"), (2, "2 级"), (3, "3 级")],
        )
        layout.addWidget(self._make_card("震动强度", "⚙️ + ↑/↓；先到 3 级再往下调，不用猜当前值。", [rumble_row]))

        stick_rows = [
            self._row("stick_left", "左摇杆", "短震 1/2/3 次 = 50% / 100% / 150%。", [(50, "50%"), (100, "100%"), (150, "150%")]),
            self._row("stick_right", "右摇杆", "短震 1/2/3 次 = 50% / 100% / 150%。", [(50, "50%"), (100, "100%"), (150, "150%")]),
        ]
        layout.addWidget(self._make_card("摇杆灵敏度", "⚙️ + L3 / R3；反复按，直到短震次数等于目标。", stick_rows))

        trigger_rows = [
            self._row("trigger_left", "左扳机 L2", "短震 = 瞬时；长震 = 默认。", [("default", "默认"), ("instant", "瞬时")]),
            self._row("trigger_right", "右扳机 R2", "短震 = 瞬时；长震 = 默认。", [("default", "默认"), ("instant", "瞬时")]),
        ]
        layout.addWidget(self._make_card("扳机灵敏度", "⚙️ + ← / →；按一次切换，按震动长短判断结果。", trigger_rows))

        settings_row = self._row(
            "settings_key",
            "开关",
            "长按 6 秒切换；长震 = 开启，短震 = 关闭。",
            [("on", "开启"), ("off", "关闭")],
        )
        layout.addWidget(self._make_card("设置键（PS5 为 ≡）", "组合键功能默认关闭；先把它打开，上面的调节才会生效。", [settings_row]))

        footer = CaptionLabel("当前档位主机读不到；卡片显示的是你上次确认的结果，换手柄/重置后请重新引导。")
        footer.setWordWrap(True)
        footer.setStyleSheet(f"color:{MUTED};")
        layout.addWidget(footer)
        layout.addStretch(1)

        self._refresh_status()

    def _row(self, key: str, title: str, hint: str, options: list[tuple[object, str]]) -> QWidget:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 4, 0, 4)
        row_layout.setSpacing(5)

        top = QHBoxLayout()
        name = BodyLabel(title)
        name.setStyleSheet(f"color:{TEXT};")
        status = CaptionLabel("")
        status.setStyleSheet(f"color:{MUTED};")
        self._status_labels[key] = status
        top.addWidget(name)
        top.addStretch(1)
        top.addWidget(status)
        row_layout.addLayout(top)

        hint_label = CaptionLabel(hint)
        hint_label.setWordWrap(True)
        hint_label.setStyleSheet(f"color:{MUTED};")
        row_layout.addWidget(hint_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        for value, label in options:
            btn = PushButton(label)
            btn.clicked.connect(lambda _=False, k=key, v=value: self._open_coach(k, v))
            buttons.addWidget(btn)
        buttons.addStretch(1)
        row_layout.addLayout(buttons)
        return row

    def _make_card(self, title: str, caption: str, rows: list[QWidget]) -> CardWidget:
        layout = QVBoxLayout()
        layout.setContentsMargins(22, 16, 22, 16)
        layout.setSpacing(8)
        heading = StrongBodyLabel(title)
        heading.setStyleSheet(f"color:{TEXT};")
        desc = CaptionLabel(caption)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{MUTED};")
        layout.addWidget(heading)
        layout.addWidget(desc)
        for row in rows:
            layout.addWidget(row)
        return _card(layout)

    def _status_text(self, key: str) -> str:
        receiver = self.config.get("receiver", {})
        value = receiver.get(key)
        if value is None:
            return "未记录"
        label = self.VALUE_NAMES.get(key, {}).get(value, str(value))
        stamp = receiver.get("confirmed", {}).get(key, "")
        return f"上次确认：{label}" + (f" · {stamp}" if stamp else "")

    def _refresh_status(self) -> None:
        for key, label in self._status_labels.items():
            label.setText(self._status_text(key))

    def _record(self, key: str, value: object) -> None:
        record_receiver_setting(self.config, key, value)
        self._refresh_status()

    def _open_coach(self, key: str, value: object) -> None:
        self.build_coach(key, value).exec()

    def build_coach(self, key: str, value: object) -> ReceiverCoachDialog:
        title, chord, steps, detect_keys, hold_seconds = self._coach_spec(key, value)
        return ReceiverCoachDialog(
            self,
            self.worker,
            title,
            chord,
            steps,
            detect_keys,
            on_confirm=lambda: self._record(key, value),
            hold_seconds=hold_seconds,
        )

    def _coach_spec(self, key: str, value: object) -> tuple[str, list[str], list[str], set[str], int]:
        if key == "rumble_level":
            level = int(value)
            label = RUMBLE_LEVELS[level]
            steps = [
                "先按 ⚙️ + ↑，直到手柄连续短震 3 次（最多按 3 次；已经是 3 级就跳过）。",
                f"再按 ⚙️ + ↓ {3 - level} 次，直到短震 {level} 次。",
                f"短震 {level} 次就是 {label}；听到后点下面的确认。",
            ]
            if level == 3:
                steps = [
                    "按 ⚙️ + ↑，直到手柄连续短震 3 次（3 级）。",
                    "短震 3 次就是 3 级；听到后确认。",
                ]
            return f"设置震动强度 · {label}", ["⚙️", "↑ / ↓"], steps, {"Options", "↑"}, 0

        if key in ("stick_left", "stick_right"):
            percent = int(value)
            count = {50: 1, 100: 2, 150: 3}[percent]
            side = "左" if key == "stick_left" else "右"
            button = "L3" if key == "stick_left" else "R3"
            steps = [
                f"反复按 ⚙️ + {button}，每次切换一档。",
                f"直到手柄短震 {count} 次（{percent}%）。",
                "短震 1/2/3 次分别对应 50% / 100% / 150%。",
            ]
            return f"设置{side}摇杆 · {percent}%", ["⚙️", button], steps, {"Options", button}, 0

        if key in ("trigger_left", "trigger_right"):
            mode = str(value)
            label = TRIGGER_MODES[mode]
            side = "左" if key == "trigger_left" else "右"
            trigger = "L2" if key == "trigger_left" else "R2"
            arrow = "←" if key == "trigger_left" else "→"
            steps = [
                f"按一次 ⚙️ + {arrow}（{trigger}）。",
                "短震 = 瞬时（增强）已开启；长震 = 已恢复默认。",
                f"目标是{label}；如果震动与目标不符，再按一次。",
            ]
            return f"设置{side}扳机 {trigger} · {label}", ["⚙️", arrow], steps, {"Options", arrow}, 0

        if key == "settings_key":
            mode = str(value)
            label = SETTINGS_KEY_MODES[mode]
            steps = [
                "按住 ⚙️ 不放 6 秒。",
                "长震 = 设置键已开启；短震 = 已关闭。",
                f"目标是{label}；如果震动与目标不符，再长按 6 秒。",
            ]
            return f"设置键 · {label}", ["⚙️"], steps, {"Options"}, 6

        raise ValueError(f"unknown receiver setting: {key}")


class MappingWizard:
    """两步式只读映射检测：按左背键、按右背键，记录最终上报的按键组合。"""

    def __init__(self, page: "BackButtonsPage") -> None:
        self.page = page
        self.active = False
        self.side = "left"
        self.pressed = False
        self.union: tuple[int, int, int, int] | None = None
        self.deadline = 0.0
        self.baseline: InputState | None = None

    def start(self) -> None:
        self.page.results = {}
        self._begin("left")

    def _begin(self, side: str) -> None:
        self.active = True
        self.side = side
        self.pressed = False
        self.union = None
        self.deadline = time.monotonic() + 15
        self.baseline = self.page.worker.latest_state
        self.page.set_wizard_text(f"请按一下{SIDE_NAMES[side]}（15 秒内）")
        self.page.set_wizard_progress(1 if side == "right" else 0)
        self.page.set_wizard_running(True)

    def on_state(self, state: InputState) -> None:
        if not self.active:
            return
        if state.is_idle:
            if self.pressed and self.union is not None:
                self._finish_side()
            return
        self.pressed = True
        self.union = state.buttons if self.union is None else union_buttons(self.union, state.buttons)

    def tick(self) -> None:
        if not self.active:
            return
        if time.monotonic() > self.deadline and not self.pressed:
            self.active = False
            self.page.set_wizard_running(False)
            self.page.set_wizard_text("检测超时，请点“重新检测”。")
            InfoBar.warning("检测超时", "没有收到背键上报，请确认手柄已连接。", parent=self.page, position=InfoBarPosition.TOP_RIGHT, duration=3000)

    def _finish_side(self) -> None:
        assert self.union is not None
        label = describe_buttons(self.union)
        self.page.results[self.side] = (label, datetime.now().strftime("%H:%M:%S"))
        record_mapping(self.page.config, self.side, label.split(" + ") if label != "无按键" else [])
        self.page.refresh_table()
        if self.side == "left":
            self._begin("right")
        else:
            self.active = False
            self.page.set_wizard_running(False)
            self.page.set_wizard_text("检测完成。映射来自接收器当前实际输出。")
            self.page.set_wizard_progress(2)
            InfoBar.success("检测完成", "已记录左/右背键当前映射。", parent=self.page, position=InfoBarPosition.TOP_RIGHT, duration=3000)


class BackButtonsPage(QWidget):
    def __init__(self, worker: DeviceWorker, config: dict) -> None:
        super().__init__()
        self.worker = worker
        self.config = config
        self.results: dict[str, tuple[str, str]] = {}
        self.setObjectName("BackButtonsPage")
        self.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background: transparent;} QScrollArea > QWidget > QWidget{background: transparent;}")
        outer.addWidget(scroll)
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 28)
        layout.setSpacing(18)
        scroll.setWidget(content)

        layout.addWidget(TitleLabel("背键映射"))
        layout.addWidget(CaptionLabel("只读检测：不修改手柄或接收器的任何配置。"))

        live_layout = QVBoxLayout()
        live_layout.setContentsMargins(22, 18, 22, 18)
        live_layout.setSpacing(10)
        live_layout.addWidget(StrongBodyLabel("原始背键 / Fn 状态"))
        self.live_label = BodyLabel("FN1 —   FN2 —   左背键 —   右背键 —")
        self.live_label.setStyleSheet(f"color: {TEXT}; font-size: 14px;")
        live_layout.addWidget(self.live_label)
        note = CaptionLabel(
            "该接收器把背键转换成普通按键后上报，DSE 原始背键位通常是 0。"
            "下面的检测向导通过“按一次背键→记录最终按键”来还原当前映射。"
        )
        note.setWordWrap(True)
        note.setStyleSheet(f"color: {MUTED};")
        live_layout.addWidget(note)
        layout.addWidget(_card(live_layout))

        wizard_layout = QVBoxLayout()
        wizard_layout.setContentsMargins(22, 18, 22, 18)
        wizard_layout.setSpacing(12)
        wizard_layout.addWidget(StrongBodyLabel("映射检测向导"))
        self.wizard_text = BodyLabel("点击开始，然后按提示依次按左背键、右背键。")
        self.wizard_text.setWordWrap(True)
        self.wizard_text.setStyleSheet(f"color: {TEXT}; font-size: 14px;")
        wizard_layout.addWidget(self.wizard_text)
        self.progress = ProgressBar()
        self.progress.setRange(0, 2)
        self.progress.setValue(0)
        wizard_layout.addWidget(self.progress)
        row = QHBoxLayout()
        self.start_btn = PrimaryPushButton("开始检测")
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn = PushButton("取消")
        self.cancel_btn.clicked.connect(self._cancel)
        self.cancel_btn.setEnabled(False)
        row.addWidget(self.start_btn)
        row.addWidget(self.cancel_btn)
        row.addStretch(1)
        wizard_layout.addLayout(row)
        layout.addWidget(_card(wizard_layout))

        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(22, 18, 22, 18)
        table_layout.setSpacing(10)
        table_layout.addWidget(StrongBodyLabel("已记录的映射"))
        self.table = QTableWidget(2, 3)
        self.table.setHorizontalHeaderLabels(["背键", "映射结果", "检测时间"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setFixedHeight(110)
        self.table.setStyleSheet(
            "QTableWidget{background: transparent; color: #E8EAED; border: 1px solid rgba(255,255,255,0.08);"
            " border-radius: 8px; gridline-color: rgba(255,255,255,0.06);}"
            "QHeaderView::section{background: rgba(255,255,255,0.04); color: #9AA0A6; border: none; padding: 6px;}"
            "QTableWidget::item{padding: 6px;}"
        )
        table_layout.addWidget(self.table)
        layout.addWidget(_card(table_layout))

        guide_layout = QVBoxLayout()
        guide_layout.setContentsMargins(22, 18, 22, 18)
        guide_layout.setSpacing(6)
        guide_layout.addWidget(StrongBodyLabel("修改映射（接收器原生组合键）"))
        g1 = BodyLabel("1. 长按设置键（PS5 手柄为 ≡）6 秒，开启设置功能。")
        g2 = BodyLabel("2. 按“设置键 + 需要设置的背键”，短震表示开始。")
        g3 = BodyLabel("3. 再按目标按键（最多 10 键同时映射），长震表示完成。")
        for label in (g1, g2, g3):
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {MUTED};")
            guide_layout.addWidget(label)
        layout.addWidget(_card(guide_layout))
        layout.addStretch(1)

        self.wizard = MappingWizard(self)
        self.timer = QTimer(self)
        self.timer.setInterval(120)
        self.timer.timeout.connect(self.wizard.tick)
        self.timer.start()
        self.refresh_table()

    def _start(self) -> None:
        self.progress.setValue(0)
        self.cancel_btn.setEnabled(True)
        self.start_btn.setEnabled(False)
        self.wizard.start()

    def _cancel(self) -> None:
        self.wizard.active = False
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress.setValue(0)
        self.wizard_text.setText("已取消。")

    def set_wizard_text(self, text: str) -> None:
        self.wizard_text.setText(text)

    def set_wizard_progress(self, value: int) -> None:
        self.progress.setValue(value)

    def set_wizard_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)

    def refresh_table(self) -> None:
        rows = [("left", "左背键"), ("right", "右背键")]
        for row, (side, name) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            stored = self.config.get("mappings", {}).get(side, {})
            value = self.results.get(side)
            if value:
                text, when = value
            else:
                buttons = stored.get("buttons", []) if isinstance(stored, dict) else []
                text = " + ".join(buttons) if buttons else "未检测"
                when = stored.get("detected_at", "") if isinstance(stored, dict) else ""
            self.table.setItem(row, 1, QTableWidgetItem(text))
            self.table.setItem(row, 2, QTableWidgetItem(when))

    def update_state(self, state: InputState) -> None:
        bits = state.edge_bits
        flags = [
            ("FN1", 0x10),
            ("FN2", 0x20),
            ("左背键", 0x40),
            ("右背键", 0x80),
        ]
        parts = [f"{name} {'●' if bits & mask else '—'}" for name, mask in flags]
        self.live_label.setText("   ".join(parts))
        self.wizard.on_state(state)


class TonePlayer(QThread):
    done = Signal(bool, str)

    def run(self) -> None:  # noqa: D401
        try:
            import numpy as np
            import sounddevice as sd
        except Exception as exc:  # pragma: no cover - 依赖缺失时给出可读错误
            self.done.emit(False, f"缺少音频依赖：{exc}")
            return
        try:
            hostapis = sd.query_hostapis()
            candidate = None
            for i, dev in enumerate(sd.query_devices()):
                if "DualSense" in dev["name"] and dev["max_output_channels"] >= 4:
                    if hostapis[dev["hostapi"]]["name"] == "Windows WASAPI":
                        candidate = i
                        break
                    if candidate is None:
                        candidate = i
            if candidate is None:
                self.done.emit(False, "没有找到 DualSense 音频端点")
                return
            rate = 48000

            def tone(freq: float, seconds: float):
                t = np.arange(int(rate * seconds)) / rate
                return 0.22 * np.sin(2 * math.pi * freq * t)

            zeros = np.zeros(int(rate * 0.2))
            mono = np.concatenate([tone(660, 0.8), zeros, tone(880, 0.8), zeros, tone(520, 0.8)])
            silence = np.zeros_like(mono)
            data = np.stack([mono, mono, silence, silence], axis=1)
            sd.play(data, samplerate=rate, device=candidate, blocking=True)
            self.done.emit(True, "已向 DualSense 扬声器端点播放 3 秒提示音。")
        except Exception as exc:
            self.done.emit(False, f"播放失败：{exc}")


class AudioPage(QWidget):
    def __init__(self, worker: DeviceWorker, config: dict) -> None:
        super().__init__()
        self.worker = worker
        self.config = config
        self._player: TonePlayer | None = None
        self.setObjectName("AudioPage")
        self.setStyleSheet("background: transparent;")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background: transparent;} QScrollArea > QWidget > QWidget{background: transparent;}")
        outer.addWidget(scroll)
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 28)
        layout.setSpacing(18)
        scroll.setWidget(content)

        layout.addWidget(TitleLabel("扬声器"))
        layout.addWidget(CaptionLabel("接收器已暴露音频端点，但实测不转发扬声器声道。"))

        status_layout = QVBoxLayout()
        status_layout.setContentsMargins(22, 18, 22, 18)
        status_layout.setSpacing(8)
        status_layout.addWidget(StrongBodyLabel("当前结论"))
        conclusion = BodyLabel(
            "2026-10-21 复测：先发送内部扬声器路由（audio_control=0x03）、音量 0x64、+6dB 预放（audio_control2=0x02），"
            "用户握持手柄时播放 3 秒旋律，手柄扬声器仍然无声；同一轮震动通道正常。"
            "结论：该接收器只转发了触觉声道，没有把扬声器声道（0/1）转发到手柄。"
        )
        conclusion.setWordWrap(True)
        conclusion.setStyleSheet(f"color: {TEXT};")
        status_layout.addWidget(conclusion)
        hint = CaptionLabel("如果是直连 DualSense 或换用支持音频透传的接收器，可再用下面的按钮验证。")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {MUTED};")
        status_layout.addWidget(hint)
        layout.addWidget(_card(status_layout))

        control_layout = QVBoxLayout()
        control_layout.setContentsMargins(22, 18, 22, 18)
        control_layout.setSpacing(12)
        row = QHBoxLayout()
        row.addWidget(BodyLabel("手柄扬声器音量"))
        row.addStretch(1)
        initial_volume = min(100, max(0, int(config["audio"].get("speaker_volume", 100))))
        self.volume_value = BodyLabel(f"{initial_volume}%")
        self.volume_value.setStyleSheet(f"color: {MUTED};")
        row.addWidget(self.volume_value)
        control_layout.addLayout(row)
        self.volume = Slider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(initial_volume)
        self.volume.valueChanged.connect(lambda v: self.volume_value.setText(f"{v}%"))
        control_layout.addWidget(self.volume)
        actions = QHBoxLayout()
        apply_btn = PushButton("启用扬声器通路")
        apply_btn.clicked.connect(self._apply_volume)
        test_btn = PrimaryPushButton("播放 3 秒提示音")
        test_btn.clicked.connect(self._test_tone)
        actions.addWidget(apply_btn)
        actions.addWidget(test_btn)
        actions.addStretch(1)
        control_layout.addLayout(actions)
        layout.addWidget(_card(control_layout))
        layout.addStretch(1)

    @staticmethod
    def _raw_volume(percent: int) -> int:
        if percent <= 0:
            return 0
        return int(round(0x3D + (0x64 - 0x3D) * percent / 100))

    def _send_audio_path(self) -> None:
        percent = self.volume.value()
        self.worker.submit_output(
            speaker_volume=self._raw_volume(percent),
            audio_control=0x03,
            audio_control2=0x02,
        )

    def _apply_volume(self) -> None:
        self.config["audio"] = {"speaker_volume": self.volume.value()}
        save_config(self.config)
        self._send_audio_path()
        InfoBar.success("已发送", "内部扬声器路由和音量已写入输出报文。", parent=self, position=InfoBarPosition.TOP_RIGHT, duration=2500)

    def _test_tone(self) -> None:
        self._send_audio_path()
        QTimer.singleShot(180, self._start_tone)

    def _start_tone(self) -> None:
        self._player = TonePlayer(self)
        self._player.done.connect(self._on_tone_done)
        self._player.start()

    def _on_tone_done(self, ok: bool, message: str) -> None:
        if ok:
            InfoBar.info("已播放", message, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=4000)
        else:
            InfoBar.error("播放失败", message, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=4000)


class AboutPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("AboutPage")
        self.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 28)
        layout.setSpacing(18)
        layout.addWidget(TitleLabel("关于"))
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(22, 18, 22, 18)
        card_layout.setSpacing(8)
        card_layout.addWidget(StrongBodyLabel("DSE Control 0.1"))
        body = BodyLabel(
            "面向 DualSense Edge + GuliKit 悟空2 接收器的只读控制台。"
            "提供电量、原生震动测试、接收器档位引导、背键映射检测和扬声器诊断。"
        )
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {TEXT};")
        card_layout.addWidget(body)
        notes = [
            "协议依据：Linux hid-playstation 的 DualSense 输入/输出报文布局。",
            "映射检测只读取最终上报的按键，不修改接收器配置。",
            "接收器内置震动强度/摇杆/扳机灵敏度/设置键可用组合键调节，程序在“接收器”页提供分步引导；主机侧没有配置写入接口，也读不到当前档位。",
        ]
        for note in notes:
            label = CaptionLabel("· " + note)
            label.setWordWrap(True)
            label.setStyleSheet(f"color: {MUTED};")
            card_layout.addWidget(label)
        layout.addWidget(_card(card_layout))
        layout.addStretch(1)


class MainWindow(FluentWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DSE Control · GuliKit 悟空2")
        self.resize(1180, 820)
        self.setMinimumSize(1000, 700)
        self.setMicaEffectEnabled(False)
        self.setStyleSheet("FluentWindow{background-color: #17181B;}")
        self.stackedWidget.setStyleSheet("QStackedWidget{background-color: #17181B;}")
        self.config = load_config()
        self.worker = DeviceWorker()

        self.overview = OverviewPage()
        self.rumble = RumblePage(self.worker, self.config)
        self.receiver = ReceiverPage(self.worker, self.config)
        self.back = BackButtonsPage(self.worker, self.config)
        self.audio = AudioPage(self.worker, self.config)
        self.about = AboutPage()

        self.addSubInterface(self.overview, FluentIcon.HOME, "概览")
        self.addSubInterface(self.rumble, FluentIcon.SPEED_HIGH, "震动")
        self.addSubInterface(self.receiver, FluentIcon.SETTING, "接收器")
        self.addSubInterface(self.back, FluentIcon.GAME, "背键")
        self.addSubInterface(self.audio, FluentIcon.VOLUME, "扬声器")
        self.addSubInterface(self.about, FluentIcon.INFO, "关于", NavigationItemPosition.BOTTOM)

        self.worker.stateChanged.connect(self._on_state)
        self.worker.infoChanged.connect(self.overview.update_info)
        self.worker.statusChanged.connect(self._on_status)
        self.worker.logMessage.connect(self._on_log)
        self.worker.start()

    def _on_state(self, state: InputState) -> None:
        self.overview.update_state(state)
        self.back.update_state(state)

    def _on_status(self, connected: bool, message: str) -> None:
        self.overview.update_status(connected)
        if connected:
            InfoBar.success("设备已连接", message, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=2500)
        else:
            InfoBar.warning("设备断开", message, parent=self, position=InfoBarPosition.TOP_RIGHT, duration=3000)

    def _on_log(self, message: str) -> None:
        # 目前只用于诊断输出，避免 UI 噪声。
        pass

    def closeEvent(self, event) -> None:  # noqa: N802
        self.worker.shutdown()
        self.worker.wait(2000)
        save_config(self.config)
        super().closeEvent(event)
