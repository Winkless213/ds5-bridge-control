# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from ds5_bridge.protocol import DEFAULTS, DeviceInfo, normalize_config
from ds5_bridge.qml_bridge import ThemeModel, UiBridge, _signal_text, audio_activity_text


def test_signal_text_thresholds():
    assert _signal_text(None) == "信号未知"
    assert _signal_text(0) == "信号未知"
    assert _signal_text(-50) == "信号良好"
    assert _signal_text(-70) == "信号一般"
    assert _signal_text(-90) == "信号较弱"


def test_theme_tokens_are_static():
    theme = ThemeModel()
    assert theme.version == "1.6.0"
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
        assert bridge.reportRateDetail == "窗口显示时自动开始"
        assert bridge.reportRateSamples == []
    finally:
        bridge.shutdown()


# ----------------------------------------------------------------- wording
def test_audio_activity_is_worded_as_live_state():
    status = {"rssi": -50, "speaker_active": False, "mic_active": False}
    saved = normalize_config(DEFAULTS)
    assert audio_activity_text(status, saved) == "声音空闲 · 麦克风空闲"
    status = {"rssi": -50, "speaker_active": True, "mic_active": True}
    assert audio_activity_text(status, saved) == "声音播放中 · 麦克风录音中"
    disabled = dict(saved, disable_mic=True, disable_speaker=True)
    assert audio_activity_text({"speaker_active": False, "mic_active": False}, disabled) == (
        "声音已关闭 · 麦克风已关闭"
    )
    assert audio_activity_text({"speaker_active": None, "mic_active": None}, saved) == "未知"


def test_power_summary_names_settings_not_live_state():
    bridge = UiBridge()
    try:
        bridge.setValue("inactiveTime", 0)
        bridge.setValue("disableMic", False)
        assert bridge.powerSummary == "闲置不断开 · 指示灯开 · 麦克风可用"
        bridge.setValue("inactiveTime", 30)
        bridge.setValue("disableMic", True)
        bridge.setValue("disableLed", True)
        assert bridge.powerSummary == "闲置 30 分钟断开 · 指示灯关 · 麦克风已关闭"
    finally:
        bridge.shutdown()


# ----------------------------------------------------- connected behaviour
class Recorder:
    def __init__(self) -> None:
        self.previews: list[dict] = []
        self.applies: list[tuple[dict, bool, bool]] = []
        self.writes: list[dict] = []
        self.lights = 0


@pytest.fixture()
def connected():
    def make(firmware: str = "v0.7.2-hotfix"):
        bridge = UiBridge()
        rec = Recorder()
        bridge.service.preview = lambda config: rec.previews.append(dict(config)) or True
        bridge.service.apply = (
            lambda config, save, reconnect=False: rec.applies.append((dict(config), save, reconnect)) or True
        )
        bridge.service.write_now = lambda config: rec.writes.append(dict(config)) or True
        bridge.service.watch_battery = lambda path: None
        bridge.service.claim_lights = lambda: rec.__setattr__("lights", rec.lights + 1) or True
        info = DeviceInfo(path=b"fake", product_id=0x0DF2, product="DualSense Edge", firmware=firmware)
        saved = normalize_config(dict(DEFAULTS, haptics_gain=1.4, inactive_time=0))
        bridge._on_connected(info, saved, firmware, {"rssi": -50})
        made.append(bridge)
        return bridge, rec, saved

    made: list[UiBridge] = []
    yield make
    for bridge in made:
        bridge.shutdown()


def test_live_field_is_previewed_without_saving(connected):
    bridge, rec, saved = connected()
    bridge.setValue("hapticsGain", 1.6)
    assert bridge.dirty is True
    assert bridge.changedKeys == ["hapticsGain"]
    bridge._push_preview()
    assert len(rec.previews) == 1
    preview = rec.previews[0]
    assert preview["haptics_gain"] == 1.6
    assert {k: v for k, v in preview.items() if k != "haptics_gain"} == {
        k: v for k, v in saved.items() if k != "haptics_gain"
    }
    assert rec.applies == []
    # Same target again: nothing new is written.
    bridge._push_preview()
    assert len(rec.previews) == 1
    bridge._on_preview_done(preview)
    assert bridge.liveActive is True
    assert "试用" in bridge.stateHint


def test_reconnect_fields_are_not_previewed(connected):
    bridge, rec, _ = connected()
    bridge.setValue("polling", 1)
    bridge._push_preview()
    assert rec.previews == []
    assert bridge.pendingReconnect is True
    assert bridge.stateHint == "这些改动要保存后自动重连才生效。"


def test_idle_disconnect_is_saved_not_previewed(connected):
    bridge, rec, _ = connected()
    bridge.setValue("inactiveTime", 5)
    bridge._push_preview()
    assert rec.previews == []
    assert bridge.dirty is True
    assert "5 分钟" in bridge.idleDropHint
    assert bridge.stateHint == "这些改动保存后才生效。"


