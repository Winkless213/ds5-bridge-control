# -*- coding: utf-8 -*-
"""What the console shows for real-world battery sequences."""
from __future__ import annotations

from ds5_bridge.battery import JUMP_HOLD_S, BatteryTracker
from ds5_bridge.protocol import parse_battery

POWER_ONLY = 0x10  # b54 while charging from a power-only cable (captured live)


def reading(battery: int, flags: int = 0x00) -> dict:
    raw = bytearray(64)
    raw[0] = 0x01
    raw[53] = battery
    raw[54] = flags
    return parse_battery(bytes(raw))


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_charging_then_error_while_plugged_reads_full():
    tracker = BatteryTracker(Clock())
    assert tracker.update(reading(0x19, POWER_ONLY)).label == "充电中"
    view = tracker.update(reading(0xF0, POWER_ONLY))
    assert view.percent == 100
    assert view.label == "已充满"
    assert view.kind == "full"
    assert "0xF0" in view.note
    # Stays full for as long as the controller keeps reporting the error.
    assert tracker.update(reading(0xF0, POWER_ONLY)).label == "已充满"


def test_complete_state_reads_full():
    tracker = BatteryTracker(Clock())
    view = tracker.update(reading(0x20, POWER_ONLY))
    assert (view.percent, view.label, view.kind) == (100, "已充满", "full")


def test_error_at_full_level_reads_full_without_history():
    tracker = BatteryTracker(Clock())
    view = tracker.update(reading(0xFA, POWER_ONLY))
    assert (view.percent, view.label) == (100, "已充满")


def test_real_charging_error_keeps_last_percent():
    tracker = BatteryTracker(Clock())
    tracker.update(reading(0x14, POWER_ONLY))
    view = tracker.update(reading(0xF4, POWER_ONLY))
    assert view.label == "充电异常"
    assert view.kind == "error"
    assert view.percent == 45  # last trustworthy value, not an empty ring


def test_error_without_any_history_has_no_percent():
    tracker = BatteryTracker(Clock())
    view = tracker.update(reading(0xF0, POWER_ONLY))
    assert view.percent is None
    assert view.label == "充电异常"


def test_temperature_error_is_named():
    tracker = BatteryTracker(Clock())
    tracker.update(reading(0x05))
    view = tracker.update(reading(0xB5))
    assert view.label == "温度异常"
    assert view.percent == 55


def test_big_drop_is_held_until_it_persists():
    clock = Clock()
    tracker = BatteryTracker(clock)
    tracker.update(reading(0x29, POWER_ONLY))  # full
    # Unplugged; the gauge briefly reports level 0.
    view = tracker.update(reading(0x00))
    assert view.percent == 100
    assert view.label == "已充满"
    assert "确认" in view.note or "采用" in view.note
    clock.now += JUMP_HOLD_S / 2
    assert tracker.update(reading(0x00)).percent == 100
    # The real value arrives before the hold expires: shown at once.
    view = tracker.update(reading(0x09))
    assert (view.percent, view.label, view.note) == (95, "使用中", "")


def test_big_drop_is_accepted_after_hold():
    clock = Clock()
    tracker = BatteryTracker(clock)
    tracker.update(reading(0x08))
    assert tracker.update(reading(0x01)).percent == 85
    clock.now += JUMP_HOLD_S + 1
    view = tracker.update(reading(0x01))
    assert (view.percent, view.label, view.kind) == (15, "电量低", "low")


def test_small_steps_are_immediate():
    tracker = BatteryTracker(Clock())
    tracker.update(reading(0x05))
    assert tracker.update(reading(0x04)).percent == 45
    assert tracker.update(reading(0x14, POWER_ONLY)).label == "充电中"
    assert tracker.update(reading(0x16, POWER_ONLY)).percent == 65


def test_reset_forgets_history():
    tracker = BatteryTracker(Clock())
    tracker.update(reading(0x19, POWER_ONLY))
    tracker.reset()
    view = tracker.update(reading(0xF0, POWER_ONLY))
    assert view.label == "充电异常"
    assert view.percent is None
