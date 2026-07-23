"""
Unit tests for fluid_voice.ui.overlay (Milestone 5 Sleek Minimal Floating Overlay UI).

Covers:
- Window flags and non-stealing Win32 focus attributes
- OverlayState enum and state transitions
- WaveformWidget animation, level clamping, and exponential decay smoothing
- Auto-hide timers, smooth 300ms opacity fade-out animation, and interruption protection
- Screen positioning math (top_center and bottom_center)
- Custom QPainter glassmorphism rendering
"""

import sys
import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt, QTimer, QAbstractAnimation
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QApplication

from fluid_voice.ui.overlay import (
    OverlayWidget,
    OverlayState,
    WaveformWidget,
    WaveformVisualizer,
    apply_win32_no_activate,
)


def test_overlay_window_flags_and_attributes(qapp):
    """Verify frameless glassmorphic widget flags and non-stealing focus attributes."""
    overlay = OverlayWidget()
    flags = overlay.windowFlags()

    assert bool(flags & Qt.WindowType.FramelessWindowHint)
    assert bool(flags & Qt.WindowType.WindowStaysOnTopHint)
    assert bool(flags & Qt.WindowType.Tool)
    assert bool(flags & Qt.WindowType.WindowDoesNotAcceptFocus)

    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
    assert overlay.width() == 280
    assert overlay.height() == 70


def test_win32_no_activate_hook(qapp):
    """Verify apply_win32_no_activate executes gracefully on all platforms."""
    overlay = OverlayWidget()
    hwnd = int(overlay.winId())
    # Should not raise any exceptions
    apply_win32_no_activate(hwnd)


def test_overlay_state_enum_and_string_values():
    """Verify OverlayState enum values match specified state strings."""
    assert OverlayState.IDLE.value == "idle"
    assert OverlayState.LISTENING.value == "listening"
    assert OverlayState.TRANSCRIBING.value == "transcribing"
    assert OverlayState.PASTED.value == "pasted"
    assert OverlayState.ERROR.value == "error"

    # Verify str comparison works cleanly
    assert OverlayState.LISTENING == "listening"


def test_overlay_state_transitions(qapp):
    """Verify state transitions update internal state, status text, and emit state_changed signal."""
    overlay = OverlayWidget()
    emitted = []
    overlay.state_changed.connect(lambda state, msg: emitted.append((state, msg)))

    # Listening
    overlay.set_state("listening", "Listening...")
    assert overlay.current_state == "listening"
    assert overlay.status_label.text() == "Listening..."

    # Transcribing
    overlay.set_state(OverlayState.TRANSCRIBING, "Processing speech...")
    assert overlay.current_state == "transcribing"
    assert overlay.status_label.text() == "Processing speech..."

    # Pasted
    overlay.set_state("pasted", "Text Pasted!")
    assert overlay.current_state == "pasted"
    assert overlay.status_label.text() == "Text Pasted!"

    # Error
    overlay.set_state("error", "STT API Error")
    assert overlay.current_state == "error"
    assert overlay.status_label.text() == "STT API Error"

    # Check signal emissions
    assert len(emitted) == 4
    assert emitted[0] == ("listening", "Listening...")
    assert emitted[1] == ("transcribing", "Processing speech...")
    assert emitted[2] == ("pasted", "Text Pasted!")
    assert emitted[3] == ("error", "STT API Error")


def test_overlay_unknown_state_fallback(qapp):
    """Verify unknown state fallback to listening."""
    overlay = OverlayWidget()
    overlay.set_state("unknown_xyz", "Fallback msg")
    assert overlay.current_state == "listening"
    assert overlay.status_label.text() == "Fallback msg"


def test_waveform_level_clamping_and_smoothing(qapp):
    """Verify WaveformWidget clamps audio levels to [0.0, 1.0] and applies exponential smoothing."""
    waveform = WaveformWidget(num_bars=5)

    # Clamping
    waveform.set_level(-0.5)
    assert waveform.audio_level == 0.0

    waveform.set_level(1.5)
    assert waveform.audio_level == 1.0

    waveform.set_level(0.8)
    assert waveform.audio_level == 0.8

    # Exponential decay physics step
    waveform._target_level = 1.0
    waveform._smoothed_level = 0.0
    waveform._on_anim_frame()
    # 0.0 + (1.0 - 0.0) * 0.25 = 0.25
    assert abs(waveform._smoothed_level - 0.25) < 1e-5


