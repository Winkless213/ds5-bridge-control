# -*- coding: utf-8 -*-
"""User actions queue behind running HID work; previews coalesce."""
from __future__ import annotations

import threading
import time

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from ds5_bridge.service import DeviceService

_app = None


@pytest.fixture()
def service():
    global _app
    _app = QGuiApplication.instance() or QGuiApplication([])
    value = DeviceService()
    try:
        yield value
    finally:
        value.shutdown()


def wait_idle(service: DeviceService, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QTest.qWait(20)
        if service.idle:
            return
    raise AssertionError("service did not become idle")


def test_actions_wait_for_running_task(service):
    gate = threading.Event()
    order: list[str] = []

    def slow() -> str:
        gate.wait(2.0)
        return "slow"

    service._enqueue("apply", lambda: service._submit(slow, order.append))
    service._enqueue("connect", lambda: service._submit(lambda: "connect", order.append))
    assert service.idle is False
    gate.set()
    wait_idle(service)
    assert order == ["slow", "connect"]


def test_trailing_previews_coalesce(service):
    gate = threading.Event()
    done: list[str] = []

    service._enqueue("apply", lambda: service._submit(lambda: gate.wait(2.0) and "apply", done.append))
    for name in ("p1", "p2", "p3"):
        service._enqueue("preview", lambda n=name: service._submit(lambda: n, done.append, quiet_busy=True))
    gate.set()
    wait_idle(service)
    assert done == ["apply", "p3"]


def test_preview_before_another_action_is_kept(service):
    gate = threading.Event()
    done: list[str] = []

    service._enqueue("apply", lambda: service._submit(lambda: gate.wait(2.0) and "apply", done.append))
    service._enqueue("preview", lambda: service._submit(lambda: "restore", done.append, quiet_busy=True))
    service._enqueue("connect", lambda: service._submit(lambda: "connect", done.append))
    service._enqueue("preview", lambda: service._submit(lambda: "p-new", done.append, quiet_busy=True))
    gate.set()
    wait_idle(service)
    assert done == ["apply", "restore", "connect", "p-new"]


def test_status_poll_is_skipped_while_busy(service):
    from ds5_bridge.protocol import DeviceInfo

    service.info = DeviceInfo(path=b"fake", product_id=0x0DF2, product="x")
    gate = threading.Event()
    service._enqueue("apply", lambda: service._submit(lambda: gate.wait(2.0), lambda _: None))
    assert service.refresh_status() is False
    gate.set()
    wait_idle(service)


def test_test_haptics_opens_a_handle_to_free_the_actuators(service, monkeypatch):
    """The HD test must clear rumble mode itself, not rely on a rumble test.

    Without this the first HD test after a cold start played into actuators
    the motors still owned, so nothing could be felt.
    """
    from ds5_bridge.protocol import DeviceInfo

    opened: list[str] = []
    played: list[object] = []

    class Handle:
        def close(self):
            opened.append("close")

    monkeypatch.setattr("ds5_bridge.service.open_device",
                        lambda path: opened.append("open") or Handle())
    monkeypatch.setattr("ds5_bridge.service.play_test_haptics",
                        lambda device=None: played.append(device) or "pad")
    service.info = DeviceInfo(path=b"fake", product_id=0x0DF2, product="DualSense Edge",
                              firmware="v0.7.2-hotfix-vib.4")
    assert service.test_haptics() is True
    wait_idle(service)
    assert opened == ["open", "close"]
    assert played and played[0] is not None


def test_test_haptics_still_plays_when_the_handle_will_not_open(service, monkeypatch):
    from ds5_bridge.protocol import DeviceInfo, Ds5Error

    played: list[object] = []

    def refuse(path):
        raise Ds5Error("busy")

    monkeypatch.setattr("ds5_bridge.service.open_device", refuse)
    monkeypatch.setattr("ds5_bridge.service.play_test_haptics",
                        lambda device=None: played.append(device) or "pad")
    service.info = DeviceInfo(path=b"fake", product_id=0x0DF2, product="DualSense Edge",
                              firmware="v0.7.2-hotfix-vib.4")
    assert service.test_haptics() is True
    wait_idle(service)
    assert played == [None]
