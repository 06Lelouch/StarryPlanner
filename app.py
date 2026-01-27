# app.py — minimal main UI: one AI button + Settings menu
from pathlib import Path
from datetime import datetime
import sys, json

from PySide6.QtCore import Qt, QUrl, QTimer, QPropertyAnimation, QEasingCurve, QRect, QSize
from PySide6.QtGui import QAction, QDesktopServices, QGuiApplication, QPainter, QColor, QPainterPath, QPixmap, QIcon, QPen
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QDialog,
    QHBoxLayout, QCheckBox, QComboBox, QLineEdit
)

# === your existing modules ===
from calendars.google_calendar import add_event_to_google, is_authenticated, _ensure_creds
# from calendars.ms_calendar import add_event_to_ms        # (placeholder)
# from calendars.ics_utils import save_event_to_ics         # (placeholder)
import logic_from_notebook as logic  # build_event_dict_from_prompt(prompt)

# === validation ===
from validation import (
    ValidationError,
    RateLimitExceededError,
    InputTooLongError,
)

APP_NAME = "AI Scheduler"

#todo: replace with image file?
def create_star_icon(size=32, star_color="#ffffff", bg_color="#2c2c2e"):
    """Create a 4-pointed star icon (white star, dark circles in corners)."""
    # Use high DPI for crisp rendering
    scale = 4  # Higher scale for 4K
    actual_size = size * scale
    pixmap = QPixmap(actual_size, actual_size)
    pixmap.fill(QColor(0, 0, 0, 0))  # Transparent background

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.setPen(Qt.NoPen)

    # First fill with star color (white)
    margin = 6 * scale
    painter.setBrush(QColor(star_color))
    painter.drawRect(margin, margin, actual_size - 2 * margin, actual_size - 2 * margin)

    # Then draw dark quarter circles in corners to carve out the star
    painter.setBrush(QColor(bg_color))
    circle_radius = (actual_size // 2) - margin

    # Top-left quarter circle
    painter.drawPie(margin - circle_radius, margin - circle_radius,
                    circle_radius * 2, circle_radius * 2, 270 * 16, 90 * 16)
    # Top-right quarter circle
    painter.drawPie(actual_size - margin - circle_radius, margin - circle_radius,
                    circle_radius * 2, circle_radius * 2, 180 * 16, 90 * 16)
    # Bottom-left quarter circle
    painter.drawPie(margin - circle_radius, actual_size - margin - circle_radius,
                    circle_radius * 2, circle_radius * 2, 0 * 16, 90 * 16)
    # Bottom-right quarter circle
    painter.drawPie(actual_size - margin - circle_radius, actual_size - margin - circle_radius,
                    circle_radius * 2, circle_radius * 2, 90 * 16, 90 * 16)

    painter.end()

    pixmap.setDevicePixelRatio(scale)
    return QIcon(pixmap)


class StyledDialog(QDialog):
    """Base class for styled dialogs matching the main window design."""
    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._drag_pos = None

        # Dark theme styling
        self.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 13px;
                padding: 2px 0px;
            }
            QCheckBox {
                color: #ffffff;
                font-size: 13px;
                padding: 4px 0px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #3a3a3c;
                background-color: #2c2c2e;
            }
            QCheckBox::indicator:checked {
                background-color: #636366;
                border: 1px solid #636366;
            }
            QComboBox {
                background-color: #2c2c2e;
                color: #ffffff;
                border: 1px solid #3a3a3c;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                min-height: 20px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                background-color: #2c2c2e;
                color: #ffffff;
                selection-background-color: #3a3a3c;
                padding: 4px;
            }
            QLineEdit {
                background-color: #2c2c2e;
                color: #ffffff;
                border: 1px solid #3a3a3c;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 1px solid #636366;
            }
            QPushButton {
                font-size: 13px;
                padding: 10px 16px;
                border-radius: 6px;
                background-color: #2c2c2e;
                color: #ffffff;
                border: none;
                min-height: 18px;
            }
            QPushButton:hover {
                background-color: #3a3a3c;
            }
            QPushButton:pressed {
                background-color: #1c1c1e;
            }
        """)

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
    """
    Simple non-blocking settings:
      - Calendar provider (Google is active, others disabled)
      - Optional toggles (placeholders for future)
    """
    def __init__(self, parent=None):
        super().__init__(parent, "Settings")
        self.setFixedSize(340, 430)

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        # Title
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        v.addWidget(title)
        v.addSpacing(8)

        # Calendar provider
        v.addWidget(QLabel("Calendar provider"))
        self.provider = QComboBox()
        self.provider.addItem("Google (active)")
        self.provider.addItem("Microsoft (coming)")
        self.provider.addItem("Apple / ICS (coming)")
        self.provider.setCurrentIndex(0)
        v.addWidget(self.provider)

        v.addSpacing(8)

        # Toggles
        self.chk_preview = QCheckBox("Show event preview after creation")
        self.chk_preview.setChecked(True)
        v.addWidget(self.chk_preview)

        self.chk_always_on_top = QCheckBox("Always on top")
        self.chk_always_on_top.setChecked(False)
        v.addWidget(self.chk_always_on_top)

        self.chk_auto_hide = QCheckBox("Auto-hide to icon")
        self.chk_auto_hide.setChecked(True)
        v.addWidget(self.chk_auto_hide)

        v.addSpacing(8)

        self.auth_btn = QPushButton()
        self._update_auth_button()
        v.addWidget(self.auth_btn)

        v.addStretch()

        # Bottom buttons
        btn_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #48484a;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #5a5a5c;
            }
        """)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.ok_btn)
        v.addLayout(btn_row)

        v.addSpacing(12)
        self.quit_btn = QPushButton("Quit App")
        self.quit_btn.setStyleSheet("""
            QPushButton {
                background-color: #3a3a3c;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                color: #98989d;
                border: none;
            }
            QPushButton:hover {
                background-color: #48484a;
                color: #ffffff;
            }
        """)
        self.quit_btn.clicked.connect(QApplication.instance().quit)
        v.addWidget(self.quit_btn)
    def _update_auth_button(self):
        """Update auth button text and connection based on login state."""
        try:
            self.auth_btn.clicked.disconnect()
        except RuntimeError:
            pass  # No connection to disconnect

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
        import os
        token_path = "token.json"
        if os.path.exists(token_path):
            os.remove(token_path)
            StyledMessageBox.information(self, "Signed Out", "Google account disconnected.")
            self._update_auth_button()
        else:
            StyledMessageBox.information(self, "Not Signed In", "No Google account currently connected.")

    def get_values(self):
        return {
            "provider": self.provider.currentIndex(),  # 0 Google, 1 MS, 2 ICS
            "preview": self.chk_preview.isChecked(),
            "always_on_top": self.chk_always_on_top.isChecked(),
            "auto_hide": self.chk_auto_hide.isChecked(),
        }


