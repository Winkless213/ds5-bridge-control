# -*- coding: utf-8 -*-
"""Background status refreshes must not make the UI look busy."""
from __future__ import annotations

import time

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest

from ds5_bridge.service import DeviceService

_app = None


@pytest.fixture(scope="module")
def service():
    global _app
    _app = QGuiApplication.instance() or QGuiApplication([])
    value = DeviceService()
    try:
        yield value
    finally:
        value.shutdown()


def run_task(service: DeviceService, quiet: bool) -> tuple[list[int], list[bool]]:
    results: list[int] = []
    busy: list[bool] = []
    service.busy_changed.connect(busy.append)
    try:
        assert service._submit(lambda: 7, results.append, quiet_busy=quiet)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            QTest.qWait(20)
            if results and not service._running:
                break
    finally:
        service.busy_changed.disconnect(busy.append)
    return results, busy


def test_foreground_task_reports_busy(service):
    results, busy = run_task(service, quiet=False)
    assert results == [7]
    assert busy == [True, False]
    assert service.busy is False


def test_background_task_stays_quiet(service):
    results, busy = run_task(service, quiet=True)
    assert results == [7]
    assert busy == []
    assert service.busy is False
