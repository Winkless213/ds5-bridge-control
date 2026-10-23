# -*- coding: utf-8 -*-
from ds5_bridge.qml_bridge import ThemeModel, UiBridge, _signal_text


def test_signal_text_thresholds():
    assert _signal_text(None) == "信号未知"
    assert _signal_text(0) == "信号未知"
    assert _signal_text(-50) == "信号良好"
    assert _signal_text(-70) == "信号一般"
    assert _signal_text(-90) == "信号较弱"


def test_theme_tokens_are_static():
    theme = ThemeModel()
    assert theme.version == "1.5.0"
    assert theme.accent == "#6FA8FF"
    assert theme.bg == "#080C11"


def test_bridge_clamps_draft_values_without_device():
    bridge = UiBridge()
    try:
        bridge.setValue("hapticsGain", 1.5)
        bridge.setValue("audioBuffer", 999)
        bridge.setValue("disableLed", True)
        bridge.setValue("unknown", 1)
        assert bridge.gainLabel == "1.50×"
        assert bridge.audioBuffer == 127
        assert bridge.disableLed is True
        assert bridge.connected is False
        assert bridge.statusText == "未连接"
    finally:
        bridge.shutdown()


def test_bridge_empty_state_after_failed_probe():
    bridge = UiBridge()
    try:
        bridge._on_probe_done([])
        assert bridge.empty is True
        assert "没有找到" in bridge.emptyDetail
        assert bridge.probing is False
    finally:
        bridge.shutdown()


def test_bridge_rate_starts_off():
    bridge = UiBridge()
    try:
        assert bridge.reportRateValue == "—"
        assert bridge.reportRateState == "off"
        assert bridge.reportRateDetail == "切到设备页后自动开始"
        assert bridge.reportRateSamples == []
    finally:
        bridge.shutdown()
