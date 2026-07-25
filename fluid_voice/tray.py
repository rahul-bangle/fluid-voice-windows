from enum import Enum, auto
import logging
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen
from PyQt6.QtCore import pyqtSignal, Qt, QObject

logger = logging.getLogger(__name__)


class TrayState(Enum):
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    ERROR = auto()


class FluidVoiceTrayIcon(QSystemTrayIcon):
    """
    PyQt6 QSystemTrayIcon wrapper with procedural SVG/QPixmap icon rendering,
    multi-state visual indicators, context menu, and signals for app interaction.
    """
    recording_toggled = pyqtSignal()
    settings_requested = pyqtSignal()
    dashboard_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._state = TrayState.IDLE
        self._init_menu()
        self.set_state(TrayState.IDLE)
        self.activated.connect(self._on_activated)

    def _init_menu(self) -> None:
        menu = QMenu()

        # Context Menu Actions
        self.toggle_action = menu.addAction("Toggle Recording (Alt+S)")
        self.toggle_action.triggered.connect(self.recording_toggled.emit)

        self.dashboard_action = menu.addAction("📊 Open Dashboard")
        self.dashboard_action.triggered.connect(self.dashboard_requested.emit)

        self.settings_action = menu.addAction("⚙️ Settings...")
        self.settings_action.triggered.connect(self.settings_requested.emit)

        menu.addSeparator()

        exit_action = menu.addAction("🚪 Quit VeloVoice")
        exit_action.triggered.connect(self.exit_requested.emit)

        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # Single click
            self.recording_toggled.emit()
        elif reason == QSystemTrayIcon.ActivationReason.DoubleClick:  # Double click
            self.dashboard_requested.emit()

    @staticmethod
    def create_state_icon(state: TrayState) -> QIcon:
        """Procedurally draws a crisp microphone badge icon for high-DPI Windows tray."""
        size = 32
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # State background colors
        if state == TrayState.IDLE:
            bg_color = QColor("#007ACC")  # Blue accent
        elif state == TrayState.RECORDING:
            bg_color = QColor("#E51400")  # Red active
        elif state == TrayState.TRANSCRIBING:
            bg_color = QColor("#E3A857")  # Amber transcribing
        else:  # ERROR
            bg_color = QColor("#666666")  # Gray error

        # Outer badge circle
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)

        # Draw Microphone symbol in crisp white
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        
        # Mic capsule body
        painter.drawRoundedRect(12, 7, 8, 12, 4, 4)

        # Mic stand arc
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawArc(9, 11, 14, 11, 0, -180 * 16)

        # Mic stand vertical line and base bar
        painter.drawLine(16, 22, 16, 26)
        painter.drawLine(12, 26, 20, 26)

        # If ERROR state, add warning exclamation mark badge
        if state == TrayState.ERROR:
            painter.setBrush(QBrush(QColor("#FF0000")))
            painter.setPen(QPen(QColor("#FFFFFF"), 1))
            painter.drawEllipse(20, 20, 10, 10)
            painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
            painter.drawLine(25, 22, 25, 26)
            painter.drawPoint(25, 28)

        painter.end()
        return QIcon(pixmap)

    @property
    def current_state(self) -> TrayState:
        return self._state

    def set_state(self, state: TrayState, custom_tooltip: str | None = None) -> None:
        """Updates the system tray icon image and tooltip string."""
        self._state = state
        self.setIcon(self.create_state_icon(state))

        status_text = {
            TrayState.IDLE: "Ready",
            TrayState.RECORDING: "Listening...",
            TrayState.TRANSCRIBING: "Transcribing...",
            TrayState.ERROR: "Error / Warning"
        }.get(state, "Ready")

        tooltip = custom_tooltip or f"FluidVoice - {status_text}"
        self.setToolTip(tooltip)
