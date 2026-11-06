"""Notes, lists, remembered facts and scheduled items, saved as JSON."""
import datetime as dt
import json
import threading

from .paths import data_dir


class Store:
    def __init__(self):
        self._path = data_dir() / "data.json"
        self._lock = threading.RLock()
        self.version = 0  # bumped on every change so the UI knows when to refresh
        self.data = {"notes": [], "lists": {}, "facts": [], "items": []}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))
        except (OSError, ValueError):
            pass

    def _save(self):
        self.version += 1
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1, ensure_ascii=False)
        except OSError:
            pass

    # ---- notes
    def add_note(self, text):
        with self._lock:
            self.data["notes"].append({"t": dt.datetime.now().isoformat(timespec="minutes"), "text": text})
            self._save()

    def notes(self):
        with self._lock:
            return list(self.data["notes"])

    def delete_note(self, index):
        with self._lock:
            if 0 <= index < len(self.data["notes"]):
                self.data["notes"].pop(index)
                self._save()

    def clear_notes(self):
        with self._lock:
            self.data["notes"] = []
            self._save()

    # ---- lists (to-do, shopping, ...)
    def list_add(self, name, item):
        with self._lock:
            self.data["lists"].setdefault(name, []).append(item)
            self._save()

    def list_get(self, name):
        with self._lock:
            return list(self.data["lists"].get(name, []))

    def list_all(self):
        with self._lock:
            return {k: list(v) for k, v in self.data["lists"].items() if v}

    def list_remove(self, name, item):
        with self._lock:
            items = self.data["lists"].get(name, [])
            for i, it in enumerate(items):
                if it.lower() == item.lower():
                    items.pop(i)
                    self._save()
                    return True
        return False

    def list_clear(self, name):
        with self._lock:
            self.data["lists"][name] = []
            self._save()

    # ---- facts Fro remembers about you
    def add_fact(self, fact):
        with self._lock:
            self.data["facts"].append(fact)
            self.data["facts"] = self.data["facts"][-40:]
            self._save()

    def facts(self):
        with self._lock:
            return list(self.data["facts"])

    def clear_facts(self):
        with self._lock:
            self.data["facts"] = []
            self._save()

    # ---- scheduled items (timers, alarms, reminders)
    def items(self):
        with self._lock:
            return [dict(i) for i in self.data["items"]]

    def set_items(self, items):
        with self._lock:
            self.data["items"] = items
            self._save()