class InputDialog(StyledDialog):
    """Styled input dialog for entering event descriptions."""
    def __init__(self, parent=None, title="", label="", default_text=""):
        super().__init__(parent, title)
        self.setFixedSize(400, 180)

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        v.addWidget(title_label)

        # Input field
        self.input = QLineEdit()
        self.input.setPlaceholderText(label)
        if default_text:
            self.input.setText(default_text)
            self.input.selectAll()  # Select all so user can easily replace or edit
        v.addWidget(self.input)

        v.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn = QPushButton("Schedule")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #48484a;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #5a5a5c;
            }
        """)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.ok_btn)
        v.addLayout(btn_row)

        # Allow Enter key to submit
        self.input.returnPressed.connect(self.accept)

    def get_text(self):
        return self.input.text()

    @staticmethod
    def getText(parent, title, label, default_text=""):
        dlg = InputDialog(parent, title, label, default_text)
        result = dlg.exec()
        return dlg.get_text(), result == QDialog.Accepted


class StyledMessageBox(StyledDialog):
    """Styled message box matching the app design."""
    def __init__(self, parent=None, title="", message=""):
        super().__init__(parent, title)
        self.setFixedSize(360, 180)

        v = QVBoxLayout(self)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        v.addWidget(title_label)

        # Message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        v.addWidget(msg_label)

        v.addStretch()

        # OK button
        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self.accept)
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #48484a;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #5a5a5c;
            }
        """)
        v.addWidget(self.ok_btn, alignment=Qt.AlignRight)

    @staticmethod
    def information(parent, title, message):
        dlg = StyledMessageBox(parent, title, message)
        dlg.exec()

    @staticmethod
    def critical(parent, title, message):
        dlg = StyledMessageBox(parent, title, message)
        dlg.exec()

    @staticmethod
    def question(parent, title, message) -> bool:
        """
        Show a Yes/No question dialog.
        Returns True if user clicked Yes, False otherwise.
        """
        dlg = StyledDialog(parent, title)
        dlg.setFixedSize(400, 200)

        v = QVBoxLayout(dlg)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        v.addWidget(title_label)

        # Message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet("color: #ffffff;")
        v.addWidget(msg_label)

        v.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        no_btn = QPushButton("No")
        no_btn.clicked.connect(dlg.reject)
        no_btn.setStyleSheet("""
            QPushButton {
                background-color: #48484a;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                color: #ffffff;
                border: none;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #5a5a5c; }
        """)
        btn_layout.addWidget(no_btn)

        yes_btn = QPushButton("Yes")
        yes_btn.clicked.connect(dlg.accept)
        yes_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a84ff;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                color: #ffffff;
                border: none;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #409cff; }
        """)
        btn_layout.addWidget(yes_btn)

        v.addLayout(btn_layout)

        return dlg.exec() == QDialog.Accepted


class MainWindow(QWidget):
    EDGE_MARGIN = 8  # pixels from edge to trigger resize

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        screen = QGuiApplication.primaryScreen().geometry()
        w = screen.width() // 5
        h = screen.height() * 2 // 7
        self.resize(w, h)
        self.move((screen.width() - w) // 2, (screen.height() - h) // 2)
        self.setMinimumSize(200, 150)

        # Frameless window with rounded corners
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # For dragging and resizing
        self._drag_pos = None
        self._resizing = False
        self._resize_edge = None
        self.setMouseTracking(True)

        # For auto-collapse
        self._collapsed = False
        self._expanded_size = None
        self._expanded_pos = None
        self._expand_timer = QTimer(self)
        self._expand_timer.setSingleShot(True)
        self._expand_timer.timeout.connect(self._expand)
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.timeout.connect(self._collapse)

        # Style children but not the main widget background (painted in paintEvent)
        self.setStyleSheet("""
            QWidget {
                color: #ffffff;
            }
        """)

        # --- Menu actions (only Settings and Quit) ---
        self.settings_values = {"provider": 0, "preview": True, "always_on_top": True, "auto_hide": True}

        # Shared button style for all buttons
        button_style = """
            QPushButton {
                font-size: 13px;
                padding: 8px 16px;
                border-radius: 6px;
                background-color: #2c2c2e;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #3a3a3c;
            }
            QPushButton:pressed {
                background-color: #1c1c1e;
            }
        """

        # Top row: Settings button only
        top = QHBoxLayout()
        top.addStretch(1)
        self.btn_settings = QPushButton("Settings")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.setStyleSheet(button_style)
        self.btn_settings.clicked.connect(self.open_settings)
        top.addWidget(self.btn_settings)

        # --- Main content: Simple "+" button ---
        self.btn_ai = QPushButton("+")
        self.btn_ai.setCursor(Qt.PointingHandCursor)
        self.btn_ai.setFixedSize(64, 64)
        self.btn_ai.setStyleSheet("""
            QPushButton {
                font-size: 32px;
                font-weight: 300;
                border-radius: 12px;
                background-color: #2c2c2e;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #3a3a3c;
            }
            QPushButton:pressed {
                background-color: #1c1c1e;
            }
        """)
        self.btn_ai.clicked.connect(self.on_ai_assistant)

        # --- Layout ---
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.addLayout(top)
        v.addStretch(1)
        v.addWidget(self.btn_ai, alignment=Qt.AlignHCenter)
        v.addStretch(2)

    def _get_edge(self, pos):
        """Determine which edge/corner the mouse is near."""
        if self._collapsed:
            return None  # No resizing when collapsed
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = self.EDGE_MARGIN

        left = x < m
        right = x > w - m
        top = y < m
        bottom = y > h - m

        if top and left:
            return "top-left"
        if top and right:
            return "top-right"
        if bottom and left:
            return "bottom-left"
        if bottom and right:
            return "bottom-right"
        if left:
            return "left"
        if right:
            return "right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        return None

    def _update_cursor(self, edge):
        """Update cursor based on edge."""
        cursors = {
            "left": Qt.SizeHorCursor,
            "right": Qt.SizeHorCursor,
            "top": Qt.SizeVerCursor,
            "bottom": Qt.SizeVerCursor,
            "top-left": Qt.SizeFDiagCursor,
            "bottom-right": Qt.SizeFDiagCursor,
            "top-right": Qt.SizeBDiagCursor,
            "bottom-left": Qt.SizeBDiagCursor,
        }
        if edge in cursors:
            self.setCursor(cursors[edge])
        else:
            self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            edge = self._get_edge(event.position().toPoint())
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geo = self.geometry()
            else:
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._resizing and self._resize_edge:
            diff = event.globalPosition().toPoint() - self._resize_start_pos
            geo = self._resize_start_geo
            new_geo = self.geometry()

            edge = self._resize_edge
            if "right" in edge:
                new_geo.setWidth(max(self.minimumWidth(), geo.width() + diff.x()))
            if "bottom" in edge:
                new_geo.setHeight(max(self.minimumHeight(), geo.height() + diff.y()))
            if "left" in edge:
                new_w = max(self.minimumWidth(), geo.width() - diff.x())
                if new_w != geo.width():
                    new_geo.setLeft(geo.left() + (geo.width() - new_w))
                    new_geo.setWidth(new_w)
            if "top" in edge:
                new_h = max(self.minimumHeight(), geo.height() - diff.y())
                if new_h != geo.height():
                    new_geo.setTop(geo.top() + (geo.height() - new_h))
                    new_geo.setHeight(new_h)

            self.setGeometry(new_geo)
        elif self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
        else:
            edge = self._get_edge(event.position().toPoint())
            self._update_cursor(edge)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        self._resizing = False
        self._resize_edge = None
        self._update_cursor(self._get_edge(event.position().toPoint()))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        radius = 12 if self._collapsed else 16
        color = "#2c2c2e" if self._collapsed else "#1c1c1e"
        path.addRoundedRect(0, 0, self.width(), self.height(), radius, radius)
        painter.fillPath(path, QColor(color))

    def enterEvent(self, event):
        """Expand when mouse enters and auto-hide is enabled."""
        self._collapse_timer.stop()
        if self._collapsed and self.settings_values.get("auto_hide", True):
            self._expand_timer.start(300)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Collapse when mouse leaves and auto-hide is enabled."""
        self._expand_timer.stop()
        if not self._collapsed and self.settings_values.get("auto_hide", True):
            self._collapse_timer.start(400)
        super().leaveEvent(event)

    def _get_collapse_corner(self):
        """Determine which corner of the window to collapse to based on screen quadrant."""
        screen = QApplication.primaryScreen().geometry()
        geo = self.geometry()
        center = geo.center()
        collapsed_size = 48

        # Determine which screen quadrant the window is in
        in_left = center.x() < screen.center().x()
        in_top = center.y() < screen.center().y()

        # Collapse to the corresponding corner of the current window
        if in_top and in_left:
            # Top-left quadrant -> collapse to top-left corner of window
            return QRect(geo.x(), geo.y(), collapsed_size, collapsed_size)
        elif in_top and not in_left:
            # Top-right quadrant -> collapse to top-right corner of window
            return QRect(geo.right() - collapsed_size, geo.y(), collapsed_size, collapsed_size)
        elif not in_top and in_left:
            # Bottom-left quadrant -> collapse to bottom-left corner of window
            return QRect(geo.x(), geo.bottom() - collapsed_size, collapsed_size, collapsed_size)
        else:
            # Bottom-right quadrant -> collapse to bottom-right corner of window
            return QRect(geo.right() - collapsed_size, geo.bottom() - collapsed_size, collapsed_size, collapsed_size)

    def _collapse(self):
        """Collapse to a small button with animation, snapping to nearest corner."""
        if self._collapsed:
            return
        self._collapsed = True
        self._expanded_size = self.size()
        self._expanded_pos = self.pos()

        # Remember which corner we're collapsing to
        screen = QApplication.primaryScreen().geometry()
        center = self.geometry().center()
        self._collapse_corner = (
            center.y() < screen.center().y(),  # in_top
            center.x() < screen.center().x()   # in_left
        )

        # Hide main content
        self.btn_settings.hide()
        self.btn_ai.hide()

        # Change + button to star icon with transparent background
        self.btn_ai.setText("")
        self.btn_ai.setIcon(create_star_icon(28))
        self.btn_ai.setIconSize(QSize(48, 48))
        self.btn_ai.setFixedSize(48, 48)
        self.btn_ai.setStyleSheet("""
            QPushButton {
                border-radius: 12px;
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #3a3a3c;
            }
        """)
        self.btn_ai.show()
        self.layout().setContentsMargins(0, 0, 0, 0)

        # Animate collapse to corner based on screen quadrant
        self.setMinimumSize(48, 48)
        self.setMaximumSize(16777215, 16777215)
        target = self._get_collapse_corner()
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(250)
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(lambda: self.setFixedSize(48, 48))
        self._anim.start()

    def _expand(self):
        """Expand back to full size with animation, restoring original position."""
        if not self._collapsed:
            return
        self._collapsed = False

        # Capture the 48x48 start geometry BEFORE any layout changes
        start_geo = self.geometry()

        # Remove fixed size constraint
        self.setMinimumSize(48, 48)
        self.setMaximumSize(16777215, 16777215)

        # Restore layout so content is in final position during animation
        self.layout().setContentsMargins(16, 16, 16, 16)
        self.btn_ai.setIcon(QIcon())
        self.btn_ai.setText("+")
        self.btn_ai.setFixedSize(64, 64)
        self.btn_ai.setStyleSheet("""
            QPushButton {
                font-size: 32px;
                font-weight: 300;
                border-radius: 12px;
                background-color: #2c2c2e;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #3a3a3c;
            }
            QPushButton:pressed {
                background-color: #1c1c1e;
            }
        """)
        self.btn_settings.show()
        self.btn_ai.show()

        # Force back to 48x48 start position (undo any Qt auto-resize)
        self.setGeometry(start_geo)

        # Animate from captured start to target
        target_size = self._expanded_size if self._expanded_size else QSize(320, 240)
        target_pos = self._expanded_pos if self._expanded_pos else self.pos()
        target = QRect(target_pos, target_size)
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(250)
        self._anim.setStartValue(start_geo)
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._on_expand_finished)
        self._anim.start()

    def _on_expand_finished(self):
        """Called when expand animation finishes."""
        self.setMinimumSize(200, 150)
        self.setMaximumSize(16777215, 16777215)

    def _snap_expand(self):
        """Instantly restore to expanded state (no animation)."""
        if not self._collapsed:
            return
        self._collapsed = False
        self.setMinimumSize(200, 150)
        self.setMaximumSize(16777215, 16777215)
        target_size = self._expanded_size if self._expanded_size else QSize(320, 240)
        target_pos = self._expanded_pos if self._expanded_pos else self.pos()
        self.setGeometry(QRect(target_pos, target_size))
        self.layout().setContentsMargins(16, 16, 16, 16)
        self.btn_ai.setIcon(QIcon())
        self.btn_ai.setText("+")
        self.btn_ai.setFixedSize(64, 64)
        self.btn_ai.setStyleSheet("""
            QPushButton {
                font-size: 32px;
                font-weight: 300;
                border-radius: 12px;
                background-color: #2c2c2e;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #3a3a3c;
            }
            QPushButton:pressed {
                background-color: #1c1c1e;
            }
        """)
        self.btn_settings.show()
        self.btn_ai.show()
        self.update()

    # --------- Settings ---------
    def open_settings(self):
        dlg = SettingsDialog(self)
        # prefill
        dlg.provider.setCurrentIndex(self.settings_values.get("provider", 0))
        dlg.chk_preview.setChecked(self.settings_values.get("preview", True))
        dlg.chk_always_on_top.setChecked(self.settings_values.get("always_on_top", False))
        dlg.chk_auto_hide.setChecked(self.settings_values.get("auto_hide", True))
        if dlg.exec() == QDialog.Accepted:
            self.settings_values = dlg.get_values()
            self._apply_always_on_top()
            # If auto-hide was just disabled and we're collapsed, snap back instantly
            if not self.settings_values.get("auto_hide", True) and self._collapsed:
                self._snap_expand()
            self.toast("Settings saved")

    def _apply_always_on_top(self):
        """Apply or remove the always-on-top window flag."""
        if self.settings_values.get("always_on_top", False):
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()

    # --------- AI flow (prompt → parse → create) ---------
    def on_ai_assistant(self):
        # Check Google auth BEFORE anything else to avoid wasting AI tokens
        if not is_authenticated():
            if StyledMessageBox.question(
                self,
                "Sign In Required",
                "Please sign in to Google Calendar to schedule events.\n\nSign in now?"
            ):
                try:
                    _ensure_creds()
                except Exception as e:
                    StyledMessageBox.critical(self, "Sign In Failed", str(e))
                    return
            else:
                return  # User declined to sign in

        current_prompt = ""

        while True:
            # Get input (with previous text preserved on retry)
            prompt, ok = InputDialog.getText(
                self,
                "What should I schedule?",
                "e.g. 'Lunch with Alice tomorrow 1–2pm at campus'",
                default_text=current_prompt,
            )
            if not ok:
                return  # User cancelled
            if not prompt.strip():
                continue  # Empty input, ask again

            current_prompt = prompt  # Save for retry

            # Parse prompt with validation
            try:
                ev, warnings = logic.build_event_dict_from_prompt(prompt)
            except RateLimitExceededError as e:
                StyledMessageBox.critical(self, "Please Wait", e.user_message)
                return  # Rate limit is a hard stop, don't retry
            except InputTooLongError as e:
                StyledMessageBox.critical(self, "Input Too Long", e.user_message)
                continue  # Let user edit
            except ValidationError as e:
                StyledMessageBox.critical(self, "Couldn't Parse Event", e.user_message)
                continue  # Let user edit
            except Exception as e:
                StyledMessageBox.critical(self, "AI Error", str(e))
                continue  # Let user edit

            # Handle soft warnings with "Are you sure?" confirmation
            if warnings:
                warning_text = "\n".join(f"• {w.message}" for w in warnings)
                if not StyledMessageBox.question(
                    self,
                    "Are you sure?",
                    f"{warning_text}\n\nAdd this event anyway?"
                ):
                    continue  # Let user edit

            # Always show confirmation preview before adding
            if not self.show_event_confirmation(ev):
                continue  # User chose to edit

            # Add to calendar
            provider = self.settings_values.get("provider", 0)
            try:
                if provider == 0:
                    created = add_event_to_google(ev)
                elif provider == 1:
                    raise NotImplementedError("Microsoft integration not enabled yet.")
                else:
                    raise NotImplementedError("ICS flow is paused in this build.")

                self.show_event_preview(created)
                self.toast("Event added to calendar")
                return  # Success, exit loop

            except Exception as e:
                StyledMessageBox.critical(self, "Calendar Error", str(e))
                continue  # Let user try again

    def show_event_confirmation(self, ev: dict) -> bool:
        """
        Show event preview BEFORE adding to calendar.
        Returns True if user confirms, False if they want to edit.
        """
        dlg = StyledDialog(self, "Confirm Event")
        dlg.setFixedSize(380, 270)  # Slightly taller to fit recurrence info

        v = QVBoxLayout(dlg)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        # Title
        title_label = QLabel("Add this event?")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        v.addWidget(title_label)

        # Event details
        summary = ev.get("summary", "(no title)")
        start = ev.get("start")
        end = ev.get("end")

        event_title = QLabel(summary)
        event_title.setStyleSheet("font-size: 14px; color: #ffffff;")
        event_title.setWordWrap(True)
        v.addWidget(event_title)

        # Format times nicely
        if hasattr(start, 'strftime'):
            date_str = start.strftime("%A, %B %d, %Y")
            time_str = f"{start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}"
        else:
            date_str = str(start)
            time_str = f"{start} - {end}"

        date_label = QLabel(date_str)
        date_label.setStyleSheet("font-size: 13px; color: #8e8e93;")
        v.addWidget(date_label)

        time_label = QLabel(time_str)
        time_label.setStyleSheet("font-size: 13px; color: #8e8e93;")
        v.addWidget(time_label)

        # Show recurrence if present
        recurrence = ev.get("recurrence")
        if recurrence:
            recur_text = self._format_recurrence(recurrence)
            recur_label = QLabel(f"Repeats: {recur_text}")
            recur_label.setStyleSheet("font-size: 13px; color: #0a84ff;")
            v.addWidget(recur_label)

        v.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(dlg.reject)
        edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #48484a;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                color: #ffffff;
                border: none;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #5a5a5c; }
        """)
        btn_row.addWidget(edit_btn)

        confirm_btn = QPushButton("Add Event")
        confirm_btn.clicked.connect(dlg.accept)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #0a84ff;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                color: #ffffff;
                border: none;
                min-width: 80px;
            }
            QPushButton:hover { background-color: #409cff; }
        """)
        btn_row.addWidget(confirm_btn)

        v.addLayout(btn_row)

        return dlg.exec() == QDialog.Accepted

    def _format_recurrence(self, recurrence) -> str:
        """Convert RRULE to human-readable text."""
        if not recurrence:
            return ""

        # recurrence is a list of RRULE strings
        rrule = recurrence[0] if isinstance(recurrence, list) else recurrence
        rrule = rrule.upper().replace("RRULE:", "")

        # Parse common patterns
        parts = dict(p.split("=") for p in rrule.split(";") if "=" in p)
        freq = parts.get("FREQ", "")
        count = parts.get("COUNT", "")
        byday = parts.get("BYDAY", "")
        interval = parts.get("INTERVAL", "1")

        # Build human-readable string
        freq_map = {
            "DAILY": "Daily",
            "WEEKLY": "Weekly",
            "MONTHLY": "Monthly",
            "YEARLY": "Yearly",
        }
        day_map = {
            "MO": "Mon", "TU": "Tue", "WE": "Wed", "TH": "Thu",
            "FR": "Fri", "SA": "Sat", "SU": "Sun"
        }

        result = freq_map.get(freq, freq.capitalize())

        if interval and interval != "1":
            result = f"Every {interval} " + ("days" if freq == "DAILY" else
                                              "weeks" if freq == "WEEKLY" else
                                              "months" if freq == "MONTHLY" else "years")

        if byday:
            days = [day_map.get(d.strip("0123456789-"), d) for d in byday.split(",")]
            result += f" on {', '.join(days)}"

        if count:
            result += f" ({count} times)"

        return result

    # --------- Pretty preview + helpers ---------
    def show_event_preview(self, created: dict):
        dlg = StyledDialog(self, "Event created")
        dlg.setFixedSize(360, 220)

        v = QVBoxLayout(dlg)
        v.setContentsMargins(24, 24, 24, 24)
        v.setSpacing(12)

        title = created.get("summary", "(no title)")
        start = created.get("start", "?")
        end = created.get("end", "?")

        # Title
        title_label = QLabel("Event Created")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        v.addWidget(title_label)

        # Event details
        event_title = QLabel(title)
        event_title.setStyleSheet("font-size: 14px; color: #ffffff;")
        v.addWidget(event_title)

        time_label = QLabel(f"{start} -> {end}")
        time_label.setStyleSheet("font-size: 12px; color: #8e8e93;")
        v.addWidget(time_label)

        v.addStretch()

        link = created.get("htmlLink")

        def open_link():
            if link:
                QDesktopServices.openUrl(QUrl(link))
        def copy_link():
            if link:
                QGuiApplication.clipboard().setText(link)
                self.toast("Link copied")

        # Buttons
        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(open_link)
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #48484a;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 6px;
                color: #ffffff;
                border: none;
            }
            QPushButton:hover {
                background-color: #5a5a5c;
            }
        """)
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(copy_link)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)

        btn_row.addWidget(open_btn)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(close_btn)
        v.addLayout(btn_row)

        dlg.exec()

    def toast(self, text: str, ms: int = 2200):
        # Create toast as a top-level frameless window (works even when main window is collapsed)
        note = QLabel(text)
        note.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        note.setAttribute(Qt.WA_TransparentForMouseEvents)
        note.setAttribute(Qt.WA_ShowWithoutActivating)
        note.setStyleSheet(
            "QLabel{background:rgba(30,30,30,0.95); color:white; padding:10px 16px;"
            "border-radius:10px; font-size:12pt;}"
        )
        note.adjustSize()

        # Position near bottom-right of main window (using screen coordinates)
        m = 12
        win_geo = self.geometry()  # Screen coordinates of main window
        toast_x = win_geo.right() - note.width() - m
        toast_y = win_geo.bottom() - note.height() - m

        # If window is collapsed, position above/beside it instead
        if self._collapsed:
            toast_x = win_geo.x() - note.width() - m
            toast_y = win_geo.y()
            # If that would go off-screen left, put it to the right
            if toast_x < 0:
                toast_x = win_geo.right() + m

        note.move(toast_x, toast_y)
        note.show()

        # Fade in animation
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
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
