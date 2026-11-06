"""Colors and fonts shared by the whole UI (matches the dark teal 2D design)."""
from PySide6.QtGui import QColor, QFont

ACCENT = QColor(18, 150, 214)
ACCENT_HEX = "#1296d6"
TEXT = QColor(255, 255, 255)
MUTED = QColor(255, 255, 255, 105)

FAMILIES = ["Segoe UI Variable Display", "Segoe UI", "Inter", "SF Pro Display", "Helvetica Neue", "Arial"]
CSS_FAMILY = '"Segoe UI Variable Display", "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif'


def font(px: int, weight=QFont.Weight.Medium, spacing: float = 0.0) -> QFont:
    f = QFont()
    f.setFamilies(FAMILIES)
    f.setPixelSize(px)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


SCROLLBAR_QSS = """
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(255,255,255,40); border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: rgba(255,255,255,70); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
"""
