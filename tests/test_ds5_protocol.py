# -*- coding: utf-8 -*-
import sys
from array import array

import pytest

from ds5_bridge.protocol import (
    CONFIG_SIZE,
    CONFIG_VERSION,
    DEFAULTS,
    LIVE_KEYS,
    REPORT_SET,
    TEST_HAPTICS_AMPLITUDE,
    TEST_RUMBLE_LEVEL,
    VIB_CONFIG_SIZE,
    ConfigVersionError,
    DeviceNotFound,
    changed_keys,
    configs_equal,
    find_haptics_output,
    firmware_block_reason,
    firmware_has_vib,
    firmware_writable,
    haptics_test_frames,
    idle_drop_risk,
    live_config,
    normalize_config,
    pack_config,
    parse_battery,
    play_test_haptics,
    play_test_rumble,
    read_firmware,
    LIGHTBAR_COLOR,
    REPORT_OUTPUT,
    claim_lights_report,
    read_status,
    reconnect_usb,
    requires_reconnect,
    rumble_report,
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


def test_claim_lights_report_pulses_reset_and_sets_colour():
    """Over BT the pad blinks its own "unclaimed" animation until a host
    pulses ResetLights; colour writes before that are silently ignored."""
    report = claim_lights_report()
    assert report[0] == REPORT_OUTPUT
    # flags1: ResetLights | AllowLedColor | AllowPlayerIndicators
    assert report[2] & 0x08, "ResetLights must be set"
    assert report[2] & 0x04, "AllowLedColor must be set"
    assert report[2] & 0x10, "AllowPlayerIndicators must be set"
    # Player 1 is the centre LED, as the console assigns for a single pad.
    assert report[44] == 0x04
    assert tuple(report[45:48]) == LIGHTBAR_COLOR
    # The firmware only forwards a report at once when a rumble flag is set,
    # and FW >= 2.24 pads need the improved-emulation bit; motors stay at 0.
    assert report[1] & 0x02 and report[39] & 0x04
    assert report[3] == report[4] == 0


def test_status_reports_which_vibration_path_is_live():
    """The vib.2 firmware adds bit2: a game is driving ordinary rumble."""

    class FakeDevice:
        def __init__(self, flags):
            self.flags = flags

        def get_feature_report(self, report_id, length):
            return bytes([0xF9, 0xC0, self.flags])

    # bit7 valid, bit3 "this build reports rumble", bit2 rumbling, audio idle.
    rumbling = read_status(FakeDevice(0x8C))
    assert rumbling["rumble_active"] is True
    assert rumbling["speaker_active"] is False

    # Speaker streaming, rumble reported but idle -> the HD path.
    haptics = read_status(FakeDevice(0x8A))
    assert haptics["rumble_active"] is False
    assert haptics["speaker_active"] is True

    # Firmware without the bit (official v0.7.2) must stay unknown, not False,
    # and must not lose the audio flags it does report.
    official = read_status(FakeDevice(0x83))
    assert official["rumble_active"] is None
    assert official["speaker_active"] is True
    assert official["mic_active"] is True


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


def test_write_keeps_receiver_volume_set_by_windows():
    # Windows lowered the controller volume to 30 after the console read the
    # config; saving must not push the stale 100 back.
    live = bytearray(REAL_REPORT)
    live[6] = 30  # speaker_volume
    live[7] = 25  # headset_volume

    class FakeDevice:
        def __init__(self):
            self.sent = []

        def get_feature_report(self, report_id, length):
            return bytes(live)

        def send_feature_report(self, report):
            self.sent.append(bytes(report))
            return len(report)

    device = FakeDevice()
    cfg = unpack_config(REAL_REPORT)
    cfg["haptics_gain"] = 1.5
    write_config(device, cfg)
    body = unpack_config(device.sent[0][2:21])
    assert body["speaker_volume"] == 30
    assert body["headset_volume"] == 25
    assert body["haptics_gain"] == 1.5


def test_write_refuses_other_config_versions():
    other = bytearray(REAL_REPORT)
    other[1] = 4

    class FakeDevice:
        sent: list = []

        def get_feature_report(self, report_id, length):
            return bytes(other)

        def send_feature_report(self, report):
            self.sent.append(bytes(report))
            return len(report)

    device = FakeDevice()
    try:
        write_config(device, unpack_config(REAL_REPORT))
    except ConfigVersionError:
        pass
    else:
        raise AssertionError("write must stop on a config version mismatch")
    assert device.sent == []


def test_firmware_write_whitelist():
    assert firmware_writable("v0.7.2")
    assert firmware_writable("v0.7.2-hotfix")
    assert firmware_writable("0.7.2-hotfix")
    # v0.8.0 keeps config_version 5 but changed the layout.
    assert not firmware_writable("v0.8.0")
    assert not firmware_writable("v0.7.21")
    assert not firmware_writable("v0.7.1")
    assert not firmware_writable("")
    assert not firmware_writable(None)
    assert "v0.8.0" in firmware_block_reason("v0.8.0")


# The vib firmware (v0.7.2-hotfix-vib.N) appends rumble_gain and vib_flags.
VIB_REPORT = REAL_REPORT + bytes([20, 0x05])


class ReportDevice:
    def __init__(self, report: bytes):
        self.report = report
        self.sent: list[bytes] = []

    def get_feature_report(self, report_id, length):
        return self.report

    def send_feature_report(self, report):
        self.sent.append(bytes(report))
        return len(report)


def test_official_report_reads_vib_fields_as_defaults():
    cfg = unpack_config(REAL_REPORT)
    assert cfg["rumble_gain"] == 0
    assert cfg["vib_flags"] == 0


def test_vib_report_roundtrips_extra_fields():
    cfg = unpack_config(VIB_REPORT)
    assert cfg["rumble_gain"] == 20
    assert cfg["vib_flags"] == 0x05
    assert cfg["haptics_gain"] == 1.0
    body = pack_config(cfg, vib=True)
    assert len(body) == VIB_CONFIG_SIZE
    assert body == VIB_REPORT[1:]


def test_write_uses_vib_layout_only_when_receiver_reports_it():
    vib = ReportDevice(VIB_REPORT)
    write_config(vib, dict(unpack_config(VIB_REPORT), rumble_gain=30, vib_flags=0x02))
    update = vib.sent[0]
    assert update[2:21] == VIB_REPORT[1:20]
    assert update[21:23] == bytes([30, 0x02])

    # Official v0.7.2 keeps exactly the 19-byte write it always had.
    official = ReportDevice(REAL_REPORT)
    write_config(official, dict(unpack_config(REAL_REPORT), rumble_gain=30, vib_flags=0x02))
    assert official.sent[0][2:21] == REAL_REPORT[1:]
    assert official.sent[0][21:] == bytes(64 - 21)


def test_vib_fields_count_as_changes():
    saved = normalize_config(DEFAULTS)
    assert not configs_equal(saved, dict(saved, rumble_gain=20))
    assert changed_keys(saved, dict(saved, vib_flags=1)) == ["vib_flags"]
    assert "rumble_gain" in LIVE_KEYS and "vib_flags" in LIVE_KEYS


def test_vib_fields_are_clamped():
    cfg = normalize_config({"rumble_gain": 99, "vib_flags": 0xFF})
    assert cfg["rumble_gain"] == 40
    assert cfg["vib_flags"] == 0x07


def test_rumble_report_only_touches_rumble():
    report = rumble_report(96)
    assert report[0] == 0x02
    assert report[1] == 0x02  # UseRumbleNotHaptics
    assert report[39] == 0x04  # EnableImprovedRumbleEmulation
    assert report[3] == report[4] == 96  # light and heavy motor
    # No Allow* bit: lights, triggers and volumes keep the game's state.
    untouched = [b for i, b in enumerate(report) if i not in (0, 1, 3, 4, 39)]
    assert untouched == [0] * len(untouched)
    # The receiver needs the whole 47-byte SetStateData block after the id.
    assert len(report) >= 48
    stop = rumble_report(0)
    assert stop[0] == 0x02 and set(stop[1:]) == {0}


class WriteDevice:
    def __init__(self):
        self.writes: list[bytes] = []

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)


