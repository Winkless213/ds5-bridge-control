# -*- coding: utf-8 -*-
"""Small custom widgets that give the console its own visual identity."""

from __future__ import annotations

from typing import Callable, Iterable

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSequentialAnimationGroup,
    QTimer,
    Qt,
    Property,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import SwitchButton

from .theme import ACCENT, ACCENT_2, AMBER, BORDER, GREEN, MUTED, MUTED_2, RED, SURFACE_2, TEXT, TEXT_SOFT


class BrandMark(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(42, 42)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 0, 42, 42)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        gradient = QLinearGradient(0, 0, 42, 42)
        gradient.setColorAt(0, QColor(ACCENT))
        gradient.setColorAt(1, QColor(ACCENT_2))
        painter.fillPath(path, gradient)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(4, 18, 22, 210))
        painter.drawRoundedRect(QRectF(8, 28, 26, 4), 2, 2)
        painter.setBrush(QColor(4, 18, 22, 160))
        painter.drawRoundedRect(QRectF(8, 35, 18, 3), 1.5, 1.5)

        painter.setPen(QColor(4, 18, 22))
        font = QFont("Bahnschrift", 13, QFont.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(7, 6, 28, 20), Qt.AlignCenter, "DS5")


class StatusDot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._color = QColor(MUTED_2)

    def set_state(self, state: str) -> None:
        self._color = QColor({"ok": GREEN, "busy": AMBER, "error": RED}.get(state, MUTED_2))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        glow = QColor(self._color)
        glow.setAlpha(45)
        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(0, 0, 12, 12))
        painter.setBrush(self._color)
        painter.drawEllipse(QRectF(3.5, 3.5, 5, 5))


