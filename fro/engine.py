"""The assistant's brain stem: listens for the wake word, runs commands, speaks the answer.

It runs in its own thread and talks to the UI only through Qt signals.
"""
import logging
import queue
import re
import threading
import time

from PySide6.QtCore import QObject, Signal

from .brain import Brain
from .scheduler import Scheduler
from .settings import settings
from .skills import Hooks, Router
from .store import Store
from .voice import Listener, Speaker

log = logging.getLogger("fro.engine")

_WAKE_DEFAULT = r"(?:hey|hay|hi|ok|okay|yo)[ ,]+(?:fro|pro|foe|froh|frow|throw|frau)\b"
_WAKE_BN = r"(?:হে|হেই|ওকে)\s*ফ্রো|ফ্রো"


def build_wake_regex() -> "re.Pattern":
    custom = (settings.get("wake_word") or "").strip().lower()
    parts = [_WAKE_DEFAULT, _WAKE_BN, r"^\s*fro\b"]
    if custom and custom not in ("hey fro", "fro"):
        parts.insert(0, re.escape(custom))
    return re.compile("|".join(parts), re.I)


class _EngineHooks(Hooks):
    def __init__(self, engine):
        self.e = engine

    def quit_app(self):
        self.e.quit_requested.emit()

    def show_main(self):
        self.e.main_requested.emit()

    def show_page(self, name):
        self.e.page_requested.emit(name)

    def stop_speaking(self):
        self.e.speaker.stop()

    def copy_text(self, text):
        self.e.copy_requested.emit(text)


class Engine(QObject):
    state_changed = Signal(str)       # idle | listening | thinking | speaking
    level_changed = Signal(float)     # microphone loudness 0..1
    heard = Signal(str)               # what the user said / typed
    replied = Signal(str)             # what Fro answers
    notify = Signal(str, str)         # tray notification (title, text)
    page_requested = Signal(str)
    main_requested = Signal()
    quit_requested = Signal()
    copy_requested = Signal(str)
    mic_status = Signal(bool)

    def __init__(self):
        super().__init__()
        self.store = Store()
        self.listener = Listener()
        self.speaker = Speaker()
        self.brain = Brain(self.store)
        self.scheduler = Scheduler(self.store, self._on_due)
        self.router = Router(self.store, self.scheduler, self.brain, _EngineHooks(self))
        self.state = "idle"
        self.voice_active = False  # True while a spoken session / alert runs (the ring overlay follows this)
        self.speaker.level_cb = self.level_changed.emit
        self._q = queue.Queue()
        self._running = False
        self._thread = None
        self._wake_rx = build_wake_regex()

    # ------------------------------------------------------------ public API (any thread)
    def start(self):
        self._running = True
        self.scheduler.start()
        self._thread = threading.Thread(target=self._run, daemon=True, name="fro-engine")
        self._thread.start()

    def stop(self):
        self._running = False
        self.scheduler.stop()
        self.speaker.stop()
        if self._thread:
            self._thread.join(timeout=2)
        self.listener.close()

    def reload_settings(self):
        self._wake_rx = build_wake_regex()

    def trigger(self):
        """Hotkey or mic button: stop talking if speaking, otherwise start listening."""
        if self.state == "speaking":
            self.speaker.stop()
        else:
            self._q.put(("listen",))

    def submit(self, text: str):
        text = text.strip()
        if text:
            self._q.put(("text", text))

    def submit_file(self, path: str, question: str = ""):
        self._q.put(("file", path, question))

    # ------------------------------------------------------------ worker thread
    def _run(self):
        self.mic_status.emit(self.listener.open())
        while self._running:
            try:
                wake_on = settings.get("wake_enabled") and self.listener.ok
                task = self._q.get(timeout=0.05 if wake_on else 0.3)
            except queue.Empty:
                task = None
            try:
                if task:
                    self._do(task)
                elif settings.get("wake_enabled") and self.listener.ok:
                    self._wake_step()
            except Exception:
                log.exception("engine loop error")
                self._set_state("idle")

    def _do(self, task):
        kind = task[0]
        if kind == "listen":
            self._session("")
        elif kind == "text":
            self._respond(task[1], voice=False)
            self._set_state("idle")
        elif kind == "file":
            self._set_state("thinking")
            self.heard.emit(f"📎 {task[1].split(chr(92))[-1].split('/')[-1]}")
            reply = self.router.handle_file(task[1], task[2])
            self._finish_reply(reply)
            self._set_state("idle")
        elif kind == "notify":
            self._announce(task[1], task[2])

    def _wake_step(self):
        text = self.listener.listen(timeout=1.0, phrase_limit=9)
        if not text:
            return
        m = self._wake_rx.search(text.lower())
        if not m:
            return
        self._session(text[m.end():].strip(" ,.!?"))

    def _session(self, first_command: str):
        """One spoken conversation: wake -> command -> answer, then keep listening while Fro expects a reply."""
        self.voice_active = True
        try:
            command, first = first_command, True
            while True:
                if not command:
                    self._set_state("listening")
                    if first:
                        self.speaker.chime()
                        self.listener.flush()
                    command = self._listen_command(timeout=7)
                    if not command:
                        break
                first = False
                reply = self._respond(command, voice=True)
                command = ""
                if not (reply and reply.expect):
                    break
        finally:
            self.voice_active = False
            self._set_state("idle")

    def _listen_command(self, timeout):
        self._set_state("listening")
        text = self.listener.listen(timeout=timeout, phrase_limit=15, level_cb=self.level_changed.emit)
        return text.strip()

    def _respond(self, command, voice):
        self.heard.emit(command)
        self._set_state("thinking")
        reply = self.router.handle(command)
        return self._finish_reply(reply, voice)

    def _finish_reply(self, reply, voice=False):
        if reply.text:
            self.replied.emit(reply.text)
        if reply.speak and reply.text and settings.get("tts_enabled"):
            self._set_state("speaking")
            self.speaker.speak(reply.text)
            self.listener.flush()
        if reply.expect and not voice:
            pass  # typed conversation: the next typed message answers the question
        return reply

    # ------------------------------------------------------------ timers / alarms / reminders
    def _on_due(self, item, late):
        self._q.put(("notify", item, late))

    def _announce(self, item, late):
        kind, label = item["kind"], item.get("label", "")
        missed = late > 90
        if kind == "timer":
            text = f"Your {label} timer is done." if label else "Your timer is done."
        elif kind == "alarm":
            text = "Alarm!" + (f" {label}." if label else "")
        else:
            text = f"Reminder: {label}." if label else "Here's your reminder."
        if missed:
            text = "Missed while Fro was closed: " + text
        title = {"timer": "Timer", "alarm": "Alarm", "reminder": "Reminder"}.get(kind, "Fro")
        self.voice_active = True
        self.notify.emit(title, text)
        self.replied.emit(text)
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass
        self._set_state("speaking")
        if settings.get("tts_enabled"):
            self.speaker.speak(text)
        else:
            time.sleep(3)
        self.voice_active = False
        self._set_state("idle")

    def _set_state(self, state):
        if state != self.state:
            self.state = state
            self.state_changed.emit(state)
