"""Draws the Fro ring icon and saves assets/fro.ico (+ fro.png). Run:  python tools/make_icon.py"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PIL import Image  # noqa: E402
from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QColor, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from fro.ui.ring_orb import RingOrb  # noqa: E402


def main():
    app = QApplication([])
    orb = RingOrb(512)
    orb.set_state("listening")
    orb.set_level(0.35)
    orb._t = 3.2
    for _ in range(40):
        orb._tick()
    pm = QPixmap(512, 512)
    pm.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pm)
    orb.render(painter, QPoint(0, 0))
    painter.end()
    # dark rounded tile behind the ring so it is visible on any taskbar
    tile = QPixmap(512, 512)
    tile.fill(QColor(0, 0, 0, 0))
    tp = QPainter(tile)
    tp.setRenderHint(QPainter.RenderHint.Antialiasing)
    tp.setBrush(QColor(8, 11, 24))
    tp.setPen(QColor(0, 0, 0, 0))
    tp.drawRoundedRect(8, 8, 496, 496, 112, 112)
    tp.drawPixmap(0, 0, pm)
    tp.end()
    out = os.path.join(ROOT, "assets")
    os.makedirs(out, exist_ok=True)
    png = os.path.join(out, "fro.png")
    tile.save(png)
    img = Image.open(png).convert("RGBA")
    img.save(os.path.join(out, "fro.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icon written to", out)


if __name__ == "__main__":
    main()