class StatusPill(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusPill")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.dot = StatusDot()
        self.label = QLabel("未连接")
        self.label.setStyleSheet(f"color: {TEXT_SOFT}; font-size: 12.5px;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 12, 4)
        layout.setSpacing(6)
        layout.addWidget(self.dot)
        layout.addWidget(self.label)
        self._state = "off"

    def set_status(self, state: str, text: str) -> None:
        self._state = state
        self.dot.set_state(state)
        self.label.setText(text)
        self.setProperty("state", "off" if state == "off" else "busy" if state == "busy" else "ok")
        self.style().unpolish(self)
        self.style().polish(self)


class BatteryIcon(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(22, 12)
        self._percent: int | None = None
        self._color = QColor(MUTED_2)

    def set_battery(self, percent: int | None, color: str) -> None:
        self._percent = percent
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(self._color, 1.2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(QRectF(0.6, 1.6, 17.0, 8.8), 2.0, 2.0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._color)
        painter.drawRoundedRect(QRectF(18.4, 4.2, 2.2, 3.6), 0.8, 0.8)
        if self._percent is not None:
            width = 14.0 * max(0, min(100, self._percent)) / 100
            if width > 0:
                painter.drawRoundedRect(QRectF(2.0, 3.0, width, 6.0), 1.0, 1.0)


class BatteryPill(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BatteryPill")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.icon = BatteryIcon()
        self.value = QLabel("—")
        self.value.setStyleSheet(f"color: {TEXT_SOFT}; font-size: 12.5px; font-weight: 600;")
        self.state = QLabel("电量未知")
        self.state.setStyleSheet(f"color: {MUTED_2}; font-size: 11.5px;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 12, 4)
        layout.setSpacing(6)
        layout.addWidget(self.icon)
        layout.addWidget(self.value)
        layout.addWidget(self.state)
        self.setProperty("state", "off")

    def set_battery(self, percent: int | None, label: str = "电量未知", charging: bool = False) -> None:
        if percent is None:
            self.value.setText("—")
            self.state.setText(label or "电量未知")
            state = "low" if label and label != "电量未知" else "off"
            color = AMBER if state == "low" else MUTED_2
        else:
            self.value.setText(f"{percent}%")
            self.state.setText(label)
            if percent <= 20 and not charging:
                state = "low"
                color = AMBER
            elif charging:
                state = "charging"
                color = ACCENT
            else:
                state = "normal"
                color = TEXT_SOFT
        self.icon.set_battery(percent, color)
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 18, 20, 18)
        self.body.setSpacing(4)


class HeroCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HeroCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(24, 16, 24, 16)
        self.body.setSpacing(8)


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.setMaximumHeight(50)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(12)
        accent = QFrame()
        accent.setFixedSize(4, 20)
        accent.setStyleSheet(f"background: {ACCENT}; border-radius: 1px;")
        layout.addWidget(accent, 0, Qt.AlignVCenter)
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        label = QLabel(title)
        label.setObjectName("SectionTitle")
        text_box.addWidget(label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("Caption")
            text_box.addWidget(sub)
        layout.addLayout(text_box)
        layout.addStretch(1)


class Chevron(QWidget):
    """Small hand-drawn chevron with a rotation and a press-scale animation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self._angle = 0.0
        self._scale = 1.0
        self._angle_anim: QPropertyAnimation | None = None
        self._scale_anim: QSequentialAnimationGroup | None = None

    def get_angle(self) -> float:
        return self._angle

    def set_angle(self, value: float) -> None:
        self._angle = float(value)
        self.update()

    angle = Property(float, get_angle, set_angle)

    def get_scale(self) -> float:
        return self._scale

    def set_scale(self, value: float) -> None:
        self._scale = float(value)
        self.update()

    scale = Property(float, get_scale, set_scale)

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        target = 180.0 if expanded else 0.0
        if self._angle_anim is not None:
            self._angle_anim.stop()
        if not animate:
            self.set_angle(target)
            return
        anim = QPropertyAnimation(self, b"angle", self)
        anim.setDuration(220)
        anim.setStartValue(self._angle)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.InOutCubic)
        self._angle_anim = anim
        anim.start()

    def pulse(self) -> None:
        if self._scale_anim is not None:
            self._scale_anim.stop()
        down = QPropertyAnimation(self, b"scale", self)
        down.setDuration(70)
        down.setStartValue(1.0)
        down.setEndValue(0.82)
        down.setEasingCurve(QEasingCurve.OutCubic)
        up = QPropertyAnimation(self, b"scale", self)
        up.setDuration(120)
        up.setStartValue(0.82)
        up.setEndValue(1.0)
        up.setEasingCurve(QEasingCurve.OutCubic)
        group = QSequentialAnimationGroup(self)
        group.addAnimation(down)
        group.addAnimation(up)
        self._scale_anim = group
        group.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)
        painter.scale(self._scale, self._scale)
        pen = QPen(QColor(TEXT_SOFT), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(
            [
                QPointF(-4.5, -1.5),
                QPointF(0, 3.0),
                QPointF(4.5, -1.5),
            ]
        )


class _CollapsibleHeader(QWidget):
    clicked = Signal()

    def __init__(self, title: str, subtitle: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CollapsibleHeader")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)
        self.setCursor(Qt.PointingHandCursor)
        self._pressed = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 6, 8)
        layout.setSpacing(12)
        accent = QFrame()
        accent.setFixedSize(4, 19)
        accent.setStyleSheet(f"background: {ACCENT}; border-radius: 1px;")
        layout.addWidget(accent, 0, Qt.AlignVCenter)
        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        self.title = QLabel(title)
        self.title.setStyleSheet(
            f"color: {TEXT_SOFT}; font-size: 14.5px; font-weight: 600; letter-spacing: 0.7px;"
        )
        text_box.addWidget(self.title)
        self.subtitle = QLabel(subtitle)
        self.subtitle.setObjectName("Caption")
        self.subtitle.setWordWrap(False)
        text_box.addWidget(self.subtitle)
        layout.addLayout(text_box, 1)
        self.summary = QLabel("")
        self.summary.setObjectName("Summary")
        self.summary.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.summary.setMaximumWidth(330)
        layout.addWidget(self.summary, 0)
        self.chevron = Chevron()
        layout.addWidget(self.chevron, 0, Qt.AlignVCenter)

        for child in (accent, self.title, self.subtitle, self.summary, self.chevron):
            child.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        self.chevron.set_expanded(expanded, animate)

    def set_summary(self, text: str) -> None:
        self.summary.setText(text)
        self.summary.setToolTip(text)

    def _set_pressed(self, pressed: bool) -> None:
        self._pressed = pressed
        self.setProperty("pressed", pressed)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._set_pressed(True)
            self.chevron.pulse()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._pressed:
            inside = self.rect().contains(event.position().toPoint())
            self._set_pressed(False)
            if inside:
                self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._pressed:
            self._set_pressed(False)
        super().leaveEvent(event)


class CollapsibleCard(Card):
    """A card whose body folds away, leaving a state summary in the header."""

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        expanded: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._expanded = expanded
        self._anim: QPropertyAnimation | None = None
        self.header = _CollapsibleHeader(title, subtitle)
        self.body.addWidget(self.header)

        self.content = QWidget()
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 2, 0, 0)
        self.content_layout.setSpacing(0)
        self.body.addWidget(self.content)

        self.header.clicked.connect(self.toggle)
        self.header.set_expanded(expanded, animate=False)
        self._apply_expanded(expanded, animate=False)

    def add_row(self, row: QWidget) -> None:
        self.content_layout.addWidget(row)

    def add_widget(self, widget: QWidget) -> None:
        self.content_layout.addWidget(widget)

    def set_summary(self, text: str) -> None:
        self.header.set_summary(text)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded, animate=True)

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        if self._anim is not None:
            self._anim.stop()
            self._anim = None
        self._expanded = expanded
        self.header.set_expanded(expanded, animate)
        if not animate:
            self._apply_expanded(expanded, animate=False)
            return

        if expanded:
            self.content.setMinimumHeight(0)
            self.content.setMaximumHeight(16777215)
            self.content.show()
            self.body.activate()
            width = self.content.width()
            content_height = max(
                1,
                self.content.heightForWidth(width)
                if width > 0
                else self.content.sizeHint().height(),
            )
            # Keep the inner layout at full height while the card clips it.
            # If the content itself is resized every frame, rows reflow and
            # the text visibly jumps during the animation.
            self.content.setFixedHeight(content_height)
            self.body.activate()
            target = max(self.sizeHint().height(), self._collapsed_height())
            start = max(self.height(), self._collapsed_height())
        else:
            if not self.content.isVisible():
                self._apply_expanded(False, animate=False)
                return
            width = self.content.width()
            self.content.setFixedHeight(
                max(
                    self.content.height(),
                    self.content.heightForWidth(width)
                    if width > 0
                    else self.content.sizeHint().height(),
                )
            )
            start = max(self.height(), self._collapsed_height())
            target = self._collapsed_height()

        self.setMaximumHeight(start)
        anim = QPropertyAnimation(self, b"maximumHeight", self)
        anim.setDuration(300 if expanded else 250)
        anim.setStartValue(start)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.OutCubic if expanded else QEasingCurve.InOutCubic)
        anim.finished.connect(lambda e=expanded: self._finish_expand(e))
        self._anim = anim
        anim.start()

    def _collapsed_height(self) -> int:
        margins = self.body.contentsMargins()
        header = max(self.header.height(), self.header.sizeHint().height())
        return header + margins.top() + margins.bottom()

    def _apply_expanded(self, expanded: bool, animate: bool) -> None:
        self.content.setMinimumHeight(0)
        self.content.setMaximumHeight(16777215)
        self.content.setVisible(expanded)
        self.setMaximumHeight(16777215 if expanded else self._collapsed_height())

    def _finish_expand(self, expanded: bool) -> None:
        self._anim = None
        self.content.setMinimumHeight(0)
        self.content.setMaximumHeight(16777215)
        if expanded:
            self.setMaximumHeight(16777215)
        else:
            self.content.hide()
            self.setMaximumHeight(self._collapsed_height())


class SettingRow(QFrame):
    def __init__(
        self,
        title: str,
        description: str,
        control: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Row")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumHeight(66)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(22)

        text = QVBoxLayout()
        text.setSpacing(4)
        label = QLabel(title)
        label.setStyleSheet(f"color: {TEXT}; font-size: 14.5px; font-weight: 500;")
        desc = QLabel(description)
        desc.setObjectName("Description")
        desc.setWordWrap(True)
        desc.setMinimumHeight(18)
        text.addWidget(label)
        if description:
            text.addWidget(desc)
        layout.addLayout(text, 1)
        control.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(control, 0, Qt.AlignRight | Qt.AlignVCenter)


class SliderControl(QWidget):
    value_changed = Signal(int)

    def __init__(
        self,
        minimum: int,
        maximum: int,
        value: int,
        formatter: Callable[[int], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._formatter = formatter or (lambda v: str(v))
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(minimum, maximum)
        self.slider.setValue(value)
        self.slider.setFixedWidth(300)
        self.badge = QLabel(self._formatter(value))
        self.badge.setObjectName("ValueBadge")
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setMinimumWidth(74)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addWidget(self.slider)
        layout.addWidget(self.badge)
        self.slider.valueChanged.connect(self._on_value)

    def _on_value(self, value: int) -> None:
        self.badge.setText(self._formatter(value))
        self.value_changed.emit(value)

    def value(self) -> int:
        return self.slider.value()

    def set_value(self, value: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.badge.setText(self._formatter(value))
        self.slider.blockSignals(False)


class ToggleControl(QWidget):
    checked_changed = Signal(bool)

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.switch = SwitchButton()
        self.switch.setChecked(checked)
        self.switch.setOnText("")
        self.switch.setOffText("")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.switch)
        self.switch.checkedChanged.connect(self.checked_changed.emit)

    def is_checked(self) -> bool:
        return bool(self.switch.isChecked())

    def set_checked(self, checked: bool) -> None:
        self.switch.blockSignals(True)
        self.switch.setChecked(checked)
        self.switch.blockSignals(False)


class PillSelector(QWidget):
    changed = Signal(int)

    def __init__(
        self,
        options: Iterable[str],
        value: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._buttons: list[QPushButton] = []
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for index, text in enumerate(options):
            button = QPushButton(text)
            button.setObjectName("PillButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, i=index: self._choose(i, True))
            self._group.addButton(button, index)
            self._buttons.append(button)
            layout.addWidget(button)
        self.set_value(value, emit=False)

    def _choose(self, index: int, emit: bool) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)
        if emit:
            self.changed.emit(index)

    def value(self) -> int:
        for index, button in enumerate(self._buttons):
            if button.isChecked():
                return index
        return 0

    def set_value(self, value: int, emit: bool = False) -> None:
        index = max(0, min(len(self._buttons) - 1, int(value)))
        self._buttons[index].setChecked(True)
        if emit:
            self.changed.emit(index)


class NavButton(QPushButton):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)
        self.setStyleSheet("text-align: left;")


class Metric(QWidget):
    def __init__(self, label: str, value: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        self.label = QLabel(label)
        self.label.setObjectName("Caption")
        self.value = QLabel(value)
        self.value.setStyleSheet(f"color: {TEXT_SOFT}; font-size: 15px; font-weight: 600;")
        layout.addWidget(self.label)
        layout.addWidget(self.value)

    def set_value(self, value: str) -> None:
        self.value.setText(value)
