# app.py — minimal main UI: 48x48 star icon with popup menus
import sys, os
from utils import base_path

from PySide6.QtCore import (
    Qt, QUrl, QTimer, QPropertyAnimation, QEasingCurve,
    QVariantAnimation, QThread, Signal,
)
from PySide6.QtGui import (
    QDesktopServices, QGuiApplication, QPainter, QColor,
    QPainterPath, QPixmap, QIcon,
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QDialog,
    QHBoxLayout, QCheckBox, QComboBox, QLineEdit, QMenu, QSystemTrayIcon,
)

from calendars.google_calendar import add_event_to_google, is_authenticated, _ensure_creds
import logic_from_notebook as logic

from validation import ValidationError, RateLimitExceededError, InputTooLongError

APP_NAME = "AI Scheduler"

# ── Shared stylesheets ──
BTN_SECONDARY = """
    QPushButton {
        background-color: #48484a; font-size: 13px; padding: 10px 20px;
        border-radius: 6px; color: #ffffff; border: none; min-width: 80px;
    }
    QPushButton:hover { background-color: #5a5a5c; }
"""
BTN_ACCENT = """
    QPushButton {
        background-color: #0a84ff; font-size: 13px; padding: 10px 20px;
        border-radius: 6px; color: #ffffff; border: none; min-width: 80px;
    }
    QPushButton:hover { background-color: #409cff; }
"""
MENU_STYLE = """
    QMenu {
        background-color: #2c2c2e; border: 1px solid #3a3a3c;
        border-radius: 8px; padding: 4px 0px;
    }
    QMenu::item { color: #ffffff; padding: 8px 24px; font-size: 13px; }
    QMenu::item:selected { background-color: #3a3a3c; }
    QMenu::separator { height: 1px; background-color: #3a3a3c; margin: 4px 8px; }
"""


# ── Icon helpers ──