def test_test_rumble_pulses_then_stops():
    device = WriteDevice()
    play_test_rumble(device, seconds=0)
    assert [w[3] for w in device.writes] == [TEST_RUMBLE_LEVEL, 0]
    assert device.writes[-1][1] == 0


def test_test_rumble_stops_even_if_interrupted(monkeypatch):
    def interrupted(seconds):
        raise RuntimeError("interrupted")

    monkeypatch.setattr("ds5_bridge.protocol.time.sleep", interrupted)
    device = WriteDevice()
    try:
        play_test_rumble(device)
    except RuntimeError:
        pass
    assert device.writes[-1] == rumble_report(0)


# Host API order and endpoint names as sounddevice listed them on the real PC.
HOSTAPIS = ({"name": "MME"}, {"name": "Windows DirectSound"}, {"name": "Windows WASAPI"})
PAD_SPEAKER = "扬声器 (3- DualSense Edge Wireless Controller)"


def _output(name, channels, hostapi):
    return {"name": name, "max_output_channels": channels, "hostapi": hostapi}


class FakeStream:
    def __init__(self, **settings):
        self.settings = settings
        self.written = b""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def write(self, data):
        self.written += bytes(data)


class FakeSoundDevice:
    def __init__(self, devices):
        self.devices = devices
        self.calls: list[str] = []
        self.streams: list[FakeStream] = []

    def _terminate(self):
        self.calls.append("terminate")

    def _initialize(self):
        self.calls.append("initialize")

    def query_devices(self):
        self.calls.append("query")
        return self.devices

    def query_hostapis(self):
        return HOSTAPIS

    def RawOutputStream(self, **settings):
        stream = FakeStream(**settings)
        self.streams.append(stream)
        return stream


