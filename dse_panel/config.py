"""用户配置持久化：只保存本程序自己的设置，不触碰接收器配置。"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

APP_NAME = "DSEControl"


def config_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(base) / APP_NAME


def config_path() -> Path:
    return config_dir() / "config.json"


DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "mappings": {},
    "rumble": {"left": 128, "right": 128},
    "audio": {"speaker_volume": 100},
    "receiver": {
        "rumble_level": None,
        "stick_left": None,
        "stick_right": None,
        "trigger_left": None,
        "trigger_right": None,
        "settings_key": None,
        "confirmed": {},
    },
    "window": {},
}


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return json.loads(json.dumps(DEFAULT_CONFIG))
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            else:
                merged[key] = value
    audio = merged.get("audio")
    if isinstance(audio, dict):
        try:
            audio["speaker_volume"] = min(100, max(0, int(audio.get("speaker_volume", 100))))
        except (TypeError, ValueError):
            audio["speaker_volume"] = 100
    return merged


def save_config(data: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def record_mapping(config: dict[str, Any], side: str, buttons: list[str]) -> None:
    config.setdefault("mappings", {})[side] = {
        "buttons": buttons,
        "detected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_config(config)


def record_receiver_setting(config: dict[str, Any], key: str, value: Any) -> None:
    """记录用户确认过的接收器档位；接收器本身不向主机回报当前值。"""
    receiver = config.setdefault("receiver", {})
    receiver[key] = value
    receiver.setdefault("confirmed", {})[key] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_config(config)
