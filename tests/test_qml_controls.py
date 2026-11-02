# -*- coding: utf-8 -*-
"""Toggle switches must write the new value, not the bound (old) one."""
from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent, QQmlEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest

from ds5_bridge.protocol import DEFAULTS, DeviceInfo, normalize_config
from ds5_bridge.qml_bridge import ThemeModel, UiBridge

QML_DIR = Path(__file__).resolve().parents[1] / "ds5_bridge" / "qml"
TOGGLES = (
    ("ledToggle", "disableLed"),
    ("micToggle", "disableMic"),
    ("speakerToggle", "disableSpeaker"),
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


def test_gain_badge_grows_with_its_text():
    """A RowLayout drives width, so the badge must size itself via implicitWidth.

    Binding plain `width` leaves the box frozen at whatever the first (shorter)
    label needed, and the longer one spills over the "×" next to it. Only a real
    window lays the row out, so this builds Main.qml instead of using ``page``.
    """
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication.instance() or QGuiApplication([])
    bridge = UiBridge()
    bridge.service.preview = lambda config: True
    bridge.service.watch_battery = lambda path: None
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.rootContext().setContextProperty("theme", ThemeModel())
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    window = engine.rootObjects()[0]
    window.resize(1280, 820)
    try:
        firmware = "v0.7.2-hotfix"
        info = DeviceInfo(path=b"fake", product_id=0x0DF2, product="DualSense Edge",
                          firmware=firmware)
        # A saved non-default gain hides the badge at connect, and the layout
        # then freezes its width; that is the state a real user starts from.
        saved = normalize_config(dict(DEFAULTS, haptics_gain=1.4))
        bridge._on_connected(info, saved, firmware, {"rssi": -50})
        badge = window.findChild(QObject, "gainBadge")
        assert badge is not None
        label = next(child for child in badge.children() if child.property("text") is not None)

        # qWait, not processEvents: the RowLayout only overwrites width during a
        # real layout pass, and that is what breaks a plain `width:` binding.
        QTest.qWait(50)
        bridge.setValue("hapticsGain", 1.6)  # "试用中 · 未保存", the longest label
        QTest.qWait(50)

        assert label.property("text") == "试用中 · 未保存"
        assert badge.property("width") >= label.property("implicitWidth")
    finally:
        window.deleteLater()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        bridge.shutdown()


def test_row_descriptions_moved_into_hover_tooltips(page):
    """Explanations stay available but off the page until asked for."""
    _bridge, root = page
    row = root.findChild(QObject, "audioGainRow")
    assert row is not None
    assert row.property("desc"), "the row still carries its explanation"
    # No always-on description text: the row is title + control only.
    texts = [c.property("text") for c in _descendants(row) if c.property("text")]
    assert row.property("desc") not in texts
    tip = row.findChild(QObject, "rowTip")
    assert tip is not None and tip.property("text") == row.property("desc")


def test_haptics_is_two_parallel_folds_open_by_default(page):
    """触觉反馈 is two sibling folds, both open, with nothing folded inside."""
    _bridge, root = page
    hd = root.findChild(QObject, "hdCard")
    rumble = root.findChild(QObject, "rumbleCard")
    assert hd is not None and rumble is not None
    assert hd.parentItem() is rumble.parentItem()
    assert hd.property("open") and rumble.property("open")
    assert root.findChild(QObject, "advancedToggle") is None


@pytest.mark.parametrize(("card", "name"), (
    # The receiver only forwards the haptics channels, so speaker_gain sets how
    # hard HD haptics hit: it belongs beside the gain, not with the speaker.
    ("hdCard", "audioGainRow"),
    ("hdCard", "heroTestHapticsButton"),
    ("rumbleCard", "legacyRumbleToggle"),
    ("rumbleCard", "heroTestRumbleButton"),
    # Rarely touched, so they sit in the fold that stays closed.
    ("perfCard", "triggerReduceRow"),
    ("perfCard", "audioBufferRow"),
    # Measured rate and the speed that drives it read together.
    ("rateCard", "pollingRow"),
))
def test_settings_sit_in_their_card(page, card, name):
    _bridge, root = page
    fold = root.findChild(QObject, card)
    assert fold is not None
    assert fold.findChild(QObject, name) is not None


@pytest.fixture()
def vib_window():
    """Main.qml in a real window, connected to the vib firmware.

    Only a real window runs the layout pass that sets y and height.
    """
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication.instance() or QGuiApplication([])
    bridge = UiBridge()
    bridge.service.preview = lambda config: True
    bridge.service.watch_battery = lambda path: None
    bridge.service.claim_lights = lambda: True
    # Main.qml's Component.onCompleted calls bridge.start(), which probes the
    # real HID bus. That probe is the one queued task that reports busy, and a
    # busy service disables every "试一下" button, so stub it out.
    bridge.service.probe = lambda quiet=False: True
    theme = ThemeModel()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bridge", bridge)
    engine.rootContext().setContextProperty("theme", theme)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    window = engine.rootObjects()[0]
    window.resize(1280, 820)
    try:
        firmware = "v0.7.2-hotfix-vib.4"
        info = DeviceInfo(path=b"fake", product_id=0x0DF2, product="DualSense Edge",
                          firmware=firmware)
        bridge._on_connected(info, normalize_config(dict(DEFAULTS)), firmware, {"rssi": -50})
        QTest.qWait(600)  # past DeckCard's 280 ms height animation
        yield bridge, window
    finally:
        window.deleteLater()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        bridge.shutdown()


def _level(a, b):
    return (a.property("y"), a.property("height")) == (b.property("y"), b.property("height"))


def test_cards_in_a_row_fold_together_and_stay_level(vib_window):
    """Folding one of two side-by-side cards alone left a hole under it."""
    _bridge, window = vib_window
    hd, rumble = window.findChild(QObject, "hdCard"), window.findChild(QObject, "rumbleCard")
    power, perf = window.findChild(QObject, "powerCard"), window.findChild(QObject, "perfCard")
    assert None not in (hd, rumble, power, perf)
    open_height = hd.property("height")
    assert hd.property("open") and _level(hd, rumble)
    assert not power.property("open") and _level(power, perf)

    rumble.toggleRequested.emit()
    perf.toggleRequested.emit()
    QTest.qWait(600)

    assert not hd.property("open") and _level(hd, rumble)
    assert hd.property("height") < open_height
    assert power.property("open") and _level(power, perf)


def test_rate_card_spans_the_row_and_always_shows(vib_window):
    """回报率 is read-only live data: full width, and never folded away."""
    _bridge, window = vib_window
    rate = window.findChild(QObject, "rateCard")
    hd, power = window.findChild(QObject, "hdCard"), window.findChild(QObject, "powerCard")
    assert None not in (rate, hd, power)
    # Spans both columns, so it is wider than a card in a two-up row.
    assert rate.property("width") > hd.property("width") * 1.5
    # Sits between the haptics row and the system row. Each card's own y is
    # relative to the row holding it, so compare in window coordinates.
    top = lambda item: item.mapToItem(None, 0, 0).y()
    assert top(hd) < top(rate) < top(power)
    assert rate.findChild(QObject, "reportRateValue") is not None


def test_rate_samples_on_the_config_page_too(vib_window):
    """Sampling used to start only on the device page (`win.page === 1`).

    The config page now shows the same live readout, so gating on the device
    page left its card stuck at 已停止 with an empty chart.
    """
    _bridge, window = vib_window
    window.setProperty("page", 0)
    QTest.qWait(200)
    assert window.property("rateActive"), "config page must keep sampling"
    window.setProperty("page", 2)
    QTest.qWait(200)
    assert not window.property("rateActive"), "about page has no readout"


def test_rate_card_draws_the_same_chart_as_the_device_page(vib_window):
    """One RateChart component, so the two pages cannot drift apart."""
    _bridge, window = vib_window
    rate = window.findChild(QObject, "rateCard")
    chart = rate.findChild(QObject, "rateChart")
    assert chart is not None and chart.property("height") > 0
    window.setProperty("page", 1)
    QTest.qWait(300)
    device = window.findChild(QObject, "devicePage")
    assert device is not None and device.findChild(QObject, "rateChart") is not None


def test_rate_card_stays_put_when_rows_fold(vib_window):
    """Folding the settings rows must not take the live readout with them."""
    _bridge, window = vib_window
    rate = window.findChild(QObject, "rateCard")
    height = rate.property("height")
    page = window.findChild(QObject, "configPage")
    page.setProperty("hapticsRowOpen", False)
    page.setProperty("systemRowOpen", False)
    QTest.qWait(600)
    assert rate.property("height") == height
    assert rate.findChild(QObject, "reportRateValue") is not None


@pytest.mark.parametrize(("object_name", "method"), (
    ("heroTestHapticsButton", "test_haptics"),
    ("heroTestRumbleButton", "test_rumble"),
))
def test_test_button_plays_its_own_effect(vib_window, object_name, method):
    """Both cards' "试一下" are live once a receiver is connected and idle."""
    bridge, window = vib_window
    calls: list[str] = []
    setattr(bridge.service, method, lambda: calls.append(method) or True)
    button = window.findChild(QObject, object_name)
    assert button is not None and button.property("enabled")
    button.clicked.emit()
    assert calls == [method]


def _descendants(item):
    for child in item.childItems():
        yield child
        yield from _descendants(child)


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
