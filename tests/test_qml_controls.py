# -*- coding: utf-8 -*-
"""Toggle switches must write the new value, not the bound (old) one."""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuickControls2 import QQuickStyle

from ds5_bridge.qml_bridge import ThemeModel, UiBridge

QML_DIR = Path(__file__).resolve().parents[1] / "ds5_bridge" / "qml"
TOGGLES = (
    ("ledToggle", "disableLed"),
    ("micToggle", "disableMic"),
    ("usbSnToggle", "usbSn"),
    ("psShortcutToggle", "psShortcut"),
)

_app = None


@pytest.fixture(scope="module")
def page():
    global _app
    QQuickStyle.setStyle("Basic")
    _app = QGuiApplication.instance() or QGuiApplication([])
    bridge = UiBridge()
    theme = ThemeModel()
    engine = QQmlEngine()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.rootContext().setContextProperty("theme", theme)
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_DIR / "ConfigPage.qml")))
    root = component.create()
    assert root is not None, [error.toString() for error in component.errors()]
    try:
        yield bridge, root
    finally:
        root.deleteLater()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        bridge.shutdown()


@pytest.mark.parametrize(("object_name", "field"), TOGGLES)
def test_toggle_switch_writes_new_value(page, object_name, field):
    bridge, root = page
    toggle = root.findChild(QObject, object_name)
    assert toggle is not None
    assert bridge.property(field) is False
    assert toggle.property("checked") is False

    toggle.toggled.emit(True)

    assert bridge.property(field) is True
    assert toggle.property("checked") is True
