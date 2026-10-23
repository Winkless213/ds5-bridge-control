# -*- coding: utf-8 -*-
"""Input-report rate statistics.

The receiver exposes the controller as a wired DualSense, so every report the
host receives on report 0x01 is one sample.  The monitor only measures what the
PC actually sees; it does not claim to know the controller's internal BT rate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(slots=True)
class RateStats:
    rate: float
    p50_ms: float
    p99_ms: float
    jitter_ms: float
    samples: int
    span_s: float
    state: str


def compute_stats(
    times: Iterable[float],
    now: float | None = None,
    window: float = 1.0,
    min_samples: int = 100,
    min_span: float = 0.5,
) -> RateStats | None:
    values = [float(value) for value in times]
    if len(values) < 2:
        return None
    end = float(now) if now is not None else values[-1]
    start = end - window
    recent = [value for value in values if start <= value <= end]
    if len(recent) < min_samples:
        return None
    span = recent[-1] - recent[0]
    if span < min_span:
        return None

    intervals = sorted(
        (right - left) * 1000.0 for left, right in zip(recent, recent[1:])
    )
    p50 = intervals[len(intervals) // 2]
    p99 = intervals[min(len(intervals) - 1, int(round(0.99 * (len(intervals) - 1))))]
    rate = (len(recent) - 1) / span
    jitter = max(0.0, p99 - p50)
    stable_limit = max(2.5, p50 * 1.5)
    state = "stable" if p99 <= stable_limit and rate >= 200 else "jitter"
    return RateStats(
        rate=round(rate, 1),
        p50_ms=round(p50, 2),
        p99_ms=round(p99, 2),
        jitter_ms=round(jitter, 2),
        samples=len(recent),
        span_s=round(span, 3),
        state=state,
    )
