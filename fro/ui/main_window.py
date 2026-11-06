"""The main Fro window (2D dark teal design with sidebar, orb, greeting and chat box)."""
import datetime as dt

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QScrollArea,
    QStackedWidget, QVBoxLayout, QWidget,
)

from ..settings import settings
from .pages import NotesPage, SettingsPage, SkillsPage, TasksPage
from .sphere_orb import SphereOrb
from .theme import ACCENT_HEX, CSS_FAMILY, SCROLLBAR_QSS
from .widgets import Bubble, IconButton, PillButton, SuggestionCard

RADIUS = 30


class Sidebar(QWidget):
    def __init__(self, on_page):
        super().__init__()
        self.setFixedWidth(78)
        self.on_page = on_page
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 26, 0, 22)
        lay.setSpacing(14)
        logo = QLabel("FRO")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(f"color: white; font: 800 16px {CSS_FAMILY}; letter-spacing: 1px; background: transparent;")
        lay.addWidget(logo)
        lay.addSpacing(10)
        self.buttons = {}
        for name, icon, tip in (("home", "home", "Home"), ("tasks", "clock", "Timers & reminders"),
                                ("notes", "note", "Notes & lists"), ("skills", "grid", "What Fro can do")):
            b = IconButton(icon, 44, tip=tip)
            b.clicked.connect(lambda _=False, n=name: on_page(n))
            lay.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
            self.buttons[name] = b
        lay.addStretch(1)
        g = IconButton("gear", 44, tip="Settings")
        g.clicked.connect(lambda: on_page("settings"))
        self.buttons["settings"] = g
        lay.addWidget(g, 0, Qt.AlignmentFlag.AlignHCenter)
        self.avatar = QLabel()
        self.avatar.setFixedSize(40, 40)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignHCenter)
        self.refresh_avatar()
        self.select("home")

    def refresh_avatar(self):
        letter = (settings.get("user_name") or "F")[:1].upper()
        self.avatar.setText(letter)
        self.avatar.setStyleSheet(
            f"color: white; font: 700 16px {CSS_FAMILY}; border-radius: 20px;"
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #5a6cff, stop:1 #12b5d6);"
        )

    def select(self, name):
        for key, b in self.buttons.items():
            b.set_active(key == name)


