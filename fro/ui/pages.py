"""Side pages of the main window: Tasks, Notes, Skills, Settings."""
import datetime as dt
import sys

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from ..settings import settings
from ..scheduler import Scheduler
from ..timeparse import human_duration
from .theme import ACCENT_HEX, CSS_FAMILY, SCROLLBAR_QSS
from .widgets import IconButton

TITLE_QSS = f"color: white; font: 700 26px {CSS_FAMILY}; background: transparent;"
SUB_QSS = f"color: rgba(255,255,255,110); font: 400 13px {CSS_FAMILY}; background: transparent;"
ROW_QSS = ("QFrame#row { background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,16);"
           " border-radius: 16px; }")
INPUT_QSS = (
    f"QLineEdit, QComboBox {{ color: white; font: 500 13px {CSS_FAMILY}; background: rgba(0,0,0,110);"
    "border: 1px solid rgba(255,255,255,30); border-radius: 12px; padding: 8px 12px; min-height: 20px; }"
    f"QLineEdit:focus {{ border: 1px solid {ACCENT_HEX}; }}"
    "QComboBox QAbstractItemView { background: #10151d; color: white; selection-background-color: #1296d6; }"
    "QComboBox::drop-down { border: none; width: 22px; }"
)


def header(title, sub):
    box = QVBoxLayout()
    box.setSpacing(4)
    a, b = QLabel(title), QLabel(sub)
    a.setStyleSheet(TITLE_QSS)
    b.setStyleSheet(SUB_QSS)
    box.addWidget(a)
    box.addWidget(b)
    return box


def scroll_list():
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setStyleSheet("QScrollArea { background: transparent; } QWidget#inner { background: transparent; }" + SCROLLBAR_QSS)
    inner = QWidget()
    inner.setObjectName("inner")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(0, 0, 8, 0)
    lay.setSpacing(10)
    lay.addStretch(1)
    area.setWidget(inner)
    return area, lay


def clear_layout(lay):
    while lay.count() > 1:
        item = lay.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


def empty_label(text):
    lab = QLabel(text)
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lab.setStyleSheet(f"color: rgba(255,255,255,90); font: 500 14px {CSS_FAMILY}; padding: 40px; background: transparent;")
    return lab


class TasksPage(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 36, 40, 30)
        lay.setSpacing(18)
        lay.addLayout(header("Timers & reminders", 'Try: "set a timer for 10 minutes", "remind me to call mom at 6 pm", "wake me up at 7"'))
        self.area, self.rows = scroll_list()
        lay.addWidget(self.area, 1)
        self._sig = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1000)
        self.refresh()

    def refresh(self):
        if not self.isVisible() and self._sig is not None:
            return
        items = self.engine.scheduler.list()
        sig = [(i["id"], i["due"]) for i in items]
        now = dt.datetime.now()
        if sig != self._sig:
            self._sig = sig
            clear_layout(self.rows)
            self.labels = {}
            if not items:
                self.rows.insertWidget(0, empty_label("Nothing scheduled"))
            for n, it in enumerate(items):
                row = QFrame()
                row.setObjectName("row")
                row.setStyleSheet(ROW_QSS)
                h = QHBoxLayout(row)
                h.setContentsMargins(18, 12, 12, 12)
                kind = {"timer": "⏱ Timer", "alarm": "⏰ Alarm", "reminder": "🔔 Reminder"}.get(it["kind"], it["kind"])
                title = QLabel(f"{kind}" + (f" — {it['label']}" if it["label"] and it["kind"] != "timer" else ""))
                title.setStyleSheet(f"color: white; font: 600 14px {CSS_FAMILY}; background: transparent;")
                when = QLabel()
                when.setStyleSheet(f"color: rgba(255,255,255,140); font: 500 13px {CSS_FAMILY}; background: transparent;")
                self.labels[it["id"]] = (when, it)
                rm = IconButton("trash", 32, ring=False)
                rm.clicked.connect(lambda _=False, i=it["id"]: (self.engine.scheduler.cancel(item_id=i), self.refresh()))
                h.addWidget(title, 1)
                h.addWidget(when)
                h.addWidget(rm)
                self.rows.insertWidget(n, row)
        for when, it in self.labels.values():
            left = Scheduler.remaining(it, now)
            due = dt.datetime.fromisoformat(it["due"])
            when.setText(f"in {human_duration(max(0, left))}" if it["kind"] == "timer" or left < 3600 * 5
                         else due.strftime("%a %H:%M"))


