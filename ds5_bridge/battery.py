# -*- coding: utf-8 -*-
"""Turn raw DualSense battery readings into a steady display state.

``parse_battery`` reports exactly what the controller sends. Two quirks make
that unsuitable for direct display:

* Some controllers report 0xF ("charging error") instead of 0x2 ("complete")
  once a charge finishes while the cable is still attached.
* A single reading can be implausible (e.g. 90% -> 5%). A real battery moves
  one 10% step at a time, so large jumps must persist before they are shown.

``BatteryTracker`` keeps the last trustworthy reading, applies both rules and
explains itself in ``note``; the service logs every raw change next to the
shown value so the rules can be checked against real controllers.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable

from .protocol import POWER_CHARGING, POWER_COMPLETE

# Charging at 95%+ followed by an error state while still plugged in is
# treated as a finished charge.
FULL_AFTER_LEVEL = 9
# A change of this many percentage points must persist for JUMP_HOLD_S
# seconds before it replaces the shown value.
JUMP_POINTS = 30
JUMP_HOLD_S = 60.0


@dataclass(frozen=True, slots=True)
class BatteryView:
    percent: int | None
    label: str
    kind: str  # normal / low / charging / full / error
    charging: bool
    plugged: bool
    raw: int
    flags: int
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _looks_full(reading: dict[str, Any] | None) -> bool:
    if reading is None:
        return False
    if reading["state"] == POWER_COMPLETE:
        return True
    return reading["state"] == POWER_CHARGING and reading["level"] >= FULL_AFTER_LEVEL


class BatteryTracker:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._good: dict[str, Any] | None = None
        self._shown: BatteryView | None = None
        self._jump_since: float | None = None

    def reset(self) -> None:
        self._good = None
        self._shown = None
        self._jump_since = None

    @property
    def shown(self) -> BatteryView | None:
        return self._shown

    def update(self, reading: dict[str, Any]) -> BatteryView:
        if reading.get("percent") is None:
            self._jump_since = None
            view = self._abnormal(reading)
        else:
            view = BatteryView(
                percent=reading["percent"],
                label=reading["label"],
                kind=reading["kind"],
                charging=bool(reading["charging"]),
                plugged=bool(reading["plugged"]),
                raw=reading["raw"],
                flags=reading["flags"],
            )
            view, accepted = self._settle(view)
            if accepted:
                self._good = reading
        self._shown = view
        return view

    def _abnormal(self, reading: dict[str, Any]) -> BatteryView:
        code = f"0x{reading['raw']:02X}"
        name = reading["label"]
        plugged = bool(reading["plugged"])
        level = reading["level"]
        if plugged and (_looks_full(self._good) or FULL_AFTER_LEVEL <= level <= 10):
            return BatteryView(
                percent=100,
                label="已充满",
                kind="full",
                charging=False,
                plugged=True,
                raw=reading["raw"],
                flags=reading["flags"],
                note=f"手柄报告 {code}（{name}），充电器仍连接且之前已充到 95% 以上，按已充满显示",
            )
        last = self._shown.percent if self._shown is not None else None
        if last is None and self._good is not None:
            last = self._good["percent"]
        return BatteryView(
            percent=last,
            label=name,
            kind="error",
            charging=False,
            plugged=plugged,
            raw=reading["raw"],
            flags=reading["flags"],
            note=f"手柄报告 {code}（{name}）",
        )

    def _settle(self, view: BatteryView) -> tuple[BatteryView, bool]:
        shown = self._shown
        if (
            shown is None
            or shown.percent is None
            or abs(view.percent - shown.percent) < JUMP_POINTS  # type: ignore[operator]
        ):
            self._jump_since = None
            return view, True
        now = self._clock()
        if self._jump_since is None:
            self._jump_since = now
        if now - self._jump_since >= JUMP_HOLD_S:
            self._jump_since = None
            return view, True
        held = replace(
            shown,
            note=f"读数从 {shown.percent}% 跳到 {view.percent}%，稳定 {int(JUMP_HOLD_S)} 秒后才采用",
        )
        return held, False