class MainWindow(QWidget):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setWindowTitle("Fro")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.resize(1040, 700)
        self.setMinimumSize(820, 600)
        self._drag = None
        self._has_chat = False
        self.on_close = None  # set by the app (hide to tray)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.sidebar = Sidebar(self.show_page)
        root.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        root.addWidget(self.stack, 1)
        self.pages = {
            "home": self._build_home(),
            "tasks": TasksPage(engine),
            "notes": NotesPage(engine),
            "skills": SkillsPage(),
            "settings": SettingsPage(),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        self.pages["settings"].saved.connect(self._settings_saved)

        # window buttons (top-right)
        self.btn_min = IconButton("minimize", 30, ring=False, parent=self)
        self.btn_close = IconButton("close", 30, ring=False, parent=self)
        self.btn_min.clicked.connect(self.showMinimized)
        self.btn_close.clicked.connect(self._close_clicked)

        engine.state_changed.connect(self._on_state)
        engine.heard.connect(lambda t: self.add_message(t, True))
        engine.replied.connect(lambda t: self.add_message(t, False))
        engine.mic_status.connect(self._on_mic)
        self._on_state("idle")

    # ------------------------------------------------------------------ home page
    def _build_home(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(40, 26, 40, 28)
        v.setSpacing(0)

        self.orb = SphereOrb(150)
        v.addWidget(self.orb, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(10)

        self.hello = QLabel()
        self.hello.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hello.setStyleSheet(f"color: rgba(255,255,255,105); font: 700 30px {CSS_FAMILY}; background: transparent;")
        self.question = QLabel("How can I help today?")
        self.question.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.question.setStyleSheet(f"color: white; font: 700 30px {CSS_FAMILY}; background: transparent;")
        self.tagline = QLabel()
        self.tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tagline.setStyleSheet(f"color: rgba(255,255,255,95); font: 400 13px {CSS_FAMILY}; background: transparent;")
        for w in (self.hello, self.question, self.tagline):
            v.addWidget(w)

        # conversation (replaces the greeting after the first message)
        self.chat_area = QScrollArea()
        self.chat_area.setWidgetResizable(True)
        self.chat_area.setFrameShape(QFrame.Shape.NoFrame)
        self.chat_area.setStyleSheet("QScrollArea { background: transparent; } QWidget#chat { background: transparent; }" + SCROLLBAR_QSS)
        chat = QWidget()
        chat.setObjectName("chat")
        self.chat_lay = QVBoxLayout(chat)
        self.chat_lay.setContentsMargins(60, 0, 60, 0)
        self.chat_lay.setSpacing(10)
        self.chat_lay.addStretch(1)
        self.chat_area.setWidget(chat)
        self.chat_area.hide()
        v.addWidget(self.chat_area, 1)

        self.spacer_top = v.addStretch(1)
        v.addSpacing(16)

        # input card
        card = QFrame()
        card.setObjectName("card")
        card.setMaximumWidth(680)
        card.setStyleSheet(
            "QFrame#card { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(60,110,130,120), stop:1 rgba(30,90,115,120));"
            "border: 1px solid rgba(255,255,255,26); border-radius: 26px; }"
        )
        cv = QVBoxLayout(card)
        cv.setContentsMargins(8, 8, 8, 8)
        cv.setSpacing(6)
        self.hint = QLabel()
        self.hint.setStyleSheet(f"color: rgba(255,255,255,200); font: 500 12px {CSS_FAMILY}; padding: 2px 10px; background: transparent;")
        cv.addWidget(self.hint)
        box = QFrame()
        box.setObjectName("box")
        box.setStyleSheet("QFrame#box { background: rgba(8,9,12,235); border-radius: 20px; }")
        bv = QVBoxLayout(box)
        bv.setContentsMargins(16, 12, 12, 12)
        bv.setSpacing(10)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Ask me anything ...")
        self.input.setStyleSheet(
            f"QLineEdit {{ color: white; font: 400 14px {CSS_FAMILY}; background: transparent; border: none; padding: 6px 0; }}"
        )
        self.input.returnPressed.connect(self._send)
        bv.addWidget(self.input)
        row = QHBoxLayout()
        row.setSpacing(8)
        file_btn = PillButton("◌  Import file")
        file_btn.clicked.connect(self._pick_file)
        tools_btn = PillButton("⚙  Tools")
        tools_btn.clicked.connect(lambda: self._tools_menu(tools_btn))
        row.addWidget(file_btn)
        row.addWidget(tools_btn)
        row.addStretch(1)
        self.mic = IconButton("mic", 38, tip="Talk to Fro")
        self.mic.clicked.connect(self.engine.trigger)
        send = IconButton("up", 38, filled=True, tip="Send")
        send.clicked.connect(self._send)
        row.addWidget(self.mic)
        row.addWidget(send)
        bv.addLayout(row)
        cv.addWidget(box)
        v.addWidget(card, 0, Qt.AlignmentFlag.AlignHCenter)
        v.addSpacing(14)

        self.cards = QWidget()
        self.cards.setMaximumWidth(680)
        grid = QGridLayout(self.cards)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(14)
        defs = [
            ("Surprise me!", "Ask for a fun fact, a joke or an idea.", lambda: self.engine.submit("tell me a fun fact")),
            ("Read my screen", "Describe what is on my screen right now.", lambda: self.engine.submit("what's on my screen")),
            ("Summarise", "Summarise a document, PDF or image.", self._pick_file),
        ]
        for i, (a, b, fn) in enumerate(defs):
            c = SuggestionCard(a, b)
            c.clicked.connect(fn)
            grid.addWidget(c, 0, i)
        v.addWidget(self.cards, 0, Qt.AlignmentFlag.AlignHCenter)
        self._refresh_texts()
        return page

    def _refresh_texts(self):
        name = settings.get("user_name")
        self.hello.setText(f"Hi, {name}")
        word = settings.get("wake_word")
        key = settings.get("hotkey").replace("+", " + ").title()
        self.tagline.setText(f'Say “{word.title()}” or press {key}. I can open apps, set timers, answer questions and more.')
        self.hint.setText(f'⚡  Say “{word.title()}” or just type below')
        self.sidebar.refresh_avatar()

    def _settings_saved(self):
        self._refresh_texts()
        self.engine.reload_settings()
        if self.on_settings_saved:
            self.on_settings_saved()

    on_settings_saved = None

    # ------------------------------------------------------------------ actions
    def show_page(self, name):
        if name == "refresh":
            self.pages["settings"].load()
            return
        if name in self.pages:
            self.stack.setCurrentWidget(self.pages[name])
            self.sidebar.select(name)

    def _send(self):
        text = self.input.text().strip()
        if text:
            self.input.clear()
            self.engine.submit(text)

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a file for Fro", "", "Documents and images (*.pdf *.txt *.md *.csv *.json *.py *.log *.png *.jpg *.jpeg *.webp);;All files (*)")
        if path:
            self.show_page("home")
            self.engine.submit_file(path, self.input.text().strip())
            self.input.clear()

    def _tools_menu(self, anchor):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu {{ background: #10151d; color: white; border: 1px solid rgba(255,255,255,30); border-radius: 12px; padding: 6px; font: 500 13px {CSS_FAMILY}; }}"
            "QMenu::item { padding: 8px 18px; border-radius: 8px; } QMenu::item:selected { background: rgba(18,150,214,160); }"
        )
        for label, cmd in (("Read my screen", "what's on my screen"), ("Take a screenshot", "take a screenshot"),
                           ("Summarise clipboard", "summarize my clipboard"), ("Today's news", "give me the news"),
                           ("Weather", "what's the weather"), ("System status", "how is my pc")):
            menu.addAction(label, lambda c=cmd: self.engine.submit(c))
        menu.addSeparator()
        menu.addAction("Clear conversation", self.clear_chat)
        menu.exec(anchor.mapToGlobal(anchor.rect().topLeft() - anchor.rect().bottomLeft() * 5))

    def add_message(self, text, mine):
        if not text.strip():
            return
        if not self._has_chat:
            self._has_chat = True
            for w in (self.hello, self.question, self.tagline, self.cards):
                w.hide()
            self.chat_area.show()
        self.chat_lay.insertWidget(self.chat_lay.count() - 1, Bubble(text, mine))
        QTimer.singleShot(30, lambda: self.chat_area.verticalScrollBar().setValue(self.chat_area.verticalScrollBar().maximum()))

    def clear_chat(self):
        while self.chat_lay.count() > 1:
            item = self.chat_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.engine.brain.history = []
        self._has_chat = False
        self.chat_area.hide()
        for w in (self.hello, self.question, self.tagline, self.cards):
            w.show()

    def _on_state(self, state):
        self.orb.set_state(state)
        self.mic.set_active(state == "listening")
        self.input.setPlaceholderText({
            "listening": "Listening ...", "thinking": "Thinking ...", "speaking": "Speaking ...",
        }.get(state, "Ask me anything ..."))

    def _on_mic(self, ok):
        if not ok:
            self.hint.setText("⚠  No microphone found. You can still type below.")

    # ------------------------------------------------------------------ window behaviour
    def _close_clicked(self):
        if self.on_close:
            self.on_close()
        else:
            self.close()

    def resizeEvent(self, e):
        self.btn_close.move(self.width() - 46, 14)
        self.btn_min.move(self.width() - 80, 14)
        super().resizeEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 70:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._drag = None
        super().mouseReleaseEvent(e)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            if url.isLocalFile():
                self.show_page("home")
                self.engine.submit_file(url.toLocalFile(), self.input.text().strip())
                self.input.clear()
                break

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), RADIUS, RADIUS)
        p.setClipPath(path)
        base = QLinearGradient(0, 0, 0, h)
        base.setColorAt(0.0, QColor(8, 9, 12))
        base.setColorAt(0.55, QColor(8, 14, 20))
        base.setColorAt(1.0, QColor(10, 40, 52))
        p.fillPath(path, base)
        glow = QRadialGradient(QPointF(w * 0.55, h * 1.12), w * 0.72)
        glow.setColorAt(0.0, QColor(24, 150, 170, 170))
        glow.setColorAt(0.5, QColor(16, 90, 120, 70))
        glow.setColorAt(1.0, QColor(16, 90, 120, 0))
        p.fillPath(path, glow)
        side = QLinearGradient(0, 0, 90, 0)
        side.setColorAt(0.0, QColor(255, 255, 255, 8))
        side.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, side)
        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.end()
