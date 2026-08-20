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
    # デバイス番号は再列挙で変わるため、名前を正とし番号は補助に留める。
    # どちらも未設定なら resolve_input_device() が WASAPI の既定を選ぶ。
    "device_index": None,
    "device_name": None,
    "digital_silence_ratio": 0.5,
    "alert_interval_sec": 10,
    "alert_sound_path": "builtin:error",
    "pause_sound_enabled": True,
    "pause_sound_path": "builtin:marimba",
    "monitor_stop_sound_enabled": True,
    "monitor_stop_sound_path": "builtin:marimba",
    "monitor_resume_sound_enabled": True,
    "monitor_resume_sound_path": "builtin:notify_11",
    "theme": "system",
    "alert_volume": 50,
    "auto_pause_enabled": True,
    "auto_pause_alert_count": 1,
    # キャプチャストリームを開いたままだと USB オーディオドライバが SYSTEM
    # 電源要求を立て、Windows がスリープに入らない。無操作が続いたら閉じる。
    "idle_suspend_enabled": True,
    # 各環境の Windows スリープ設定より短くないと機能しないため設定項目とする。
    "idle_suspend_sec": 180,
    "mic_share_monitor_enabled": True,
    # 詳細ログ。巡回ごとの記録が増えるため常用は想定しない。
    "debug_log": False,
}

# 旧キー -> 新キー。既存の config.json を読めるようにするための対応。
_RENAMED_KEYS = {
    "auto_snooze_enabled": "auto_pause_enabled",
    "auto_snooze_alert_count": "auto_pause_alert_count",
}


def load() -> dict:
    config_path = get_config_path()
    if not os.path.exists(config_path):
        return DEFAULT_CONFIG.copy()
    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for old, new in _RENAMED_KEYS.items():
        if old in data and new not in data:
            data[new] = data[old]

    config = DEFAULT_CONFIG.copy()
    # 廃止済みのキーは取り込まない（config.json に残骸を残さない）
    config.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
    return config


def save(config: dict) -> None:
    with open(get_config_path(), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