def create_star_pixmap(size=32, star_color="#ffffff", bg_color=None):
    """Create a 4-pointed star pixmap (white star, transparent or solid corners)."""
    scale = 4
    actual_size = size * scale
    pixmap = QPixmap(actual_size, actual_size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setPen(Qt.NoPen)

    margin = 6 * scale
    painter.setBrush(QColor(star_color))
    painter.drawRect(margin, margin, actual_size - 2 * margin, actual_size - 2 * margin)

    corner_color = QColor(bg_color) if bg_color else QColor(0, 0, 0, 0)
    painter.setBrush(corner_color)
    r = (actual_size // 2) - margin
    painter.drawPie(margin - r, margin - r, r * 2, r * 2, 270 * 16, 90 * 16)
    painter.drawPie(actual_size - margin - r, margin - r, r * 2, r * 2, 180 * 16, 90 * 16)
    painter.drawPie(margin - r, actual_size - margin - r, r * 2, r * 2, 0, 90 * 16)
    painter.drawPie(actual_size - margin - r, actual_size - margin - r, r * 2, r * 2, 90 * 16, 90 * 16)

    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return pixmap


def create_star_icon(size=32, star_color="#ffffff", bg_color="#2c2c2e"):
    return QIcon(create_star_pixmap(size, star_color, bg_color))


# Checked in order; first file found in assets/ wins.
_ICON_CANDIDATES = ["icon.ico", "icon.png"]

def load_app_icon() -> QIcon:
    """Return a custom icon from assets/ if present, else the drawn star."""
    assets_dir = os.path.join(base_path(), "assets")
    for name in _ICON_CANDIDATES:
        path = os.path.join(assets_dir, name)
        if os.path.exists(path):
            return QIcon(path)
    return create_star_icon(32, "#ffffff", "#2c2c2e")


# ── Background worker ──

class AIWorkerThread(QThread):
    """Runs build_event_dict_from_prompt off the main thread to keep the UI responsive."""
    result_ready   = Signal(object, object)  # (ev_dict, warnings_list)
    error_occurred = Signal(str, str)        # (exc_class_name, user_message)

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt = prompt

    def run(self):
        try:
            ev, warnings = logic.build_event_dict_from_prompt(self.prompt)
            self.result_ready.emit(ev, warnings)
        except RateLimitExceededError as e:
            self.error_occurred.emit("RateLimitExceededError", e.user_message)
        except InputTooLongError as e:
            self.error_occurred.emit("InputTooLongError", e.user_message)
        except ValidationError as e:
            self.error_occurred.emit("ValidationError", e.user_message)
        except Exception as e:
            self.error_occurred.emit("Exception", str(e))


# ── Dialogs ──

class StyledDialog(QDialog):
    """Base class for all app dialogs — dark theme, frameless, draggable."""
    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._drag_pos = None

        self.setStyleSheet("""
            QLabel { color: #ffffff; font-size: 13px; padding: 2px 0px; }
            QCheckBox { color: #ffffff; font-size: 13px; padding: 4px 0px; spacing: 8px; }
            QCheckBox::indicator {
                width: 18px; height: 18px; border-radius: 4px;
                border: 1px solid #3a3a3c; background-color: #2c2c2e;
            }
            QCheckBox::indicator:checked { background-color: #636366; border: 1px solid #636366; }
            QComboBox {
                background-color: #2c2c2e; color: #ffffff; border: 1px solid #3a3a3c;
                border-radius: 6px; padding: 8px 12px; font-size: 13px; min-height: 20px;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox QAbstractItemView {
                background-color: #2c2c2e; color: #ffffff;
                selection-background-color: #3a3a3c; padding: 4px;
            }
            QLineEdit {
                background-color: #2c2c2e; color: #ffffff; border: 1px solid #3a3a3c;
                border-radius: 6px; padding: 8px 12px; font-size: 13px; min-height: 20px;
            }
            QLineEdit:focus { border: 1px solid #636366; }
            QPushButton {
                font-size: 13px; padding: 10px 16px; border-radius: 6px;
                background-color: #2c2c2e; color: #ffffff; border: none; min-height: 18px;
            }
            QPushButton:hover { background-color: #3a3a3c; }
            QPushButton:pressed { background-color: #1c1c1e; }
        """)

    def _add_title(self, layout, text, font_size=16):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: {font_size}px; font-weight: bold; color: #ffffff;")
        layout.addWidget(lbl)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 16, 16)
        painter.fillPath(path, QColor("#1c1c1e"))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


class SettingsDialog(StyledDialog):
    """Calendar provider, preferences, and Google auth."""
    def __init__(self, parent=None):
        super().__init__(parent, "Settings")
        self.setFixedSize(340, 350)

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        self._add_title(v, "Settings", 18)
        v.addSpacing(8)

        v.addWidget(QLabel("Calendar provider"))
        self.provider = QComboBox()
        self.provider.addItem("Google (active)")
        self.provider.addItem("Microsoft (coming)")
        self.provider.addItem("Apple / ICS (coming)")
        v.addWidget(self.provider)
        v.addSpacing(8)

        self.chk_preview = QCheckBox("Show event preview after creation")
        self.chk_preview.setChecked(True)
        v.addWidget(self.chk_preview)

        self.chk_always_on_top = QCheckBox("Always on top")
        self.chk_always_on_top.setChecked(False)
        v.addWidget(self.chk_always_on_top)

        v.addSpacing(8)
        self.auth_btn = QPushButton()
        self._update_auth_button()
        v.addWidget(self.auth_btn)
        v.addStretch()

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet(BTN_SECONDARY)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(ok_btn)
        v.addLayout(btn_row)

    def _update_auth_button(self):
        try:
            self.auth_btn.clicked.disconnect()
        except RuntimeError:
            pass
        if is_authenticated():
            self.auth_btn.setText("Sign out")
            self.auth_btn.clicked.connect(self.sign_out_google)
        else:
            self.auth_btn.setText("Sign in to Google")
            self.auth_btn.clicked.connect(self.sign_in_google)

    def sign_in_google(self):
        try:
            _ensure_creds()
            StyledMessageBox.information(self, "Signed In", "Google account connected successfully.")
            self._update_auth_button()
        except Exception as e:
            StyledMessageBox.critical(self, "Sign In Failed", str(e))

    def sign_out_google(self):
        token_path = os.path.join(base_path(), "token.json")
        if os.path.exists(token_path):
            os.remove(token_path)
            StyledMessageBox.information(self, "Signed Out", "Google account disconnected.")
            self._update_auth_button()
        else:
            StyledMessageBox.information(self, "Not Signed In", "No Google account currently connected.")

    def get_values(self):
        return {
            "provider": self.provider.currentIndex(),
            "preview": self.chk_preview.isChecked(),
            "always_on_top": self.chk_always_on_top.isChecked(),
        }


class InputDialog(StyledDialog):
    """Event input dialog with non-blocking loading state for the AI call."""
    schedule_requested = Signal(str)  # emitted when Schedule is clicked with non-empty text

    def __init__(self, parent=None, title="", label="", default_text=""):
        super().__init__(parent, title)
        self.setFixedSize(400, 180)

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        self._add_title(v, title)

        self.input = QLineEdit()
        self.input.setPlaceholderText(label)
        if default_text:
            self.input.setText(default_text)
            self.input.selectAll()
        v.addWidget(self.input)
        v.addStretch()

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        self._ok_btn = QPushButton("Schedule")
        self._ok_btn.clicked.connect(self._on_schedule_clicked)
        self._ok_btn.setStyleSheet(BTN_SECONDARY)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self._ok_btn)
        v.addLayout(btn_row)

        self.input.returnPressed.connect(self._on_schedule_clicked)

        self._dot_timer = QTimer(self)
        self._dot_timer.setInterval(450)
        self._dot_timer.timeout.connect(self._tick_dots)
        self._dot_count = 0

    def _on_schedule_clicked(self):
        text = self.input.text().strip()
        if text:
            self.schedule_requested.emit(text)

    def set_loading(self, loading: bool):
        """Toggle loading state: disables input and animates the button text."""
        self.input.setEnabled(not loading)
        self._ok_btn.setEnabled(not loading)
        if loading:
            self._dot_count = 0
            self._ok_btn.setText("Thinking")
            self._dot_timer.start()
        else:
            self._dot_timer.stop()
            self._ok_btn.setText("Schedule")

    def _tick_dots(self):
        self._dot_count = (self._dot_count + 1) % 4
        self._ok_btn.setText("Thinking" + "." * self._dot_count)


