# -*- coding: utf-8 -*-
from ds5_bridge.tray import tray_summary


def test_tray_summary_disconnected():
    assert tray_summary(False, "电量未知", "未知") == "未连接"


def test_tray_summary_connected_without_firmware():
    assert tray_summary(True, "82% · 放电中", "未知") == "已连接 · 82% · 放电中"


def test_tray_summary_connected_with_firmware_and_unknown_battery():
    assert tray_summary(True, "电量未知", "1.4.0") == "已连接 · 固件 1.4.0"
