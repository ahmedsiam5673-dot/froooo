"""The floating Siri-style ring that appears above everything when you say "Hey Fro".

It lives in its own click-through-where-transparent window, never steals keyboard focus,
and follows your voice (while you talk) and Fro's voice (while it answers).
"""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt, QTimer
from PySide6.QtGui import QFontMetrics, QGuiApplication
from PySide6.QtWidgets import QLabel, QWidget

from ..settings import settings
from .ring_orb import RingOrb
from .theme import CSS_FAMILY

ORB = 280
WIDTH = 720
CAP_SPACE = 190       # room for the caption next to the ring
CAP_MAX_W = 600


class Overlay(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(WIDTH, ORB + CAP_SPACE)

        self.orb = RingOrb(ORB, self)
        self.caption = QLabel("", self)
        self.caption.setWordWrap(True)
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption.setStyleSheet(
            f"QLabel {{ color: white; font: 600 17px {CSS_FAMILY}; background: rgba(12,16,26,210);"
            "border: 1px solid rgba(255,255,255,28); border-radius: 18px; padding: 11px 20px; }"
        )
        self.caption.hide()

        self._pop = QPropertyAnimation(self.orb, b"appear", self)
        self._pop.setEasingCurve(QEasingCurve.Type.OutBack)
        self._pop.finished.connect(self._after_anim)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._begin_hide)
        self._cap_timer = QTimer(self)
        self._cap_timer.setSingleShot(True)
        self._cap_timer.timeout.connect(self.caption.hide)
        self._hiding = False
        self._pending = None
        self._last_state = "idle"

        engine.state_changed.connect(self.on_state)
        engine.level_changed.connect(self.orb.set_level)
        engine.heard.connect(lambda t: self._caption(t, 0))
        engine.replied.connect(lambda t: self._caption(t, max(4500, 60 * len(t))))

    # ------------------------------------------------------------------ position / layout
    def _position(self):
        return settings.get("overlay_position") if settings.get("overlay_position") in ("top", "center", "bottom") else "top"

    def _place(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        pos = self._position()
        x = screen.center().x() - self.width() // 2
        if pos == "top":
            y = screen.top()
        elif pos == "center":
            y = screen.center().y() - self.height() // 2
        else:
            y = screen.bottom() - self.height() + 12
        self.move(x, y)
        self._layout_children()

    def _layout_children(self):
        pos = self._position()
        cap_h = 0
        if self.caption.isVisible() or self.caption.text():
            fm = QFontMetrics(self.caption.font())
            box = fm.boundingRect(QRect(0, 0, CAP_MAX_W - 44, 1000), Qt.TextFlag.TextWordWrap, self.caption.text())
            cap_w = min(CAP_MAX_W, box.width() + 48)
            cap_h = box.height() + 30
            self.caption.setGeometry((WIDTH - cap_w) // 2, 0, cap_w, cap_h)
        if pos == "bottom":
            orb_y = self.height() - ORB
            self.orb.move((WIDTH - ORB) // 2, orb_y)
            self.caption.move(self.caption.x(), max(0, int(orb_y + ORB * 0.17 - cap_h)))
        else:
            self.orb.move((WIDTH - ORB) // 2, 0)
            self.caption.move(self.caption.x(), int(ORB * 0.80))

    # ------------------------------------------------------------------ caption
    def _caption(self, text, hide_after):
        if not text.strip():
            return
        if not self.isVisible():
            if self.engine.voice_active:  # text arrived a moment before the ring: show it as soon as the ring is up
                self._pending = (text, hide_after)
            return
        self.caption.setText(text)
        self._layout_children()
        self.caption.show()
        self._cap_timer.stop()
        if hide_after:
            self._cap_timer.start(hide_after)

    # ------------------------------------------------------------------ show / hide
    def mousePressEvent(self, _):
        self.engine.speaker.stop()
        self._begin_hide()

    def on_state(self, state):
        previous, self._last_state = self._last_state, state
        self.orb.set_state(state)
        if state == "idle":
            if self.isVisible():
                self._hide_timer.start(1500 if self.caption.isVisible() else 450)
            return
        if not self.engine.voice_active:
            return  # typed in the main window: no ring
        self._hide_timer.stop()
        self._show()
        if previous in ("idle", "thinking") and state in ("listening", "speaking"):
            self.orb.pulse()

    def _show(self):
        if self.isVisible() and not self._hiding:
            return
        self._hiding = False
        self._place()
        if not self.isVisible():
            self.orb.appear = 0.0
            self.show()
            self.orb.pulse()
            if self._pending:
                text, hide_after = self._pending
                self._pending = None
                self._caption(text, hide_after)
        self._pop.stop()
        self._pop.setDuration(420)
        self._pop.setStartValue(self.orb.appear)
        self._pop.setEndValue(1.0)
        self._pop.start()

    def _begin_hide(self):
        if not self.isVisible() or self._hiding:
            return
        self._hiding = True
        self._pop.stop()
        self._pop.setDuration(260)
        self._pop.setStartValue(self.orb.appear)
        self._pop.setEndValue(0.0)
        self._pop.start()

    def _after_anim(self):
        if self._hiding:
            self._hiding = False
            self.hide()
            self.caption.hide()
            self.caption.setText("")