class StyledMessageBox(StyledDialog):
    """Info/error/question dialogs matching the app design."""
    def __init__(self, parent=None, title="", message=""):
        super().__init__(parent, title)
        self.setFixedSize(360, 180)

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        self._add_title(v, title)

        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        v.addWidget(msg_label)
        v.addStretch()

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setStyleSheet(BTN_SECONDARY)
        v.addWidget(ok_btn, alignment=Qt.AlignRight)

    @staticmethod
    def information(parent, title, message):
        StyledMessageBox(parent, title, message).exec()

    @staticmethod
    def critical(parent, title, message):
        StyledMessageBox(parent, title, message).exec()

    @staticmethod
    def question(parent, title, message) -> bool:
        dlg = StyledDialog(parent, title)
        dlg.setFixedSize(400, 200)

        v = QVBoxLayout(dlg)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        dlg._add_title(v, title)

        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet("color: #ffffff;")
        v.addWidget(msg_label)
        v.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        no_btn = QPushButton("No")
        no_btn.clicked.connect(dlg.reject)
        no_btn.setStyleSheet(BTN_SECONDARY)
        yes_btn = QPushButton("Yes")
        yes_btn.clicked.connect(dlg.accept)
        yes_btn.setStyleSheet(BTN_ACCENT)
        btn_row.addWidget(no_btn)
        btn_row.addWidget(yes_btn)

        v.addLayout(btn_row)
        return dlg.exec() == QDialog.Accepted


# ── Main window ──

