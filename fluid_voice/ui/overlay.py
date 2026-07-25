"""
fluid_voice.ui.overlay: Frameless Glassmorphism Floating Overlay UI Widget.

Provides non-stealing focus, floating top-most HUD for FluidVoice Windows.
Displays animated audio level waveform (5 dynamic bars with exponential decay smoothing),
state badges/text ('LISTENING', 'TRANSCRIBING', 'PASTED', 'ERROR'),
smooth opacity fade-out animation, and auto-hide timers.
"""

import sys
import math
import ctypes
import logging
from enum import Enum
from typing import Optional

from PyQt6.QtCore import (
    Qt,
    QTimer,
    pyqtSignal,
    QRectF,
    QEasingCurve,
    QPropertyAnimation,
    QAbstractAnimation,
)
from PyQt6.QtGui import (
    QColor,
    QPainter,
    QBrush,
    QPen,
    QPainterPath,
    QFont,
    QLinearGradient,
    QCursor,
)
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QApplication,
    QGraphicsDropShadowEffect,
)

logger = logging.getLogger(__name__)

# Exports
__all__ = ["OverlayWidget", "OverlayState", "WaveformWidget", "WaveformVisualizer", "apply_win32_no_activate"]

# Win32 Constants for non-stealing window style
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000  # Prevents window from gaining focus when shown
WS_EX_TOOLWINDOW = 0x00000080  # Hides window from Taskbar and Alt+Tab menu
WS_EX_TOPMOST    = 0x00000008  # Keeps window on top of all standard windows


def apply_win32_no_activate(hwnd: int) -> None:
    """
    Apply Win32 extended window styles to prevent focus activation when window is shown.
    Ensures active text editor / window caret focus is never stolen.
    """
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.windll.user32
        if hasattr(user32, "SetWindowLongPtrW"):
            get_style = user32.GetWindowLongPtrW
            set_style = user32.SetWindowLongPtrW
        else:
            get_style = user32.GetWindowLongW
            set_style = user32.SetWindowLongW

        current_style = get_style(hwnd, GWL_EXSTYLE)
        new_style = current_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST
        set_style(hwnd, GWL_EXSTYLE, new_style)
    except Exception as e:
        logger.debug(f"Failed to set Win32 window styles for hwnd {hwnd}: {e}")


class OverlayState(str, Enum):
    """Supported state enum for FluidVoice Overlay."""
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    PASTED = "pasted"
    ERROR = "error"


