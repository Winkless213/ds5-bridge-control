# -*- coding: utf-8 -*-
from ds5_bridge.rate import compute_stats


def timestamps(count: int, step: float) -> list[float]:
    return [index * step for index in range(count)]


def test_1000hz_is_stable():
    stats = compute_stats(timestamps(1001, 0.001))
    assert stats is not None
    assert 990 <= stats.rate <= 1010
    assert stats.p50_ms == 1.0
    assert stats.p99_ms == 1.0
    assert stats.state == "stable"


def test_750hz_is_stable():
    stats = compute_stats(timestamps(751, 1 / 750))
    assert stats is not None
    assert 740 <= stats.rate <= 760
    assert stats.state == "stable"


def test_alternating_intervals_are_still_stable():
    times = [0.0]
    for index in range(750):
        times.append(times[-1] + (0.001 if index % 2 == 0 else 0.002))
    stats = compute_stats(times)
    assert stats is not None
    assert 640 <= stats.rate <= 690
    assert stats.p99_ms == 2.0
    assert stats.state == "stable"


def test_long_gaps_are_reported_as_jitter():
    times = [0.0]
    for index in range(1000):
        times.append(times[-1] + (0.010 if index % 20 == 0 else 0.001))
    stats = compute_stats(times)
    assert stats is not None
    assert stats.p99_ms >= 10.0
    assert stats.state == "jitter"


def test_three_ms_outliers_are_jitter_at_high_rate():
    times = [0.0]
    for index in range(1000):
        times.append(times[-1] + (0.003 if index % 10 == 0 else 0.001))
    stats = compute_stats(times)
    assert stats is not None
    assert stats.p99_ms == 3.0
    assert stats.state == "jitter"


def test_too_few_samples_returns_none():
    assert compute_stats([0.0, 0.001, 0.002]) is None
    assert compute_stats([]) is None
