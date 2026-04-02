import json
import os
import sys


def get_app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_dir() -> str:
    return getattr(sys, "_MEIPASS", get_app_dir())


def get_config_path() -> str:
    return os.path.join(get_app_dir(), "config.json")


def resolve_app_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(get_app_dir(), path))

DEFAULT_CONFIG = {
    "device_index": None,
    "silence_threshold_db": -80.0,
    "silence_duration_sec": 5,
    "alert_interval_sec": 30,
    "alert_sound_path": "builtin:error",
    "pause_sound_enabled": True,
    "pause_sound_path": "builtin:marimba",
    "monitor_stop_sound_enabled": True,
    "monitor_stop_sound_path": "builtin:marimba",
    "monitor_resume_sound_enabled": True,
    "monitor_resume_sound_path": "builtin:notify_11",
    "startup_enabled": True,
    "theme": "system",
    "alert_volume": 50,
    "auto_snooze_enabled": True,
    "auto_snooze_alert_count": 2,
    "auto_snooze_resume_sec": 3,
}


def load() -> dict:
    config_path = get_config_path()
    if not os.path.exists(config_path):
        return DEFAULT_CONFIG.copy()
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    config = DEFAULT_CONFIG.copy()
    config.update(data)
    return config


def save(config: dict) -> None:
    with open(get_config_path(), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
