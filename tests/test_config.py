import json

from dse_panel import config as config_module


def test_config_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    data = config_module.load_config()
    data["rumble"] = {"left": 10, "right": 20}
    config_module.save_config(data)
    loaded = json.loads(config_module.config_path().read_text(encoding="utf-8"))
    assert loaded["rumble"] == {"left": 10, "right": 20}


def test_record_mapping(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    data = config_module.load_config()
    config_module.record_mapping(data, "left", ["L3"])
    config_module.record_mapping(data, "right", ["圆圈"])
    saved = json.loads(config_module.config_path().read_text(encoding="utf-8"))
    assert saved["mappings"]["left"]["buttons"] == ["L3"]
    assert saved["mappings"]["right"]["buttons"] == ["圆圈"]
    assert saved["mappings"]["left"]["detected_at"]


def test_record_receiver_setting(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    data = config_module.load_config()
    assert data["receiver"]["rumble_level"] is None
    config_module.record_receiver_setting(data, "rumble_level", 2)
    saved = json.loads(config_module.config_path().read_text(encoding="utf-8"))
    assert saved["receiver"]["rumble_level"] == 2
    assert saved["receiver"]["confirmed"]["rumble_level"]
