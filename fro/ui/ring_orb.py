"""The glowing ring that appears at the bottom of the screen when Fro listens (Siri-style).

Drawn live with QPainter so it has a transparent background and reacts to your voice.
"""
import math
import random
import time

from PySide6.QtCore import Property, QPointF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

# top (warm) -> bottom (cool), like the reference animation
STOPS = [
    (0.00, (255, 176, 112)),
    (0.20, (248, 98, 172)),
    (0.45, (168, 84, 240)),
    (0.72, (72, 104, 255)),
    (1.00, (38, 156, 255)),
]
CORE_STOPS = [
    (0.00, (255, 214, 170)),
    (0.22, (255, 150, 210)),
    (0.48, (205, 150, 255)),
    (0.75, (130, 170, 255)),
    (1.00, (110, 205, 255)),
]


def _vgrad(y0, y1, alpha=1.0, stops=STOPS, x=0.0):
    g = QLinearGradient(x, y0, x, y1)
    for pos, (r, gr, b) in stops:
        g.setColorAt(pos, QColor(r, gr, b, max(0, min(255, int(255 * alpha)))))
    return g


class RingOrb(QWidget):
    def __init__(self, size=250, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.state = "idle"
        self._input = 0.0
        self._input_ts = 0.0
        self._pulse = 0.0
        self._lvl = 0.0
        self._t = random.random() * 10
        self._appear = 1.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # animated 0..1 "pop in" value
    def _get_appear(self):
        return self._appear

    def _set_appear(self, v):
        self._appear = v
        self.update()

    appear = Property(float, _get_appear, _set_appear)

    def set_state(self, state):
        self.state = state

    def set_level(self, level):
        """Real loudness (0..1): your microphone while listening, Fro's own voice while speaking."""
        self._input = max(0.0, min(1.0, level))
        self._input_ts = time.monotonic()

    def pulse(self):
        """Send a ripple outwards (used when Fro wakes up)."""
        self._pulse = 1.0

    def showEvent(self, e):
        self._timer.start(16)
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def _tick(self):
        speed = {"idle": 0.7, "listening": 1.0, "thinking": 2.3, "speaking": 1.5}.get(self.state, 1.0)
        self._t += 0.016 * speed
        t = self._t
        fresh = time.monotonic() - self._input_ts < 0.3
        if self.state == "speaking":
            if fresh:  # follows the real voice
                target = 0.14 + self._input * 0.95
            else:
                target = 0.30 + 0.30 * abs(math.sin(t * 3.3) * math.sin(t * 1.7 + 1.0)) + 0.14 * abs(math.sin(t * 8.1))
        elif self.state == "thinking":
            target = 0.24 + 0.08 * math.sin(t * 2.0)
        elif self.state == "listening":
            target = 0.12 + (self._input * 0.95 if fresh else 0.0)
        else:
            target = 0.08
        self._lvl += (target - self._lvl) * (0.35 if fresh else 0.2)
        self._pulse = max(0.0, self._pulse - 0.028)
        self.update()

    # ------------------------------------------------------------ drawing
    def _blob(self, cx, cy, radius):
        t, lv = self._t, self._lvl
        path = QPainterPath()
        n = 120
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            k = (1 + 0.035 * math.sin(2 * a + 1.3 * t) + 0.030 * math.sin(3 * a - 1.1 * t + 0.5)
                 + 0.018 * math.sin(5 * a + 2.1 * t) + lv * 0.07 * math.sin(4 * a + 3.2 * t))
            x, y = cx + radius * k * math.cos(a), cy + radius * k * math.sin(a)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        path.closeSubpath()
        return path

    def paintEvent(self, _):
        s = self._appear
        if s <= 0.01:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(min(1.0, s * 1.25))
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        R = min(w, h) * 0.30 * (0.6 + 0.4 * s)
        t, lv = self._t, self._lvl
        plus = QPainter.CompositionMode.CompositionMode_Plus
        over = QPainter.CompositionMode.CompositionMode_SourceOver
        blob = self._blob(cx, cy, R)

        # soft dark halo behind the ring so the colours stay vivid on any desktop background
        halo = QRadialGradient(QPointF(cx, cy), R * 1.55)
        halo.setColorAt(0.0, QColor(6, 8, 22, 225))
        halo.setColorAt(0.6, QColor(6, 8, 22, 170))
        halo.setColorAt(1.0, QColor(6, 8, 22, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), R * 1.55, R * 1.55)

        # --- inside: soft rim glow, the "lid" with its wavy surface, hot spots
        p.save()
        p.setClipPath(blob)
        p.setCompositionMode(plus)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for width, alpha in ((R * 0.60, 0.10), (R * 0.34, 0.15), (R * 0.16, 0.24)):
            p.setPen(QPen(QBrush(_vgrad(cy - R, cy + R, alpha)), width))
            p.drawPath(blob)

        frac = 0.22 + 0.14 * math.sin(t * 0.8 + 0.5) + 0.10 * math.sin(t * 1.9) + 0.18 * lv
        frac = max(0.05, min(0.6, frac))
        amp = R * (0.03 + 0.10 * lv)
        line_y = cy - R * frac
        pts = []
        steps = 64
        x0, span = cx - R * 1.25, R * 2.5
        for i in range(steps + 1):
            u = i / steps
            env = 0.35 + 0.65 * math.sin(math.pi * u)
            y = line_y + amp * env * (0.6 * math.sin(u * 9 + t * 3.0) + 0.4 * math.sin(u * 17 - t * 4.3))
            pts.append(QPointF(x0 + span * u, y))
        cap = QPainterPath(pts[0])
        for pt in pts[1:]:
            cap.lineTo(pt)
        cap.lineTo(x0 + span, cy - R * 1.6)
        cap.lineTo(x0, cy - R * 1.6)
        cap.closeSubpath()
        fill = QLinearGradient(0, cy - R * 1.1, 0, line_y)
        fill.setColorAt(0.0, QColor(236, 84, 176, 150))
        fill.setColorAt(0.65, QColor(150, 80, 235, 80))
        fill.setColorAt(1.0, QColor(170, 90, 255, 38))
        p.fillPath(cap, fill)

        line = QPainterPath(pts[0])
        for pt in pts[1:]:
            line.lineTo(pt)
        line_cols = ((0.0, (255, 170, 100)), (0.5, (232, 90, 210)), (1.0, (255, 170, 110)))
        for width, alpha in ((R * 0.12, 0.22), (R * 0.05, 0.55), (max(1.5, R * 0.018), 1.0)):
            g = QLinearGradient(cx - R, 0, cx + R, 0)
            for pos, (cr, cg, cb) in line_cols:
                g.setColorAt(pos, QColor(cr, cg, cb, int(255 * alpha)))
            p.setPen(QPen(QBrush(g), width))
            p.drawPath(line)
        dy = line_y - cy
        off = math.sqrt(max(0.0, R * R - dy * dy))
        for sign in (-1, 1):
            hx = cx + sign * off
            glow = QRadialGradient(hx, line_y, R * 0.20)
            glow.setColorAt(0.0, QColor(255, 175, 110, 200))
            glow.setColorAt(1.0, QColor(255, 120, 150, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(QPointF(hx, line_y), R * 0.2, R * 0.2)
        p.restore()

        # --- outside glow + bright core ring
        p.setCompositionMode(plus)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for width, alpha in ((R * 0.34, 0.07), (R * 0.20, 0.12), (R * 0.10, 0.24), (R * 0.045, 0.55)):
            p.setPen(QPen(QBrush(_vgrad(cy - R, cy + R, alpha)), width))
            p.drawPath(blob)
        p.setCompositionMode(over)
        p.setPen(QPen(QBrush(_vgrad(cy - R, cy + R, 1.0, CORE_STOPS)), max(1.6, R * 0.016)))
        p.drawPath(blob)

        # wake-up ripple: a soft ring that expands and fades
        if self._pulse > 0.01:
            grow = 1.04 + 0.5 * (1.0 - self._pulse) ** 0.6
            rr = R * grow
            p.setCompositionMode(plus)
            p.setBrush(Qt.BrushStyle.NoBrush)
            for width, a in ((R * 0.10, 0.22), (R * 0.03, 0.55)):
                p.setPen(QPen(QBrush(_vgrad(cy - rr, cy + rr, a * self._pulse)), width))
                p.drawEllipse(QPointF(cx, cy), rr, rr)
        p.end()
