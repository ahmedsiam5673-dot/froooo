"""Timers, alarms and reminders. They survive restarts because they are saved in the Store."""
import datetime as dt
import threading
import time


class Scheduler:
    def __init__(self, store, on_due):
        self.store = store
        self.on_due = on_due  # on_due(item: dict, late_seconds: float)
        self._lock = threading.RLock()
        self._running = False
        self._thread = None

    def add(self, kind, due, label=""):
        with self._lock:
            items = self.store.items()
            new_id = max([i["id"] for i in items], default=0) + 1
            item = {
                "id": new_id,
                "kind": kind,
                "due": due.isoformat(timespec="seconds"),
                "label": label,
                "created": dt.datetime.now().isoformat(timespec="seconds"),
            }
            items.append(item)
            self.store.set_items(items)
            return item

    def list(self, kind=None):
        items = [i for i in self.store.items() if kind in (None, i["kind"])]
        return sorted(items, key=lambda i: i["due"])

    def cancel(self, kind=None, item_id=None):
        with self._lock:
            keep, removed = [], 0
            for i in self.store.items():
                hit = (item_id is not None and i["id"] == item_id) or (
                    item_id is None and kind in (None, i["kind"])
                )
                if hit:
                    removed += 1
                else:
                    keep.append(i)
            if removed:
                self.store.set_items(keep)
            return removed

    @staticmethod
    def remaining(item, now=None):
        now = now or dt.datetime.now()
        return (dt.datetime.fromisoformat(item["due"]) - now).total_seconds()

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="fro-scheduler")
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            try:
                self._tick()
            except Exception:
                pass
            time.sleep(0.5)

    def _tick(self):
        now = dt.datetime.now()
        due = []
        with self._lock:
            keep = []
            for i in self.store.items():
                if dt.datetime.fromisoformat(i["due"]) <= now:
                    due.append(i)
                else:
                    keep.append(i)
            if due:
                self.store.set_items(keep)
        for item in due:
            late = (now - dt.datetime.fromisoformat(item["due"])).total_seconds()
            self.on_due(item, late)