class MainWindow(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)

        # Qt.Tool keeps the floating widget off the Windows taskbar
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(48, 48)

        screen = QGuiApplication.primaryScreen().geometry()
        self.move(screen.width() - 48 - 20, screen.height() // 2 - 24)

        self._drag_pos = None
        self._press_pos = None
        self._press_button = None
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

        self.settings_values = {"provider": 0, "preview": True, "always_on_top": True}
        self._current_worker: AIWorkerThread | None = None

        self._star_pixmap = create_star_pixmap(48, "#ffffff", "#2c2c2e")
        self._star_scale = 0.75

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(150)
        self._hover_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_scale_changed)

        self._setup_tray()

    # ── System tray ──

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(load_app_icon(), self)
        self._tray.setToolTip(APP_NAME)

        menu = QMenu()
        menu.setStyleSheet(MENU_STYLE)
        menu.addAction("Settings").triggered.connect(self.open_settings)
        menu.addSeparator()
        menu.addAction("Quit").triggered.connect(QApplication.instance().quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.raise_()
            self.activateWindow()

    # ── Paint ──

    def _on_scale_changed(self, value):
        self._star_scale = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 12, 12)
        painter.fillPath(path, QColor("#2c2c2e"))

        pm = self._star_pixmap
        dpr = pm.devicePixelRatio()
        cx, cy = self.width() / 2.0, self.height() / 2.0

        painter.save()
        painter.translate(cx, cy)
        painter.scale(self._star_scale, self._star_scale)
        painter.drawPixmap(int(-pm.width() / dpr / 2), int(-pm.height() / dpr / 2), pm)
        painter.restore()

    # ── Hover ──

    def enterEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._star_scale)
        self._hover_anim.setEndValue(0.95)
        self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._star_scale)
        self._hover_anim.setEndValue(0.65)
        self._hover_anim.start()
        super().leaveEvent(event)

    # ── Mouse: drag + click ──

    def mousePressEvent(self, event):
        self._press_pos = event.globalPosition().toPoint()
        self._press_button = event.button()
        self._drag_pos = self._press_pos - self.frameGeometry().topLeft()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and self._press_button == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        event.accept()

    def mouseReleaseEvent(self, event):
        if self._press_pos is not None:
            delta = (event.globalPosition().toPoint() - self._press_pos).manhattanLength()
            if delta < 4:
                if event.button() == Qt.LeftButton:
                    self.on_ai_assistant()
                elif event.button() == Qt.RightButton:
                    self._show_context_menu(event.globalPosition().toPoint())
        self._drag_pos = None
        self._press_pos = None
        self._press_button = None

    # ── Context menu ──

    def _show_context_menu(self, global_pos):
        menu = QMenu(self)
        menu.setStyleSheet(MENU_STYLE)
        menu.addAction("Settings").triggered.connect(self.open_settings)
        menu.addSeparator()
        menu.addAction("Quit").triggered.connect(QApplication.instance().quit)
        menu.exec(global_pos)

    # ── Settings ──

    def open_settings(self):
        # parent=None gives SettingsDialog its own Windows taskbar entry
        dlg = SettingsDialog(None)
        dlg.provider.setCurrentIndex(self.settings_values.get("provider", 0))
        dlg.chk_preview.setChecked(self.settings_values.get("preview", True))
        dlg.chk_always_on_top.setChecked(self.settings_values.get("always_on_top", True))
        if dlg.exec() == QDialog.Accepted:
            self.settings_values = dlg.get_values()
            self._apply_always_on_top()
            self.toast("Settings saved")

    def _apply_always_on_top(self):
        base = Qt.FramelessWindowHint | Qt.Tool
        flags = base | Qt.WindowStaysOnTopHint if self.settings_values.get("always_on_top", True) else base
        self.setWindowFlags(flags)
        self.show()

    # ── AI flow (event-driven, non-blocking) ──

    def on_ai_assistant(self):
        if not is_authenticated():
            if StyledMessageBox.question(
                self, "Sign In Required",
                "Please sign in to Google Calendar to schedule events.\n\nSign in now?"
            ):
                try:
                    _ensure_creds()
                except Exception as e:
                    StyledMessageBox.critical(self, "Sign In Failed", str(e))
                    return
            else:
                return
        self._open_input_dialog()

    def _open_input_dialog(self, default_text=""):
        dlg = InputDialog(
            self, "What should I schedule?",
            "e.g. 'Lunch with Alice tomorrow 1-2pm at campus'",
            default_text=default_text,
        )
        dlg.schedule_requested.connect(lambda text: self._run_ai(dlg, text))
        dlg.open()  # non-blocking; flow continues via signals

    def _run_ai(self, dlg: InputDialog, prompt: str):
        dlg.set_loading(True)
        worker = AIWorkerThread(prompt)
        worker.result_ready.connect(lambda ev, w: self._on_ai_result(dlg, ev, w))
        worker.error_occurred.connect(lambda t, m: self._on_ai_error(dlg, t, m))
        worker.finished.connect(worker.deleteLater)
        worker.start()
        self._current_worker = worker

    def _on_ai_result(self, dlg: InputDialog, ev: dict, warnings: list):
        dlg.set_loading(False)
        if warnings:
            warning_text = "\n".join(f"\u2022 {w.message}" for w in warnings)
            if not StyledMessageBox.question(
                self, "Are you sure?", f"{warning_text}\n\nAdd this event anyway?"
            ):
                return  # stay in InputDialog so user can re-edit

        if not self.show_event_confirmation(ev):
            return  # user hit Edit; stay in InputDialog

        dlg.accept()  # close dialog only after full confirmation
        self._add_to_calendar(ev)

    def _on_ai_error(self, dlg: InputDialog, exc_type: str, message: str):
        dlg.set_loading(False)
        titles = {
            "RateLimitExceededError": "Please Wait",
            "InputTooLongError":      "Input Too Long",
            "ValidationError":        "Couldn't Parse Event",
            "Exception":              "AI Error",
        }
        StyledMessageBox.critical(self, titles.get(exc_type, "Error"), message)
        if exc_type == "RateLimitExceededError":
            dlg.reject()  # no point retrying immediately

    def _add_to_calendar(self, ev: dict):
        provider = self.settings_values.get("provider", 0)
        try:
            if provider == 0:
                created = add_event_to_google(ev)
            elif provider == 1:
                raise NotImplementedError("Microsoft integration not enabled yet.")
            else:
                raise NotImplementedError("ICS flow is paused in this build.")
            if self.settings_values.get("preview", True):
                self.show_event_preview(created)
            self.toast("Event added to calendar")
        except Exception as e:
            StyledMessageBox.critical(self, "Calendar Error", str(e))

    # ── Event confirmation + preview ──

    def show_event_confirmation(self, ev: dict) -> bool:
        dlg = StyledDialog(self, "Confirm Event")
        dlg.setFixedSize(380, 270)

        v = QVBoxLayout(dlg)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        dlg._add_title(v, "Add this event?")

        event_title = QLabel(ev.get("summary", "(no title)"))
        event_title.setStyleSheet("font-size: 14px; color: #ffffff;")
        event_title.setWordWrap(True)
        v.addWidget(event_title)

        start, end = ev.get("start"), ev.get("end")
        if hasattr(start, "strftime"):
            date_str = start.strftime("%A, %B %d, %Y")
            time_str = f"{start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}"
        else:
            date_str, time_str = str(start), f"{start} - {end}"

        for text, style in [(date_str, "color:#8e8e93;"), (time_str, "color:#8e8e93;")]:
            lbl = QLabel(text)
            lbl.setStyleSheet(f"font-size: 13px; {style}")
            v.addWidget(lbl)

        recurrence = ev.get("recurrence")
        if recurrence:
            recur_lbl = QLabel(f"Repeats: {self._format_recurrence(recurrence)}")
            recur_lbl.setStyleSheet("font-size: 13px; color: #0a84ff;")
            v.addWidget(recur_lbl)

        v.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(dlg.reject)
        edit_btn.setStyleSheet(BTN_SECONDARY)
        confirm_btn = QPushButton("Add Event")
        confirm_btn.clicked.connect(dlg.accept)
        confirm_btn.setStyleSheet(BTN_ACCENT)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(confirm_btn)
        v.addLayout(btn_row)

        return dlg.exec() == QDialog.Accepted

    def _format_recurrence(self, recurrence) -> str:
        rrule = recurrence[0] if isinstance(recurrence, list) else recurrence
        rrule = rrule.upper().replace("RRULE:", "")
        parts = dict(p.split("=") for p in rrule.split(";") if "=" in p)

        freq     = parts.get("FREQ", "")
        count    = parts.get("COUNT", "")
        byday    = parts.get("BYDAY", "")
        interval = parts.get("INTERVAL", "1")

        freq_map = {"DAILY": "Daily", "WEEKLY": "Weekly", "MONTHLY": "Monthly", "YEARLY": "Yearly"}
        day_map  = {"MO": "Mon", "TU": "Tue", "WE": "Wed", "TH": "Thu",
                    "FR": "Fri", "SA": "Sat", "SU": "Sun"}

        result = freq_map.get(freq, freq.capitalize())
        if interval != "1":
            unit = {"DAILY": "days", "WEEKLY": "weeks", "MONTHLY": "months"}.get(freq, "years")
            result = f"Every {interval} {unit}"
        if byday:
            days = [day_map.get(d.strip("0123456789-"), d) for d in byday.split(",")]
            result += f" on {', '.join(days)}"
        if count:
            result += f" ({count} times)"
        return result

    def show_event_preview(self, created: dict):
        dlg = StyledDialog(self, "Event Created")
        dlg.setFixedSize(360, 220)

        v = QVBoxLayout(dlg)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        dlg._add_title(v, "Event Created")

        event_title = QLabel(created.get("summary", "(no title)"))
        event_title.setStyleSheet("font-size: 14px; color: #ffffff;")
        v.addWidget(event_title)

        start, end = created.get("start", "?"), created.get("end", "?")
        time_lbl = QLabel(f"{start} → {end}")
        time_lbl.setStyleSheet("font-size: 12px; color: #8e8e93;")
        v.addWidget(time_lbl)

        v.addStretch()

        link = created.get("htmlLink")
        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(link)) if link else None)
        open_btn.setStyleSheet(BTN_SECONDARY)
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(
            lambda: (QGuiApplication.clipboard().setText(link), self.toast("Link copied")) if link else None
        )
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(close_btn)
        v.addLayout(btn_row)

        dlg.exec()

    # ── Toast notification ──

    def toast(self, text: str, ms: int = 2200):
        note = QLabel(text)
        note.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        note.setAttribute(Qt.WA_TransparentForMouseEvents)
        note.setAttribute(Qt.WA_ShowWithoutActivating)
        note.setStyleSheet(
            "QLabel{background:rgba(30,30,30,0.95); color:white; padding:10px 16px;"
            "border-radius:10px; font-size:12pt;}"
        )
        note.adjustSize()

        m = 12
        geo = self.geometry()
        toast_x = geo.x() - note.width() - m
        if toast_x < 0:
            toast_x = geo.right() + m
        note.move(toast_x, geo.y())
        note.show()

        anim_in = QPropertyAnimation(note, b"windowOpacity", note)
        anim_in.setDuration(220)
        anim_in.setStartValue(0.0)
        anim_in.setEndValue(1.0)
        anim_in.setEasingCurve(QEasingCurve.OutCubic)

        def fade_out():
            anim_out = QPropertyAnimation(note, b"windowOpacity", note)
            anim_out.setDuration(280)
            anim_out.setStartValue(1.0)
            anim_out.setEndValue(0.0)
            anim_out.finished.connect(note.deleteLater)
            anim_out.start()

        anim_in.finished.connect(lambda: QTimer.singleShot(ms, fade_out))
        anim_in.start()


def main():
    app = QApplication(sys.argv)
    app.setWindowIcon(load_app_icon())
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