def test_waveform_timer_lifecycle_by_state(qapp):
    """Verify animation timer starts in listening/transcribing and stops in pasted/error/idle."""
    waveform = WaveformWidget()

    waveform.set_state("listening")
    assert waveform._anim_timer.isActive()

    waveform.set_state("transcribing")
    assert waveform._anim_timer.isActive()

    waveform.set_state("pasted")
    assert not waveform._anim_timer.isActive()

    waveform.set_state("error")
    assert not waveform._anim_timer.isActive()

    waveform.set_state("idle")
    assert not waveform._anim_timer.isActive()


def test_update_audio_level_routing(qapp):
    """Verify update_audio_level routes to waveform only in LISTENING state."""
    overlay = OverlayWidget()

    overlay.set_state("listening")
    overlay.update_audio_level(0.72)
    assert overlay.waveform.audio_level == 0.72

    overlay.set_state("transcribing")
    overlay.update_audio_level(0.99)
    # Target level reset to 0.0 on state change to transcribing
    assert overlay.waveform.audio_level == 0.0


def test_auto_hide_timer_arm_and_fade_out(qapp):
    """Verify auto-hide timer is armed on PASTED (1500ms) and ERROR (3000ms), triggering opacity fade-out animation."""
    overlay = OverlayWidget()

    # Pasted state arms timer with 1500ms interval
    overlay.set_state("pasted", "Pasted")
    assert overlay._auto_hide_timer.isActive()
    assert overlay._auto_hide_timer.interval() == 1500

    # Error state arms timer with 3000ms interval
    overlay.set_state("error", "Error")
    assert overlay._auto_hide_timer.isActive()
    assert overlay._auto_hide_timer.interval() == 3000

    # Fade animation setup check
    assert overlay._fade_anim.duration() == 300

    # Trigger auto-hide timeout
    overlay._auto_hide_timer.timeout.emit()
    assert overlay._fade_anim.state() == QAbstractAnimation.State.Running

    # Emulate fade animation completion
    closed_emitted = []
    overlay.closed.connect(lambda: closed_emitted.append(True))
    overlay._on_fade_out_finished()

    assert not overlay.isVisible()
    assert overlay.windowOpacity() == 1.0
    assert len(closed_emitted) == 1


def test_interruption_protection(qapp):
    """Verify setting state to LISTENING cancels active auto-hide timer and fade animation."""
    overlay = OverlayWidget()

    overlay.set_state("pasted", "Pasted")
    assert overlay._auto_hide_timer.isActive()

    # Start fade animation manually
    overlay._start_fade_out()
    assert overlay._fade_anim.state() == QAbstractAnimation.State.Running

    # Interrupt with new dictation key press (LISTENING state)
    overlay.set_state("listening", "Listening...")

    assert not overlay._auto_hide_timer.isActive()
    assert overlay._fade_anim.state() == QAbstractAnimation.State.Stopped
    assert overlay.windowOpacity() == 1.0
    assert overlay.isVisible()


def test_screen_positioning(qapp):
    """Verify screen positioning calculations for top_center and bottom_center."""
    overlay = OverlayWidget()
    overlay.center_top_position()
    assert overlay._screen_position == "top_center"
    assert overlay._margin_y == 40
    assert overlay.x() >= 0
    assert overlay.y() >= 0

    overlay.center_bottom_position()
    assert overlay._screen_position == "bottom_center"
    assert overlay._margin_y == 100
    assert overlay.x() >= 0
    assert overlay.y() >= 0


def test_waveform_phase_stepping(qapp):
    """Verify WaveformWidget phase advances by 0.15 on each animation frame."""
    waveform = WaveformWidget()
    initial_phase = waveform._phase
    waveform._on_anim_frame()
    assert abs(waveform._phase - (initial_phase + 0.15)) < 1e-5


def test_overlay_paint_event(qapp):
    """Verify glassmorphism background painting completes cleanly without exceptions."""
    overlay = OverlayWidget()
    for state in ["listening", "transcribing", "pasted", "error", "idle"]:
        overlay.set_state(state)
        pixmap = QPixmap(overlay.size())
        overlay.render(pixmap)
        assert not pixmap.isNull()