class WaveformWidget(QWidget):
    """
    Custom QPainter widget rendering 5 dynamic audio waveform bars.
    Uses exponential decay smoothing for organic reactivity to audio input levels.
    """

    def __init__(self, num_bars: int = 5, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.num_bars = num_bars
        self.setFixedSize(54, 28)
        self._target_level = 0.0
        self._smoothed_level = 0.0
        self._phase = 0.0
        self._state = "listening"

        # 60 FPS Animation Timer (16ms interval)
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(16)
        self._anim_timer.timeout.connect(self._on_anim_frame)

    @property
    def audio_level(self) -> float:
        return self._target_level

    @audio_level.setter
    def audio_level(self, val: float) -> None:
        self.set_level(val)

    def set_level(self, level: float) -> None:
        """Update target audio input level (clamped 0.0 to 1.0)."""
        self._target_level = max(0.0, min(1.0, float(level)))
        if self._state not in ("listening", "transcribing"):
            self.update()

    def set_state(self, state: str) -> None:
        """Update visual state and control animation timer."""
        self._state = state.lower()
        if self._state == "listening":
            if not self._anim_timer.isActive():
                self._anim_timer.start()
        elif self._state == "transcribing":
            self._smoothed_level = 0.0
            self._target_level = 0.0
            if not self._anim_timer.isActive():
                self._anim_timer.start()
        else:
            self._anim_timer.stop()
            self._smoothed_level = 0.0
            self._target_level = 0.0
            self.update()

    def _on_anim_frame(self) -> None:
        """Physics step (exponential decay smoothing) and phase advancement."""
        self._smoothed_level += (self._target_level - self._smoothed_level) * 0.25
        self._phase += 0.15
        if self._phase > 6.283185307179586:  # 2*pi wrap
            self._phase -= 6.283185307179586
        self.update()

    def paintEvent(self, event) -> None:
        if not self.isVisible():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        num_bars = self.num_bars
        bar_width = 4
        bar_gap = 5
        total_width = num_bars * bar_width + (num_bars - 1) * bar_gap
        start_x = (self.width() - total_width) // 2
        center_y = self.height() // 2

        # State-based Gradient Palette
        if self._state == "listening":
            color_start = QColor("#00F2FE")
            color_end = QColor("#4FACFE")
        elif self._state == "transcribing":
            color_start = QColor("#8B5CF6")
            color_end = QColor("#6366F1")
        elif self._state in ("pasted", "idle", "peace"):
            # Wispr Flow Soft Emerald Peace State
            color_start = QColor("#10B981")
            color_end = QColor("#059669")
        else:  # error / fallback
            color_start = QColor("#EF4444")
            color_end = QColor("#F59E0B")

        gradient = QLinearGradient(0, 0, 0, float(self.height()))
        gradient.setColorAt(0.0, color_start)
        gradient.setColorAt(1.0, color_end)
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(num_bars):
            if self._state == "transcribing":
                # Gentle pulsing wave when transcribing
                level_mod = 0.4 + 0.3 * math.sin(self._phase + i * 0.9)
            elif self._state == "listening":
                level_mod = self._smoothed_level * (0.35 + 0.65 * math.sin(self._phase + i * 0.85))
            else:
                level_mod = 0.1

            bar_h = max(4.0, min(24.0, 4.0 + 20.0 * level_mod))
            x = float(start_x + i * (bar_width + bar_gap))
            y = float(center_y) - bar_h / 2.0

            path = QPainterPath()
            path.addRoundedRect(x, y, float(bar_width), bar_h, 2.0, 2.0)
            painter.drawPath(path)


# Backward compatibility alias
WaveformVisualizer = WaveformWidget


class OverlayWidget(QWidget):
    """
    Frameless, semi-transparent dark mode glassmorphism floating overlay UI widget.
    
    Non-stealing window focus HUD displaying live mic audio waveform, state transitions,
    smooth fade animations, and auto-hide timers.
    """

    state_changed = pyqtSignal(str, str)  # (state_name, message)
    closed = pyqtSignal()

    STATE_COLORS = {
        "listening": QColor(0, 210, 255, 220),       # Cyan
        "transcribing": QColor(255, 170, 0, 220),    # Amber/Gold
        "pasted": QColor(16, 185, 129, 220),         # Wispr Flow Soft Emerald Peace Green
        "peace": QColor(16, 185, 129, 220),          # Wispr Flow Soft Emerald Peace Green
        "error": QColor(255, 69, 58, 220),           # Bright Red
        "idle": QColor(156, 163, 175, 220),          # Gray
    }

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._state = OverlayState.IDLE
        self._message = "Listening..."
        self._screen_position = "top_center"
        self._margin_y = 40
        self._pasted_auto_hide_ms = 1500
        self._error_auto_hide_ms = 3000

        self.apply_window_flags()
        self._init_ui()
        self._init_timers_and_animations()

        self._state = OverlayState.IDLE
        self._message = "Ready"
        self._waveform.set_state("idle")
        self._lbl_status.setText(self._message)
        self.hide()

    def apply_window_flags(self) -> None:
        """Configure top-most, frameless, non-activating window flags."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

    def _init_ui(self) -> None:
        self.setFixedSize(280, 70)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(12)

        self._waveform = WaveformWidget(num_bars=5, parent=self)
        self.waveform = self._waveform  # Attribute alias for compatibility
        layout.addWidget(self._waveform)

        self._lbl_status = QLabel(self._message, self)
        self.status_label = self._lbl_status  # Attribute alias for compatibility
        font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        self._lbl_status.setFont(font)
        self._lbl_status.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(self._lbl_status, stretch=1)

        # Glassmorphism background and subtle border rendered in paintEvent without top-level shadow overflow

    def _init_timers_and_animations(self) -> None:
        """Initialize auto-hide QTimer and smooth window opacity QPropertyAnimation."""
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._start_fade_out)

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(300)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_anim.finished.connect(self._on_fade_out_finished)

    def showEvent(self, event) -> None:
        """Enforce Win32 non-activating style upon display and center on screen."""
        super().showEvent(event)
        apply_win32_no_activate(int(self.winId()))
        self.center_on_screen()

    @property
    def current_state(self) -> str:
        if isinstance(self._state, OverlayState):
            return self._state.value
        return str(self._state)

    def set_state(self, state: str | OverlayState, message: Optional[str] = None) -> None:
        """
        Transition overlay state ('listening', 'transcribing', 'pasted', 'error').
        
        Args:
            state: State name or OverlayState enum.
            message: Optional display text prompt.
        """
        raw_state = state.value if isinstance(state, OverlayState) else str(state).lower()
        if raw_state not in self.STATE_COLORS and raw_state not in [s.value for s in OverlayState]:
            logger.warning(f"Unknown overlay state '{state}', defaulting to 'listening'.")
            enum_state = OverlayState.LISTENING
        else:
            try:
                enum_state = OverlayState(raw_state)
            except ValueError:
                enum_state = OverlayState.LISTENING

        self._state = enum_state
        self._cancel_auto_hide()
        self.setWindowOpacity(1.0)

        if self._state == OverlayState.LISTENING:
            self._message = message or "Listening..."
            self._waveform.set_state("listening")
            self.show_overlay()

        elif self._state == OverlayState.TRANSCRIBING:
            self._message = message or "Transcribing..."
            self._waveform.set_state("transcribing")
            self.show_overlay()

        elif self._state == OverlayState.PASTED:
            self._message = message or "Pasted!"
            self._waveform.set_state("pasted")
            self.show_overlay()
            self._schedule_auto_hide(self._pasted_auto_hide_ms)

        elif self._state == OverlayState.ERROR:
            self._message = message or "Error"
            self._waveform.set_state("error")
            self.show_overlay()
            self._schedule_auto_hide(self._error_auto_hide_ms)

        elif self._state == OverlayState.IDLE:
            self._message = message or "Ready"
            self._waveform.set_state("idle")
            self._schedule_auto_hide(200)

        self._lbl_status.setText(self._message)
        self.update()
        self.state_changed.emit(self.current_state, self._message)

    def update_audio_level(self, level: float) -> None:
        """Forward real-time audio input RMS level (0.0 to 1.0) to waveform."""
        if self._state == OverlayState.LISTENING:
            self._waveform.set_level(level)

    def show_toast(self, message: str, duration_ms: int = 2500) -> None:
        """
        Displays a floating glass toast notification pill for duration_ms
        without stealing window focus.
        """
        self._message = message
        self._lbl_status.setText(message)
        self._waveform.set_state("idle")
        self.show_overlay()
        self._schedule_auto_hide(duration_ms)

    def show_overlay(self) -> None:
        """Display overlay without stealing active window focus."""
        self._cancel_auto_hide()
        self.setWindowOpacity(1.0)
        if not self.isVisible():
            self.show()
            self.raise_()

    def _cancel_auto_hide(self) -> None:
        """Cancel active auto-hide timer and opacity fade animation."""
        if self._auto_hide_timer.isActive():
            self._auto_hide_timer.stop()
        if self._fade_anim.state() == QAbstractAnimation.State.Running:
            self._fade_anim.stop()

    def _schedule_auto_hide(self, duration_ms: int) -> None:
        """Schedule auto-hide timeout."""
        self._cancel_auto_hide()
        self._auto_hide_timer.start(duration_ms)

    def _start_fade_out(self) -> None:
        """Begin 300ms smooth opacity fade-out animation."""
        if self._fade_anim.state() == QAbstractAnimation.State.Running:
            return
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _on_fade_out_finished(self) -> None:
        """Callback when fade-out animation completes."""
        self.hide()
        self.setWindowOpacity(1.0)
        self._waveform.set_state("idle")
        self.closed.emit()

    def center_on_screen(self) -> None:
        """Position overlay relative to active screen containing mouse cursor."""
        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        if not screen:
            return

        geom = screen.availableGeometry()
        w = self.width()
        h = self.height()

        x = geom.x() + (geom.width() - w) // 2
        if self._screen_position == "bottom_center":
            y = geom.y() + geom.height() - h - self._margin_y
        else:  # top_center default
            y = geom.y() + self._margin_y

        self.move(x, y)

    def center_bottom_position(self) -> None:
        """Position overlay near horizontal center, bottom of screen."""
        self._screen_position = "bottom_center"
        self._margin_y = 100
        self.center_on_screen()

    def center_top_position(self) -> None:
        """Position overlay near horizontal center, top of screen."""
        self._screen_position = "top_center"
        self._margin_y = 40
        self.center_on_screen()

    def paintEvent(self, event) -> None:
        """Custom QPainter glassmorphism background rendering."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 16.0, 16.0)

        # Translucent dark glass background fill rgba(24, 24, 28, 225) (~88% opacity)
        painter.fillPath(path, QColor(24, 24, 28, 225))

        # 1.2px subtle white highlight border rgba(255, 255, 255, 0.14) (35 alpha)
        pen = QPen(QColor(255, 255, 255, 35), 1.2)
        painter.setPen(pen)
        painter.drawPath(path)