def test_drop_right_after_idle_save_is_explained(connected):
    bridge, rec, _ = connected()
    toasts: list[tuple[str, str, str]] = []
    bridge.toastRequested.connect(lambda *args: toasts.append(args))
    bridge.setValue("inactiveTime", 5)
    bridge.save()
    bridge._on_status_failed("无法打开设备")
    bridge._on_status_failed("无法打开设备")
    assert bridge.connected is False
    assert toasts[-1][1] == "闲置断开已生效"
    assert "PS" in toasts[-1][2]


VIB_FIRMWARE = "v0.7.2-hotfix-vib.1"


def test_vib_options_need_the_vib_firmware(connected):
    official, rec, _ = connected()
    assert official.vibSupported is False
    official.setValue("rumbleGain", 200)
    official.setValue("hapticLpf", True)
    assert official.dirty is False
    vib, _, _ = connected(VIB_FIRMWARE)
    assert vib.vibSupported is True
    assert vib.writable is True


def test_rumble_gain_is_edited_in_percent_and_previewed(connected):
    bridge, rec, _ = connected(VIB_FIRMWARE)
    assert bridge.rumbleGain == 100
    bridge.setValue("rumbleGain", 250)
    assert bridge.rumbleGain == 250
    assert bridge.rumbleGainLabel == "250%"
    assert bridge.vibSummary == "普通震动 250%"
    assert bridge.changedKeys == ["rumbleGain"]
    bridge._push_preview()
    assert rec.previews[-1]["rumble_gain"] == 25
    # 100% is the game's own strength and is stored as 0, like the official firmware.
    bridge.setValue("rumbleGain", 100)
    assert bridge.dirty is False


def test_legacy_rumble_toggles_its_own_bit(connected):
    bridge, rec, _ = connected(VIB_FIRMWARE)
    bridge.setValue("legacyRumble", True)
    assert bridge.legacyRumble is True
    assert bridge.changedKeys == ["legacyRumble"]
    assert bridge.vibSummary == "普通震动 100% · 老式换算"
    bridge._push_preview()
    assert rec.previews[-1]["vib_flags"] == 0x01

    bridge.setValue("legacyRumble", False)
    assert bridge.changedKeys == []
    assert bridge.vibSummary == "普通震动 100%"


def test_test_rumble_uses_the_value_just_set(connected):
    bridge, _, _ = connected(VIB_FIRMWARE)
    calls: list[tuple[str, int | None]] = []
    bridge.service.preview = lambda config: calls.append(("preview", config["rumble_gain"])) or True
    bridge.service.test_rumble = lambda: calls.append(("rumble", None)) or True
    bridge.setValue("rumbleGain", 200)
    # Clicked before the preview delay ran out: the new strength goes first.
    bridge.testRumble()
    assert calls == [("preview", 20), ("rumble", None)]


def test_test_rumble_needs_the_vib_firmware(connected):
    bridge, _, _ = connected()
    calls: list[str] = []
    bridge.service.test_rumble = lambda: calls.append("rumble") or True
    bridge.testRumble()
    assert calls == []


def test_test_haptics_uses_the_gain_just_set(connected):
    # The official firmware has the HD gain too, so no vib build is needed.
    bridge, _, _ = connected()
    calls: list[tuple[str, float | None]] = []
    bridge.service.preview = lambda config: calls.append(("preview", config["haptics_gain"])) or True
    bridge.service.test_haptics = lambda: calls.append(("haptics", None)) or True
    bridge.setValue("hapticsGain", 1.8)
    # Clicked before the preview delay ran out: the new gain goes first.
    bridge.testHaptics()
    assert calls == [("preview", pytest.approx(1.8)), ("haptics", None)]


def test_test_haptics_needs_a_writable_receiver():
    bridge = UiBridge()
    calls: list[str] = []
    bridge.service.test_haptics = lambda: calls.append("haptics") or True
    try:
        bridge.testHaptics()
    finally:
        bridge.shutdown()
    assert calls == []


def test_revert_restores_saved_values_in_ram(connected):
    bridge, rec, saved = connected()
    bridge.setValue("hapticsGain", 1.8)
    bridge._push_preview()
    bridge._on_preview_done(rec.previews[-1])
    bridge.revert()
    assert bridge.dirty is False
    assert bridge.hapticsGain == pytest.approx(1.4)
    assert rec.previews[-1] == saved


def test_save_sends_full_draft_and_marks_reconnect(connected):
    bridge, rec, _ = connected()
    bridge.setValue("hapticsGain", 1.2)
    bridge.setValue("mode", 1)
    bridge.save()
    config, save, reconnect = rec.applies[-1]
    assert config["haptics_gain"] == 1.2
    assert config["controller_mode"] == 1
    assert save is True and reconnect is True


def test_unsaved_preview_is_rolled_back_on_quit(connected):
    bridge, rec, saved = connected()
    bridge.setValue("speakerGain", 6)
    bridge._push_preview()
    bridge._on_preview_done(rec.previews[-1])
    bridge.shutdown()
    assert rec.writes == [saved]


