from dse_panel.protocol import (
    InputState,
    build_output_report,
    parse_firmware_info,
    parse_input_report,
    parse_pairing_info,
)


def make_report(battery=0x15, buttons=(0x08, 0, 0, 0), l2=0, r2=0):
    raw = bytearray(64)
    raw[0] = 0x01
    raw[1:5] = bytes([0x80, 0x80, 0x80, 0x80])
    raw[5] = l2
    raw[6] = r2
    raw[7] = 0x2A
    raw[8:12] = bytes(buttons)
    raw[53] = battery
    return bytes(raw)


def test_parse_input_report_extracts_state():
    state = parse_input_report(make_report())
    assert isinstance(state, InputState)
    assert state.lx == 0x80 and state.ly == 0x80
    assert state.seq == 0x2A
    assert state.battery_raw == 0x15


def test_parse_input_report_rejects_other_reports():
    raw = bytearray(make_report())
    raw[0] = 0x31
    assert parse_input_report(raw) is None
    assert parse_input_report(b"\x01" * 10) is None


def test_battery_status_and_percent():
    # 低 4 位是档位，5 档 = 55%，高 4 位 1 = 充电中
    state = parse_input_report(make_report(battery=0x15))
    assert state.battery_level == 5
    assert state.battery_status == 0x1
    assert state.battery_percent == 55
    assert state.charging_text == "充电中"
    assert state.is_charging

    full = parse_input_report(make_report(battery=0x2A))
    assert full.battery_percent == 100
    assert full.charging_text == "已充满"

    empty_error = parse_input_report(make_report(battery=0xF0))
    assert empty_error.battery_percent == 0


def test_button_and_edge_bits():
    state = parse_input_report(make_report(buttons=(0x08, 0x40, 0xF1, 0)))
    names = state.pressed_names
    assert "L3" in names
    assert "PS" in names
    assert "FN1" in names
    assert "FN2" in names
    assert "左背键" in names
    assert "右背键" in names


def test_idle_detection():
    assert parse_input_report(make_report()).is_idle
    assert not parse_input_report(make_report(buttons=(0x48, 0, 0, 0))).is_idle


def test_output_report_rumble_and_flags():
    buf = build_output_report(100, 200)
    assert len(buf) == 64
    assert buf[0] == 0x02
    assert buf[1] == 0x03
    assert buf[3] == 100
    assert buf[4] == 200


def test_output_report_lightbar_and_volume():
    buf = build_output_report(0, 0, lightbar=(10, 20, 30), player_leds=0b101, speaker_volume=0xFF)
    assert buf[1] & 0x20
    assert buf[6] == 0xFF
    assert buf[2] & 0x04 and buf[2] & 0x10
    assert (buf[45], buf[46], buf[47]) == (10, 20, 30)
    assert buf[44] == 0b101


def test_output_report_clamps_values():
    buf = build_output_report(999, -5, lightbar=(300, -2, 128), speaker_volume=999)
    assert buf[3] == 255 and buf[4] == 0
    assert (buf[45], buf[46], buf[47]) == (255, 0, 128)
    assert buf[6] == 255


def test_output_report_audio_control_path():
    buf = build_output_report(0, 0, speaker_volume=0x64, audio_control=0x03, audio_control2=0x02)
    assert buf[1] & 0x80
    assert buf[8] == 0x03
    assert buf[2] & 0x80
    assert buf[38] == 0x02
    assert buf[6] == 0x64


def test_parse_firmware_info():
    raw = bytearray(64)
    raw[0] = 0x20
    raw[1:21] = b"Jul  4 202510:38:40\x03"
    raw[24:28] = (0x11).to_bytes(4, "little")
    raw[28:32] = (0x22).to_bytes(4, "little")
    info = parse_firmware_info(raw)
    assert info["build"] == "Jul  4 2025 10:38:40"
    assert info["hw_version"] == 0x11
    assert info["fw_version"] == 0x22


def test_parse_pairing_info():
    raw = bytes([0x09]) + bytes([0xDE, 0xEF, 0xD1, 0x32, 0xEE, 0x50]) + bytes(13)
    assert parse_pairing_info(raw) == "50:EE:32:D1:EF:DE"