class NotesPage(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 36, 40, 30)
        lay.setSpacing(18)
        lay.addLayout(header("Notes & lists", 'Try: "take a note buy milk", "add eggs to my shopping list"'))
        self.area, self.rows = scroll_list()
        lay.addWidget(self.area, 1)
        self._ver = -1
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(800)
        self.refresh()

    def _row(self, text, sub, on_delete):
        row = QFrame()
        row.setObjectName("row")
        row.setStyleSheet(ROW_QSS)
        h = QHBoxLayout(row)
        h.setContentsMargins(18, 12, 12, 12)
        col = QVBoxLayout()
        col.setSpacing(2)
        a = QLabel(text)
        a.setWordWrap(True)
        a.setStyleSheet(f"color: white; font: 500 14px {CSS_FAMILY}; background: transparent;")
        b = QLabel(sub)
        b.setStyleSheet(f"color: rgba(255,255,255,100); font: 400 11px {CSS_FAMILY}; background: transparent;")
        col.addWidget(a)
        col.addWidget(b)
        rm = IconButton("trash", 32, ring=False)
        rm.clicked.connect(on_delete)
        h.addLayout(col, 1)
        h.addWidget(rm)
        return row

    def refresh(self):
        store = self.engine.store
        if store.version == self._ver:
            return
        self._ver = store.version
        clear_layout(self.rows)
        n = 0
        for idx, note in reversed(list(enumerate(store.notes()))):
            when = dt.datetime.fromisoformat(note["t"]).strftime("%d %b, %H:%M")
            self.rows.insertWidget(n, self._row(note["text"], when, lambda _=False, i=idx: store.delete_note(i)))
            n += 1
        for name, items in store.list_all().items():
            for it in items:
                self.rows.insertWidget(n, self._row(it, f"{name} list", lambda _=False, a=name, b=it: store.list_remove(a, b)))
                n += 1
        if n == 0:
            self.rows.insertWidget(0, empty_label("No notes yet"))


SKILLS = [
    ("Apps & web", ['open chrome', 'close spotify', 'search for cheap flights', 'go to github.com', 'play lofi on youtube']),
    ("Time", ["what time is it in Tokyo", "set a timer for 25 minutes", "wake me up at 6:30 am", "remind me to call mom at 6 pm"]),
    ("Answers", ["what's 15% of 240", "convert 5 miles to km", "100 dollars in euros", "what's the weather in Paris", "give me the news"]),
    ("Your PC", ["volume up / set volume to 40", "brightness 70", "take a screenshot", "what's on my screen", "dark mode", "battery", "lock my pc"]),
    ("Notes", ["take a note buy milk", "add eggs to my shopping list", "what's on my to-do list", "remember my wifi is fast"]),
    ("Messages", ["send an email to bob at gmail dot com", "message 8801700000000 saying hi", "add a meeting tomorrow at 3 pm to my calendar"]),
    ("Files", ["find the file resume", "open downloads", "create a folder projects", "summarize this file (drop it on Fro)"]),
    ("Chat", ["tell me a joke", "explain black holes", "translate 'good morning' to French", "my name is Rakin"]),
]


class SkillsPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 36, 40, 30)
        lay.setSpacing(18)
        lay.addLayout(header("What Fro can do", 'Say "Hey Fro" first, or press the hotkey / mic button. Anything else goes to the AI.'))
        area, rows = scroll_list()
        for n, (title, examples) in enumerate(SKILLS):
            row = QFrame()
            row.setObjectName("row")
            row.setStyleSheet(ROW_QSS)
            v = QVBoxLayout(row)
            v.setContentsMargins(18, 14, 18, 14)
            v.setSpacing(6)
            a = QLabel(title)
            a.setStyleSheet(f"color: {ACCENT_HEX}; font: 700 13px {CSS_FAMILY}; background: transparent;")
            b = QLabel("   •   ".join(f"“{e}”" for e in examples))
            b.setWordWrap(True)
            b.setStyleSheet(f"color: rgba(255,255,255,200); font: 400 13px {CSS_FAMILY}; background: transparent;")
            v.addWidget(a)
            v.addWidget(b)
            rows.insertWidget(n, row)
        lay.addWidget(area, 1)


