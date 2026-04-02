import logging
import os

import pygame
import settings

logger = logging.getLogger(__name__)

_BUILTIN_MAP = {
    "builtin:chime": os.path.join("assets", "alert_chime.wav"),
    "builtin:error": os.path.join("assets", "alert_error.wav"),
    "builtin:marimba": os.path.join("assets", "alert_marimba.wav"),
    "builtin:notify_04": os.path.join("assets", "notify_04.wav"),
    "builtin:notify_11": os.path.join("assets", "notify_11.wav"),
}


def _resolve_builtin_sound(sound_key: str) -> str:
    relative_path = _BUILTIN_MAP[sound_key]
    return os.path.normpath(os.path.join(settings.get_resource_dir(), relative_path))


class Notifier:
    def __init__(self):
        pygame.mixer.init()

    def play_sound(self, sound_path: str, volume: int = 80) -> None:
        if sound_path in _BUILTIN_MAP:
            sound_path = _resolve_builtin_sound(sound_path)
        elif sound_path.startswith("custom:"):
            sound_path = sound_path[len("custom:"):]

        if not os.path.exists(sound_path):
            raise FileNotFoundError(f"音声ファイルが見つかりません: {sound_path}")
        try:
            sound = pygame.mixer.Sound(sound_path)
            sound.set_volume(volume / 100.0)
            sound.play()
            pygame.time.wait(int(sound.get_length() * 1000))
        except Exception as e:
            logger.error("アラート音の再生に失敗しました: %s", e)