def test_unknown_firmware_is_read_only(connected):
    bridge, rec, _ = connected("v0.8.0")
    assert bridge.connected is True
    assert bridge.writable is False
    assert bridge.statusText == "只读模式"
    assert "v0.8.0" in bridge.readOnlyReason
    bridge.setValue("hapticsGain", 1.8)
    bridge._push_preview()
    assert rec.previews == []
    assert bridge.canSave is False
    assert bridge.canReset is False
    bridge.save()
    bridge.resetDefaults()
    assert rec.applies == []


def test_receiver_lost_after_repeated_status_failures(connected):
    bridge, rec, _ = connected()
    toasts: list[tuple[str, str, str]] = []
    bridge.toastRequested.connect(lambda *args: toasts.append(args))
    bridge._on_status_failed("无法打开设备")
    assert bridge.connected is True
    bridge._on_status_failed("无法打开设备")
    assert bridge.connected is False
    # The receiver also drops off USB when the controller disconnects.
    assert "PS 键" in bridge.emptyDetail
    assert len(toasts) == 1
    # Further failed background probes stay silent.
    bridge._on_probe_done([])
    assert len(toasts) == 1


def test_dropped_experiments_are_gone(connected):
    """Only the legacy-rumble switch earned its place; the other two made no
    audible difference on the real pad, so they are not worth a row."""
    bridge, _rec, _saved = connected("v0.7.2-hotfix-vib.4")
    for gone in ("hapticLpf", "hardClip"):
        assert not hasattr(bridge, gone)
        bridge.setValue(gone, True)  # unknown keys must be ignored, not crash
    assert bridge.vibFlags == 0
    bridge.setValue("legacyRumble", True)
    assert bridge.legacyRumble is True


def test_the_two_paths_do_not_touch_each_other(connected):
    """Two systems, two settings: the UI promises they are independent."""
    bridge, _rec, saved = connected("v0.7.2-hotfix-vib.4")
    bridge.setValue("rumbleGain", 200)
    assert bridge.hapticsGain == saved["haptics_gain"]
    bridge.setValue("hapticsGain", 1.8)
    assert bridge.rumbleGain == 200


def test_connecting_claims_the_lights(connected):
    """Otherwise the pad keeps its "unclaimed" blink the whole session."""
    bridge, rec, _saved = connected()
    assert rec.lights == 1


def test_rows_show_the_factory_default_only_when_it_differs(connected):
    """The user cannot be expected to remember what they changed months ago."""
    bridge, _rec, _saved = connected()

    # Saved config is DEFAULTS apart from haptics_gain 1.4 and inactive_time 0.
    assert bridge.defaultHint("hapticsGain") == "原厂默认 1.00×"
    assert bridge.defaultHint("inactiveTime") == "原厂默认 30 分钟"
    # Untouched rows say nothing.
    assert bridge.defaultHint("audioBuffer") == ""
    assert bridge.defaultHint("speakerGain") == ""


def test_restoring_one_row_leaves_the_others_alone(connected):
    bridge, rec, saved = connected()
    bridge.setValue("speakerGain", 6)
    assert bridge.defaultHint("speakerGain") == "原厂默认 2"

    bridge.restoreDefault("speakerGain")

    assert bridge.speakerGain == DEFAULTS["speaker_gain"]
    assert bridge.defaultHint("speakerGain") == ""
    # The row it did not touch keeps the saved value, and nothing hit flash.
    assert bridge.hapticsGain == saved["haptics_gain"]
    assert rec.applies == []


def test_vibration_path_tells_the_user_which_slider_to_touch(connected):
    """Two vibration systems, two sliders; the device page says which is live."""
    bridge, _rec, _saved = connected("v0.7.2-hotfix-vib.2")

    bridge._on_status({"rssi": -50, "speaker_active": False, "mic_active": False,
                       "rumble_active": True})
    assert bridge.vibPathKind == "rumble"
    assert "普通震动" in bridge.vibPathText

    bridge._on_status({"rssi": -50, "speaker_active": True, "mic_active": False,
                       "rumble_active": False})
    assert bridge.vibPathKind == "haptics"
    assert "HD" in bridge.vibPathText

    bridge._on_status({"rssi": -50, "speaker_active": False, "mic_active": False,
                       "rumble_active": False})
    assert bridge.vibPathKind == "idle"

    # Official firmware cannot report it; say so rather than claim "idle".
    official, _r, _s = connected("v0.7.2-hotfix")
    official._on_status({"rssi": -50, "speaker_active": False, "mic_active": False,
                         "rumble_active": None})
    assert official.vibPathKind == "unknown"


def test_battery_view_drives_properties():
    bridge = UiBridge()
    try:
        bridge._on_battery(
            {
                "percent": 100,
                "label": "已充满",
                "kind": "full",
                "charging": False,
                "plugged": True,
                "note": "手柄报告 0xF0（充电异常）",
            }
        )
        assert bridge.batteryText == "100% · 已充满"
        assert bridge.batteryKind == "full"
        assert "0xF0" in bridge.batteryNote
        bridge._on_battery(None)
        assert bridge.batteryText == "电量未知"
        assert bridge.batteryKind == "unknown"
        assert bridge.batteryPercent == -1
    finally:
        bridge.shutdown()
