# -*- coding: utf-8 -*-
"""System tray integration for the QML console."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

if TYPE_CHECKING:
    from PySide6.QtGui import QWindow

    from .qml_bridge import UiBridge


def tray_summary(connected: bool, battery_text: str, firmware: str) -> str:
    """One-line state for the tray tooltip and disabled menu row."""
    if not connected:
        return "未连接"
    parts = ["已连接"]
    if firmware and firmware != "未知":
        parts.append(f"固件 {firmware}")
    if battery_text and battery_text != "电量未知":
        parts.append(battery_text)
    return " · ".join(parts)


class TrayController(QObject):
    """Keep the app alive when the window closes, and expose a tray menu."""

    def __init__(
        self,
        app: QApplication,
        window: QWindow,
        bridge: UiBridge,
        icon: QIcon,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._app = app
        self._window = window
        self._bridge = bridge
        self._quitting = False
        self._hinted = False

        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("DS5 Bridge 控制台")

        self._menu = QMenu()
        self._show_action = self._menu.addAction("显示控制台")
        self._show_action.triggered.connect(self.show_window)

        self._status_action = self._menu.addAction("未连接")
        self._status_action.setEnabled(False)

        self._menu.addSeparator()
        self._refresh_action = self._menu.addAction("重新检测接收器")
        self._refresh_action.triggered.connect(self._refresh_device)

        self._menu.addSeparator()
        self._quit_action = self._menu.addAction("退出")
        self._quit_action.triggered.connect(self.quit)

        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

        self._bridge.stateChanged.connect(self._refresh)
        self._bridge.batteryChanged.connect(self._refresh)
        self._window.installEventFilter(self)
        self._app.setQuitOnLastWindowClosed(False)
        self._refresh()

    def show_window(self) -> None:
        self._window.showNormal()
        self._window.raise_()
        self._window.requestActivate()

    def hide_window(self) -> None:
        self._window.hide()
        if not self._hinted:
            self._hinted = True
            self._tray.showMessage(
                "DS5 Bridge 控制台",
                "已最小化到托盘，双击图标可以恢复。",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )

    def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        self._tray.hide()
        self._window.close()
        self._app.quit()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            watched is self._window
            and event.type() == QEvent.Type.Close
            and not self._quitting
        ):
            self.hide_window()
            return True
        return super().eventFilter(watched, event)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_window()

    def _refresh(self) -> None:
        summary = tray_summary(
            bool(self._bridge.connected),
            self._bridge.batteryText,
            self._bridge.firmware,
        )
        self._status_action.setText(summary)
        self._tray.setToolTip(f"DS5 Bridge 控制台\n{summary}")
        connected = bool(self._bridge.connected)
        self._refresh_action.setText(
            "重新读取接收器" if connected else "重新检测接收器"
        )
        self._refresh_action.setEnabled(not self._bridge.busy)

    def _refresh_device(self) -> None:
        if self._bridge.busy:
            return
        self._bridge.refresh()


def create_tray(
    app: QApplication,
    window: QWindow,
    bridge: UiBridge,
    icon: QIcon,
) -> TrayController | None:
    """Create the tray when the Windows shell offers one; otherwise keep the
    normal close-to-exit behavior."""
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return None
    return TrayController(app, window, bridge, icon)
