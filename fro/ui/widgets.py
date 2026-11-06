"""Small custom widgets: painted icon buttons, chat bubbles, suggestion cards."""
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from .theme import ACCENT, CSS_FAMILY, font


def draw_icon(p: QPainter, name: str, rect: QRectF, color: QColor):
    """Tiny line icons drawn by hand so there are no image files to ship."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(color, max(1.5, rect.width() * 0.09), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    c = rect.center()
    if name == "home":
        path = QPainterPath()
        path.moveTo(x + w * 0.12, y + h * 0.48)
        path.lineTo(c.x(), y + h * 0.1)
        path.lineTo(x + w * 0.88, y + h * 0.48)
        path.moveTo(x + w * 0.22, y + h * 0.42)
        path.lineTo(x + w * 0.22, y + h * 0.88)
        path.lineTo(x + w * 0.78, y + h * 0.88)
        path.lineTo(x + w * 0.78, y + h * 0.42)
        p.drawPath(path)
    elif name == "clock":
        p.drawEllipse(c, w * 0.40, h * 0.40)
        p.drawLine(c, QPointF(c.x(), y + h * 0.26))
        p.drawLine(c, QPointF(x + w * 0.70, c.y() + h * 0.08))
    elif name == "note":
        p.drawRoundedRect(QRectF(x + w * 0.2, y + h * 0.12, w * 0.6, h * 0.76), 3, 3)
        for i in range(3):
            yy = y + h * (0.34 + 0.16 * i)
            p.drawLine(QPointF(x + w * 0.32, yy), QPointF(x + w * 0.68, yy))
    elif name == "grid":
        s = w * 0.28
        for i in range(2):
            for j in range(2):
                p.drawRoundedRect(QRectF(x + w * (0.16 + 0.38 * i), y + h * (0.16 + 0.38 * j), s, s), 2, 2)
    elif name == "gear":
        p.drawEllipse(c, w * 0.17, h * 0.17)
        import math

        for k in range(8):
            a = k * math.pi / 4
            p.drawLine(QPointF(c.x() + w * 0.30 * math.cos(a), c.y() + h * 0.30 * math.sin(a)),
                       QPointF(c.x() + w * 0.42 * math.cos(a), c.y() + h * 0.42 * math.sin(a)))
        p.drawEllipse(c, w * 0.30, h * 0.30)
    elif name == "mic":
        p.drawRoundedRect(QRectF(x + w * 0.37, y + h * 0.1, w * 0.26, h * 0.46), w * 0.13, w * 0.13)
        path = QPainterPath()
        path.moveTo(x + w * 0.24, y + h * 0.46)
        path.arcTo(QRectF(x + w * 0.24, y + h * 0.24, w * 0.52, h * 0.5), 180, 180)
        p.drawPath(path)
        p.drawLine(QPointF(c.x(), y + h * 0.74), QPointF(c.x(), y + h * 0.9))
    elif name == "up":
        p.drawLine(QPointF(c.x(), y + h * 0.80), QPointF(c.x(), y + h * 0.22))
        p.drawLine(QPointF(c.x(), y + h * 0.22), QPointF(x + w * 0.24, y + h * 0.46))
        p.drawLine(QPointF(c.x(), y + h * 0.22), QPointF(x + w * 0.76, y + h * 0.46))
    elif name == "clip":
        p.drawEllipse(QRectF(x + w * 0.2, y + h * 0.2, w * 0.6, h * 0.6))
    elif name == "tools":
        for i, off in enumerate((0.3, 0.7)):
            yy = y + h * off
            p.drawLine(QPointF(x + w * 0.12, yy), QPointF(x + w * 0.88, yy))
            p.drawEllipse(QPointF(x + w * (0.35 if i == 0 else 0.65), yy), w * 0.09, w * 0.09)
    elif name == "close":
        p.drawLine(QPointF(x + w * 0.28, y + h * 0.28), QPointF(x + w * 0.72, y + h * 0.72))
        p.drawLine(QPointF(x + w * 0.72, y + h * 0.28), QPointF(x + w * 0.28, y + h * 0.72))
    elif name == "minimize":
        p.drawLine(QPointF(x + w * 0.25, c.y()), QPointF(x + w * 0.75, c.y()))
    elif name == "trash":
        p.drawLine(QPointF(x + w * 0.22, y + h * 0.28), QPointF(x + w * 0.78, y + h * 0.28))
        p.drawRoundedRect(QRectF(x + w * 0.3, y + h * 0.32, w * 0.4, h * 0.52), 2, 2)
        p.drawLine(QPointF(x + w * 0.42, y + h * 0.18), QPointF(x + w * 0.58, y + h * 0.18))
    p.restore()


class IconButton(QPushButton):
    def __init__(self, icon, size=42, filled=False, ring=True, parent=None, tip=""):
        super().__init__(parent)
        self.icon_name, self.d, self.filled, self.ring = icon, size, filled, ring
        self.active = False
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        if tip:
            self.setToolTip(tip)

    def set_active(self, v):
        self.active = v
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(1, 1, self.d - 2, self.d - 2)
        hot = self.underMouse()
        if self.active or self.filled:
            p.setPen(Qt.PenStyle.NoPen)
            col = QColor(ACCENT)
            if hot:
                col = col.lighter(115)
            p.setBrush(col)
            p.drawEllipse(r)
            icon_col = QColor(255, 255, 255)
        else:
            if self.ring:
                p.setPen(QPen(QColor(255, 255, 255, 60 if hot else 35), 1))
                p.setBrush(QColor(255, 255, 255, 18 if hot else 6))
                p.drawEllipse(r)
            icon_col = QColor(255, 255, 255, 235 if hot else 190)
        pad = self.d * 0.27
        draw_icon(p, self.icon_name, QRectF(pad, pad, self.d - 2 * pad, self.d - 2 * pad), icon_col)
        p.end()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)


class PillButton(QPushButton):
    def __init__(self, text, icon=None, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self.setStyleSheet(
            f"QPushButton {{ color: rgba(255,255,255,200); font: 500 12px {CSS_FAMILY}; padding: 0 16px;"
            "background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,40); border-radius: 17px; }"
            "QPushButton:hover { background: rgba(255,255,255,24); }"
        )


class Bubble(QFrame):
    def __init__(self, text, mine, parent=None):
        super().__init__(parent)
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lab.setMaximumWidth(520)
        bg = "rgba(18,150,214,150)" if mine else "rgba(255,255,255,16)"
        lab.setStyleSheet(
            f"QLabel {{ color: white; font: 500 14px {CSS_FAMILY}; background: {bg};"
            "border-radius: 16px; padding: 10px 15px; }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(lab, 0, Qt.AlignmentFlag.AlignRight if mine else Qt.AlignmentFlag.AlignLeft)


class SuggestionCard(QFrame):
    clicked = Signal()

    def __init__(self, title, desc, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(76)
        self.setStyleSheet(
            "SuggestionCard { background: rgba(255,255,255,10); border: 1px solid rgba(255,255,255,18); border-radius: 18px; }"
            "SuggestionCard:hover { background: rgba(255,255,255,20); }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 10)
        lay.setSpacing(3)
        a = QLabel(title)
        a.setStyleSheet(f"color: white; font: 600 14px {CSS_FAMILY}; background: transparent;")
        b = QLabel(desc)
        b.setWordWrap(True)
        b.setStyleSheet(f"color: rgba(255,255,255,110); font: 400 12px {CSS_FAMILY}; background: transparent;")
        lay.addWidget(a)
        lay.addWidget(b)
        lay.addStretch(1)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