def test_haptics_test_frames_only_drive_the_actuator_channels():
    samples = array("f", haptics_test_frames())
    frames = [samples[i:i + 4] for i in range(0, len(samples), 4)]
    assert len(samples) % 4 == 0
    # Channels 1-2 feed the speaker; 3-4 drive the HD haptics actuators.
    assert all(frame[0] == 0 and frame[1] == 0 for frame in frames)
    assert all(frame[2] == frame[3] for frame in frames)
    assert max(abs(frame[2]) for frame in frames) == pytest.approx(TEST_HAPTICS_AMPLITUDE, rel=0.01)
    # Silent at both ends, so the stream never starts or stops mid-wave.
    assert frames[0][2] == 0 and frames[-1][2] == 0


def test_test_amplitude_leaves_room_for_the_top_gain_and_speaker_gain():
    """1.0x and 2.0x felt the same because both clipped.

    The waveform is multiplied by the receiver's HD gain (up to 2.0) and by
    speaker_gain (up to 7 -> about 2x over the factory 2). At 0.4 even 1.0x
    was at or past full scale, so raising the gain changed nothing. Keep the
    worst case under 1.0 so every step up is still felt.
    """
    top_hd = 2.0
    speaker_gain_headroom = 2.0  # gain 7 against the factory default of 2
    assert TEST_HAPTICS_AMPLITUDE * top_hd * speaker_gain_headroom <= 1.0
    # Still loud enough to feel at the bottom of the range.
    assert TEST_HAPTICS_AMPLITUDE >= 0.15


def test_haptics_output_is_the_pads_wasapi_endpoint():
    devices = [
        _output("扬声器 (Realtek(R) Audio)", 2, 2),
        _output("扬声器 (3- DualSense Edge Wireless", 4, 0),
        _output(PAD_SPEAKER, 4, 1),
        _output(PAD_SPEAKER, 4, 2),
    ]
    assert find_haptics_output(devices, HOSTAPIS) == 3


def test_haptics_output_needs_the_four_channel_endpoint():
    devices = [_output("扬声器 (Realtek(R) Audio)", 2, 2), _output("耳机 (DualSense Wireless Controller)", 2, 2)]
    assert find_haptics_output(devices, HOSTAPIS) is None


def test_test_haptics_streams_the_pulses_to_the_pad(monkeypatch):
    sd = FakeSoundDevice([_output("扬声器 (Realtek(R) Audio)", 2, 2), _output(PAD_SPEAKER, 4, 2)])
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    assert play_test_haptics() == PAD_SPEAKER
    # A USB reconnect re-creates the endpoint, so the list is read afresh.
    assert sd.calls == ["terminate", "initialize", "query"]
    [stream] = sd.streams
    assert stream.settings == {"samplerate": 48000, "channels": 4, "dtype": "float32", "device": 1}
    assert stream.written == haptics_test_frames()


def test_test_haptics_hands_the_actuators_back_before_playing(monkeypatch):
    """The pad ignores the haptics channels while it is in rumble mode.

    Until some host clears UseRumbleNotHaptics the actuators stay with the
    motors, so a first HD test after a cold start was silent and only started
    working once a rumble test had ended (its all-clear report did the
    handover). Send that report ourselves, before the waveform.
    """
    sd = FakeSoundDevice([_output(PAD_SPEAKER, 4, 2)])
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    device = WriteDevice()
    play_test_haptics(device=device)
    assert device.writes == [rumble_report(0)]
    assert sd.streams[0].written == haptics_test_frames()


def test_test_haptics_plays_even_without_a_writable_device(monkeypatch):
    """No HID handle (read-only firmware): still play rather than refuse."""
    sd = FakeSoundDevice([_output(PAD_SPEAKER, 4, 2)])
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    assert play_test_haptics(device=None) == PAD_SPEAKER


def test_test_haptics_says_when_the_pad_has_no_audio_endpoint(monkeypatch):
    sd = FakeSoundDevice([_output("扬声器 (Realtek(R) Audio)", 2, 2)])
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    with pytest.raises(DeviceNotFound):
        play_test_haptics()
    assert sd.streams == []


def test_vib_firmware_detection():
    assert firmware_has_vib("v0.7.2-hotfix-vib.1")
    assert firmware_writable("v0.7.2-hotfix-vib.1")
    assert not firmware_has_vib("v0.7.2-hotfix")
    assert not firmware_has_vib("v0.8.0")
    assert not firmware_has_vib(None)


