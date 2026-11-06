"""Application bootstrap: tray icon, hotkey, single-instance lock, auto-start."""
import logging
import sys

from PySide6.QtCore import QLockFile, QPoint, QTimer, Qt
from PySide6.QtGui import QAction, QClipboard, QColor, QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import APP_NAME
from .engine import Engine
from .paths import data_dir
from .settings import settings
from .ui.main_window import MainWindow
from .ui.overlay import Overlay
from .ui.ring_orb import RingOrb

log = logging.getLogger("fro")


def make_icon() -> QIcon:
    orb = RingOrb(256)
    orb.set_state("listening")
    orb.set_level(0.35)
    for _ in range(25):
        orb._tick()
    pm = QPixmap(256, 256)
    pm.fill(QColor(7, 9, 20))
    painter = QPainter(pm)
    orb.render(painter, QPoint(0, 0))
    painter.end()
    return QIcon(pm)


def set_autostart(enabled: bool):
    if sys.platform != "win32":
        return
    import winreg

    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
    try:
        if enabled:
            exe = sys.executable if getattr(sys, "frozen", False) else f'"{sys.executable}" -m fro'
            cmd = f'"{exe}" --background' if getattr(sys, "frozen", False) else f"{exe} --background"
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)


def selftest() -> int:
    """`Fro.exe --selftest`: checks that every bundled library loads and the UI can be built.
    Used by GitHub Actions to make sure the freshly built exe really starts."""
    import importlib
    import os
    import tempfile

    if not getattr(sys, "frozen", False):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    mods = ["speech_recognition", "pyaudio", "edge_tts", "pygame", "pyttsx3", "keyboard", "psutil",
            "requests", "anthropic", "PIL.ImageGrab", "pypdf", "screen_brightness_control"]
    if sys.platform == "win32":
        mods += ["comtypes", "pycaw.pycaw", "pythoncom", "win32com.client", "winreg", "winsound"]
    lines, bad = [], 0
    for name in mods:
        try:
            importlib.import_module(name)
            lines.append(f"ok   {name}")
        except Exception as e:
            bad += 1
            lines.append(f"FAIL {name}: {e}")
    try:
        app = QApplication.instance() or QApplication([])
        engine = Engine()
        win = MainWindow(engine)
        overlay = Overlay(engine)
        win.show()
        app.processEvents()
        win.grab()
        overlay.orb.grab()
        make_icon()
        lines.append("ok   user interface")
    except Exception as e:
        bad += 1
        lines.append(f"FAIL user interface: {e!r}")
    lines.append("SELFTEST " + ("FAILED" if bad else "PASSED"))
    try:
        with open(os.path.join(tempfile.gettempdir(), "fro_selftest.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except OSError:
        pass
    print("\n".join(lines))
    return 1 if bad else 0


def run(argv):
    if "--selftest" in argv:
        return selftest()
    background = "--background" in argv
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s: %(message)s")

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    lock = QLockFile(str(data_dir() / "fro.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        log.info("Fro is already running.")
        return 0

    icon = make_icon()
    app.setWindowIcon(icon)

    engine = Engine()
    window = MainWindow(engine)
    overlay = Overlay(engine)  # noqa: F841  (kept alive by the engine's signal connections)
    app.overlay = overlay

    def show_main():
        window.showNormal()
        window.raise_()
        window.activateWindow()

    window.on_close = window.hide
    window.on_settings_saved = lambda: (set_autostart(bool(settings.get("start_with_windows"))), register_hotkey())

    engine.main_requested.connect(show_main)
    engine.page_requested.connect(window.show_page)
    engine.quit_requested.connect(app.quit)
    engine.copy_requested.connect(lambda text: QGuiApplication.clipboard().setText(text))

    # system tray
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("Fro")
    menu = QMenu()
    act_open = QAction("Open Fro", menu)
    act_open.triggered.connect(show_main)
    act_listen = QAction("Talk to Fro", menu)
    act_listen.triggered.connect(engine.trigger)
    act_quit = QAction("Quit", menu)
    act_quit.triggered.connect(app.quit)
    for a in (act_open, act_listen):
        menu.addAction(a)
    menu.addSeparator()
    menu.addAction(act_quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: show_main() if reason in (
        QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)
    tray.show()
    engine.notify.connect(lambda title, text: tray.showMessage(title, text, QSystemTrayIcon.MessageIcon.Information, 8000))

    # global hotkey (works while Fro is hidden)
    state = {"hotkey": None}

    def register_hotkey():
        try:
            import keyboard

            if state["hotkey"]:
                keyboard.remove_hotkey(state["hotkey"])
            combo = settings.get("hotkey")
            state["hotkey"] = keyboard.add_hotkey(combo, engine.trigger)
        except Exception as e:  # Linux without root, bad combo, ...
            log.info("Global hotkey not active: %s", e)

    register_hotkey()
    engine.start()

    if not background or not settings.get("api_key"):
        QTimer.singleShot(200, show_main)
    if not settings.get("api_key") and not background:
        QTimer.singleShot(600, lambda: window.show_page("home"))

    code = app.exec()
    engine.stop()
    lock.unlock()
    return code
