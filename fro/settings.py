"""User settings, saved as JSON in %APPDATA%\\Fro\\settings.json."""
import getpass
import json
import os
import threading

from .paths import data_dir

DEFAULTS = {
    "user_name": "",
    "wake_word": "hey fro",
    "wake_enabled": True,
    "language": "en-US",
    "api_key": "",
    "model": "claude-sonnet-5-5",
    "tts_enabled": True,
    "tts_voice": "en-US-AriaNeural",
    "tts_voice_bn": "bn-BD-NabanitaNeural",
    "hotkey": "ctrl+alt+space",
    "overlay_position": "top",
    "chime": True,
    "music_service": "youtube",
    "weather_city": "",
    "start_with_windows": False,
    "extra_apps": {},
}


class Settings:
    def __init__(self):
        self._path = data_dir() / "settings.json"
        self._lock = threading.RLock()
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        with self._lock:
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self.data.update(json.load(f))
            except (OSError, ValueError):
                pass

    def save(self):
        with self._lock:
            try:
                with open(self._path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
            except OSError:
                pass

    def get(self, key):
        with self._lock:
            value = self.data.get(key, DEFAULTS.get(key))
        if key == "user_name" and not value:
            try:
                return getpass.getuser().replace(".", " ").replace("_", " ").title()
            except Exception:
                return "there"
        if key == "api_key" and not value:
            return os.environ.get("ANTHROPIC_API_KEY", "").strip()
        return value

    def set(self, key, value, save=True):
        with self._lock:
            self.data[key] = value
        if save:
            self.save()

    def update(self, values: dict):
        with self._lock:
            self.data.update(values)
        self.save()


settings = Settings()
