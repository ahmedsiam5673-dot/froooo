"""The colourful glass sphere in the main window (2D, painted live)."""
import math
import random

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QRadialGradient, QLinearGradient
from PySide6.QtWidgets import QWidget

BLOBS = [  # colour, orbit radius, speed, phase, size
    ((40, 70, 255), 0.42, 0.55, 0.0, 0.85),
    ((255, 60, 150), 0.50, -0.42, 1.7, 0.60),
    ((255, 170, 60), 0.46, 0.70, 3.1, 0.50),
    ((40, 220, 255), 0.55, -0.60, 4.4, 0.62),
    ((150, 60, 255), 0.35, 0.38, 5.6, 0.75),
]


class SphereOrb(QWidget):
    def __init__(self, size=150, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.state = "idle"
        self._t = random.random() * 10
        self._energy = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_state(self, state):
        self.state = state

    def showEvent(self, e):
        self._timer.start(33)
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def _tick(self):
        target = {"idle": 0.0, "listening": 0.7, "thinking": 1.0, "speaking": 0.85}.get(self.state, 0.0)
        self._energy += (target - self._energy) * 0.1
        self._t += 0.033 * (0.6 + 1.6 * self._energy)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        c = w / 2
        R = w * 0.46
        t, en = self._t, self._energy
        disc = QPainterPath()
        disc.addEllipse(QPointF(c, c), R, R)

        p.save()
        p.setClipPath(disc)
        p.fillPath(disc, QColor(6, 8, 30))
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
        for (r, g, b), orbit, speed, phase, size in BLOBS:
            ang = t * speed + phase
            x = c + R * orbit * math.cos(ang) * (1 + 0.25 * en)
            y = c + R * orbit * math.sin(ang * 1.3) * (1 + 0.25 * en)
            rad = R * size * (1 + 0.12 * math.sin(t * 1.7 + phase))
            grad = QRadialGradient(QPointF(x, y), rad)
            grad.setColorAt(0.0, QColor(r, g, b, 230))
            grad.setColorAt(0.55, QColor(r, g, b, 90))
            grad.setColorAt(1.0, QColor(r, g, b, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(grad)
            p.drawEllipse(QPointF(x, y), rad, rad)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        # dark ribbon crossing the sphere
        ribbon = QPainterPath()
        ribbon.moveTo(c - R, c + R * 0.1)
        sway = R * 0.35 * math.sin(t * 0.9)
        ribbon.cubicTo(c - R * 0.3, c - R * 0.4 + sway, c + R * 0.2, c + R * 0.5 - sway, c + R, c - R * 0.05)
        p.setPen(QPen(QColor(4, 4, 18, 200), R * 0.16, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(ribbon)

        # glass highlight top-left + soft dark vignette
        hl = QRadialGradient(QPointF(c - R * 0.35, c - R * 0.45), R * 0.9)
        hl.setColorAt(0.0, QColor(255, 255, 255, 70))
        hl.setColorAt(0.5, QColor(255, 255, 255, 0))
        p.fillPath(disc, hl)
        vg = QRadialGradient(QPointF(c, c), R)
        vg.setColorAt(0.7, QColor(0, 0, 0, 0))
        vg.setColorAt(1.0, QColor(0, 0, 0, 120))
        p.fillPath(disc, vg)
        p.restore()

        p.setPen(QPen(QColor(0, 0, 0, 230), w * 0.025))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(c, c), R + w * 0.012, R + w * 0.012)
        p.end()