def test_live_keys_skip_reconnect_and_host_owned_fields():
    assert "haptics_gain" in LIVE_KEYS
    assert "speaker_gain" in LIVE_KEYS
    assert "disable_speaker" in LIVE_KEYS
    for key in ("polling_rate_mode", "controller_mode", "enable_usb_sn", "speaker_volume", "config_version"):
        assert key not in LIVE_KEYS


def test_idle_disconnect_waits_for_save():
    # bt.cpp only refreshes its idle timestamp while idle disconnect is on, so
    # trying a new value from RAM can drop the controller at once.
    assert "inactive_time" not in LIVE_KEYS


def test_idle_drop_risk_when_enabling_or_shortening():
    off = normalize_config(dict(DEFAULTS, inactive_time=0))
    ten = normalize_config(dict(DEFAULTS, inactive_time=10))
    assert idle_drop_risk(off, dict(off, inactive_time=5)) == "enable"
    assert idle_drop_risk(ten, dict(ten, inactive_time=5)) == "shorten"
    assert idle_drop_risk(ten, dict(ten, inactive_time=20)) == ""
    assert idle_drop_risk(ten, dict(ten, inactive_time=0)) == ""
    assert idle_drop_risk(off, off) == ""


def test_live_config_only_takes_live_fields():
    saved = normalize_config(DEFAULTS)
    draft = dict(saved, haptics_gain=1.6, polling_rate_mode=2, speaker_gain=5)
    out = live_config(saved, draft)
    assert out["haptics_gain"] == 1.6
    assert out["speaker_gain"] == 5
    assert out["polling_rate_mode"] == saved["polling_rate_mode"]


def test_changed_keys_ignores_float_noise():
    saved = normalize_config(DEFAULTS)
    assert changed_keys(saved, dict(saved, haptics_gain=1.004)) == []
    assert changed_keys(saved, dict(saved, haptics_gain=1.4, disable_mic=True)) == [
        "haptics_gain",
        "disable_mic",
    ]


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


def _input_report(battery: int = 0x08, report_id: int = 0x01, flags: int = 0x00) -> bytes:
    raw = bytearray(64)
    raw[0] = report_id
    raw[53] = battery
    raw[54] = flags
    return bytes(raw)


def test_parse_battery_discharging_uses_midpoint():
    state = parse_battery(_input_report(0x08))
    assert state == {
        "percent": 85,
        "level": 8,
        "state": 0x00,
        "charging": False,
        "plugged": False,
        "raw": 0x08,
        "flags": 0x00,
        "kind": "normal",
        "label": "使用中",
    }


def test_parse_battery_charging_and_full():
    # Captured live: DualSense Edge charging at ~45% from a power-only cable.
    charging = parse_battery(_input_report(0x14, flags=0x10))
    assert charging["percent"] == 45
    assert charging["charging"] is True
    assert charging["plugged"] is True
    assert charging["kind"] == "charging"
    assert charging["label"] == "充电中"

    full = parse_battery(_input_report(0x2A))
    assert full["percent"] == 100
    assert full["kind"] == "full"
    assert full["label"] == "已充满"


def test_parse_battery_complete_ignores_level_nibble():
    # 0x2 means the charge finished; the level nibble is not meaningful.
    for raw in (0x20, 0x29, 0x2B, 0x2F):
        state = parse_battery(_input_report(raw))
        assert state["percent"] == 100
        assert state["label"] == "已充满"


def test_parse_battery_error_has_no_percentage():
    state = parse_battery(_input_report(0xF0, flags=0x10))
    assert state["percent"] is None
    assert state["kind"] == "error"
    assert state["plugged"] is True
    assert state["label"] == "充电异常"


def test_parse_battery_invalid_level_is_unknown_not_low():
    state = parse_battery(_input_report(0x0C))
    assert state["percent"] is None
    assert state["label"] == "状态未知"


def test_parse_battery_low_level_is_flagged():
    state = parse_battery(_input_report(0x01))
    assert state["percent"] == 15
    assert state["kind"] == "low"
    assert state["label"] == "电量低"
    assert parse_battery(_input_report(0x02))["label"] == "使用中"


def test_parse_battery_plug_flags():
    assert parse_battery(_input_report(0x08, flags=0x00))["plugged"] is False
    for flags in (0x08, 0x10, 0x20, 0x18):
        assert parse_battery(_input_report(0x08, flags=flags))["plugged"] is True
    # Headphone / mic bits are not power.
    assert parse_battery(_input_report(0x08, flags=0x07))["plugged"] is False


def test_parse_battery_rejects_other_reports():
    assert parse_battery(_input_report(0x08, report_id=0x31)) is None
    assert parse_battery(b"\x01" * 10) is None
