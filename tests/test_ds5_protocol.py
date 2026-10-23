# -*- coding: utf-8 -*-
from ds5_bridge.protocol import (
    CONFIG_SIZE,
    CONFIG_VERSION,
    DEFAULTS,
    REPORT_SET,
    ConfigVersionError,
    configs_equal,
    normalize_config,
    pack_config,
    parse_battery,
    read_firmware,
    read_status,
    reconnect_usb,
    requires_reconnect,
    unpack_config,
    validate_config,
    write_config,
)

# Captured from the real device (firmware v0.7.2-hotfix, report 0xF7).
REAL_REPORT = bytes.fromhex(
    "f7 05 00 00 80 3f 64 64 02 1e 00 00 40 02 00 00 00 00 00 00"
)


def test_real_report_parses_expected_values():
    cfg = unpack_config(REAL_REPORT)
    assert cfg["config_version"] == CONFIG_VERSION
    assert cfg["haptics_gain"] == 1.0
    assert cfg["speaker_volume"] == 100
    assert cfg["headset_volume"] == 100
    assert cfg["speaker_gain"] == 2
    assert cfg["inactive_time"] == 30
    assert cfg["polling_rate_mode"] == 0
    assert cfg["audio_buffer_length"] == 64
    assert cfg["controller_mode"] == 2
    assert cfg["trigger_reduce"] == 0
    assert cfg["disable_mic"] is False
    assert cfg["disable_speaker"] is False


def test_pack_matches_real_report_without_report_id():
    body = pack_config(unpack_config(REAL_REPORT))
    assert len(body) == CONFIG_SIZE
    assert body == REAL_REPORT[1:]


def test_defaults_roundtrip():
    body = pack_config(DEFAULTS)
    cfg = unpack_config(body)
    assert cfg == normalize_config(DEFAULTS)
    assert len(body) == CONFIG_SIZE
    assert validate_config(cfg) == []


def test_normalize_clamps_out_of_range_values():
    cfg = normalize_config(
        {
            "haptics_gain": 9.0,
            "speaker_volume": 999,
            "headset_volume": -5,
            "audio_buffer_length": 1,
            "trigger_reduce": 99,
            "disable_mic": 1,
        }
    )
    assert cfg["haptics_gain"] == 2.0
    assert cfg["speaker_volume"] == 127
    assert cfg["headset_volume"] == 0
    assert cfg["audio_buffer_length"] == 16
    assert cfg["trigger_reduce"] == 10
    assert cfg["disable_mic"] is True


def test_wrong_version_is_rejected():
    raw = bytearray(REAL_REPORT[1:])
    raw[0] = 4
    try:
        unpack_config(bytes(raw))
    except ConfigVersionError:
        pass
    else:
        raise AssertionError("wrong config version should be rejected")


def test_configs_equal_ignores_float_noise():
    left = dict(DEFAULTS)
    right = dict(DEFAULTS)
    right["haptics_gain"] = 1.004
    assert configs_equal(left, right)


def test_firmware_decode():
    class FakeDevice:
        def get_feature_report(self, report_id, length):
            return bytes([0xF8]) + b"v0.7.2-hotfix\x00"

    assert read_firmware(FakeDevice()) == "v0.7.2-hotfix"


def test_status_decode():
    class FakeDevice:
        def get_feature_report(self, report_id, length):
            return bytes([0xF9, 0xC0, 0x83])

    status = read_status(FakeDevice())
    assert status["rssi"] == -64
    assert status["speaker_active"] is True
    assert status["mic_active"] is True


def test_write_and_save_reports_are_well_formed():
    class FakeDevice:
        def __init__(self):
            self.sent = []

        def get_feature_report(self, report_id, length):
            return REAL_REPORT

        def send_feature_report(self, report):
            self.sent.append(bytes(report))
            return len(report)

    device = FakeDevice()
    cfg = unpack_config(REAL_REPORT)
    fresh = write_config(device, cfg, save=True)
    assert fresh == cfg
    assert len(device.sent) == 2
    update, save = device.sent
    assert len(update) == 64
    assert update[0] == REPORT_SET
    assert update[1] == 0x01
    assert update[2:21] == REAL_REPORT[1:]
    assert save[0] == REPORT_SET
    assert save[1] == 0x02


def test_reconnect_report():
    class FakeDevice:
        def __init__(self):
            self.sent = []

        def send_feature_report(self, report):
            self.sent.append(bytes(report))
            return len(report)

    device = FakeDevice()
    reconnect_usb(device)
    assert device.sent[0][0] == REPORT_SET
    assert device.sent[0][1] == 0x03


def test_audio_change_does_not_require_reconnect():
    before = normalize_config(DEFAULTS)
    after = dict(before)
    after["speaker_volume"] = 80
    after["haptics_gain"] = 1.5
    assert requires_reconnect(before, after) is False


def test_descriptor_change_requires_reconnect():
    before = normalize_config(DEFAULTS)
    for key, value in (
        ("polling_rate_mode", 2),
        ("controller_mode", 0),
        ("enable_usb_sn", True),
        ("ps_shortcut_enabled", True),
        ("enable_wake", True),
    ):
        after = dict(before)
        after[key] = value
        assert requires_reconnect(before, after) is True


def test_requires_reconnect_without_baseline_is_false():
    assert requires_reconnect(None, normalize_config(DEFAULTS)) is False


def _input_report(battery: int = 0x08, report_id: int = 0x01) -> bytes:
    raw = bytearray(64)
    raw[0] = report_id
    raw[53] = battery
    return bytes(raw)


def test_parse_battery_discharging_uses_midpoint():
    state = parse_battery(_input_report(0x08))
    assert state == {
        "percent": 85,
        "level": 8,
        "state": 0x00,
        "charging": False,
        "label": "使用中",
    }


def test_parse_battery_charging_and_full():
    charging = parse_battery(_input_report(0x19))
    assert charging["percent"] == 95
    assert charging["charging"] is True
    assert charging["label"] == "充电中"

    full = parse_battery(_input_report(0x2A))
    assert full["percent"] == 100
    assert full["label"] == "已充满"


def test_parse_battery_error_has_no_percentage():
    state = parse_battery(_input_report(0xF0))
    assert state["percent"] is None
    assert state["label"] == "充电异常"


def test_parse_battery_low_level_is_flagged():
    state = parse_battery(_input_report(0x01))
    assert state["percent"] == 15
    assert state["label"] == "电量低"


def test_parse_battery_rejects_other_reports():
    assert parse_battery(_input_report(0x08, report_id=0x31)) is None
    assert parse_battery(b"\x01" * 10) is None