class SettingsPage(QWidget):
    saved = Signal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 36, 40, 30)
        lay.setSpacing(14)
        lay.addLayout(header("Settings", "Everything is saved on this PC."))
        area, rows = scroll_list()
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        form = QFormLayout(wrap)
        form.setContentsMargins(0, 0, 8, 0)
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(20)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        def label(t):
            lb = QLabel(t)
            lb.setStyleSheet(f"color: rgba(255,255,255,170); font: 500 13px {CSS_FAMILY}; background: transparent;")
            return lb

        self.name = QLineEdit()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("sk-ant-...  (needed for AI answers)")
        self.lang = QComboBox()
        for code, name in (("en-US", "English (US)"), ("en-GB", "English (UK)"), ("en-IN", "English (India)"),
                           ("bn-BD", "Bangla (Bangladesh)"), ("bn-IN", "Bangla (India)"), ("hi-IN", "Hindi"),
                           ("ar-SA", "Arabic"), ("es-ES", "Spanish"), ("fr-FR", "French"), ("de-DE", "German")):
            self.lang.addItem(name, code)
        self.wake = QLineEdit()
        self.wake.setPlaceholderText("hey fro")
        self.wake_on = QCheckBox("Listen for the wake word all the time")
        self.tts_on = QCheckBox("Speak answers out loud")
        self.voice = QLineEdit()
        self.voice_bn = QLineEdit()
        self.hotkey = QLineEdit()
        self.overlay_pos = QComboBox()
        for key, name in (("top", "Top of the screen"), ("center", "Middle of the screen"), ("bottom", "Bottom of the screen")):
            self.overlay_pos.addItem(name, key)
        self.chime = QCheckBox("Play a soft sound when Fro starts listening")
        self.city = QLineEdit()
        self.city.setPlaceholderText("auto-detect")
        self.music = QComboBox()
        self.music.addItem("YouTube", "youtube")
        self.music.addItem("Spotify", "spotify")
        self.autostart = QCheckBox("Start Fro when Windows starts")
        for cb in (self.wake_on, self.tts_on, self.autostart, self.chime):
            cb.setStyleSheet(f"QCheckBox {{ color: white; font: 500 13px {CSS_FAMILY}; background: transparent; spacing: 10px; }}")
        for w in (self.name, self.key, self.lang, self.wake, self.voice, self.voice_bn, self.hotkey, self.city,
                  self.music, self.overlay_pos):
            w.setStyleSheet(INPUT_QSS)
        form.addRow(label("Your name"), self.name)
        form.addRow(label("Anthropic API key"), self.key)
        form.addRow(label("Language you speak"), self.lang)
        form.addRow(label("Wake word"), self.wake)
        form.addRow("", self.wake_on)
        form.addRow("", self.tts_on)
        form.addRow(label("Voice (English)"), self.voice)
        form.addRow(label("Voice (Bangla)"), self.voice_bn)
        form.addRow(label("Hotkey"), self.hotkey)
        form.addRow(label("Ring position"), self.overlay_pos)
        form.addRow("", self.chime)
        form.addRow(label("Weather city"), self.city)
        form.addRow(label("Music service"), self.music)
        if sys.platform == "win32":
            form.addRow("", self.autostart)
        rows.insertWidget(0, wrap)
        lay.addWidget(area, 1)

        bar = QHBoxLayout()
        self.status = QLabel("")
        self.status.setStyleSheet(f"color: {ACCENT_HEX}; font: 600 13px {CSS_FAMILY}; background: transparent;")
        btn = QPushButton("Save")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(110, 38)
        btn.setStyleSheet(
            f"QPushButton {{ color: white; font: 600 14px {CSS_FAMILY}; background: {ACCENT_HEX}; border: none; border-radius: 19px; }}"
            "QPushButton:hover { background: #2aa8e6; }"
        )
        btn.clicked.connect(self.save)
        bar.addWidget(self.status, 1)
        bar.addWidget(btn)
        lay.addLayout(bar)
        self.load()

    def load(self):
        s = settings
        self.name.setText(s.data.get("user_name", ""))
        self.key.setText(s.data.get("api_key", ""))
        self.lang.setCurrentIndex(max(0, self.lang.findData(s.get("language"))))
        self.wake.setText(s.get("wake_word"))
        self.wake_on.setChecked(bool(s.get("wake_enabled")))
        self.tts_on.setChecked(bool(s.get("tts_enabled")))
        self.voice.setText(s.get("tts_voice"))
        self.voice_bn.setText(s.get("tts_voice_bn"))
        self.hotkey.setText(s.get("hotkey"))
        self.overlay_pos.setCurrentIndex(max(0, self.overlay_pos.findData(s.get("overlay_position"))))
        self.chime.setChecked(bool(s.get("chime")))
        self.city.setText(s.get("weather_city"))
        self.music.setCurrentIndex(max(0, self.music.findData(s.get("music_service"))))
        self.autostart.setChecked(bool(s.get("start_with_windows")))

    def save(self):
        settings.update({
            "user_name": self.name.text().strip(),
            "api_key": self.key.text().strip(),
            "language": self.lang.currentData(),
            "wake_word": self.wake.text().strip().lower() or "hey fro",
            "wake_enabled": self.wake_on.isChecked(),
            "tts_enabled": self.tts_on.isChecked(),
            "tts_voice": self.voice.text().strip() or "en-US-AriaNeural",
            "tts_voice_bn": self.voice_bn.text().strip() or "bn-BD-NabanitaNeural",
            "hotkey": self.hotkey.text().strip().lower() or "ctrl+alt+space",
            "overlay_position": self.overlay_pos.currentData(),
            "chime": self.chime.isChecked(),
            "weather_city": self.city.text().strip(),
            "music_service": self.music.currentData(),
            "start_with_windows": self.autostart.isChecked(),
        })
        self.status.setText("Saved ✓")
        QTimer.singleShot(2500, lambda: self.status.setText(""))
        self.saved.emit()
