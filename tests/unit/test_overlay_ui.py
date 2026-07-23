"""
Unit tests for Overlay UI Widget (fluid_voice.ui.overlay).
Tier 1: Feature Coverage (Happy Path)
Tier 2: Boundary and Corner Cases
"""

import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication

from fluid_voice.ui.overlay import OverlayWidget, WaveformVisualizer


# ============================================================================
# Tier 1: Core Functionality Tests
# ============================================================================

def test_overlay_ui_window_flags_and_attributes(qapp):
    """Tier 1: Verifies frameless glassmorphic widget flags and translucent background attribute."""
    overlay = OverlayWidget()
    flags = overlay.windowFlags()

    assert bool(flags & Qt.WindowType.FramelessWindowHint)
    assert bool(flags & Qt.WindowType.WindowStaysOnTopHint)
    assert bool(flags & Qt.WindowType.Tool)
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert overlay.width() == 280
    assert overlay.height() == 70


def test_overlay_ui_initial_state(qapp):
    """Tier 1: Verifies default state, message, and visible sub-widgets upon creation."""
    overlay = OverlayWidget()
    overlay.show()
    assert overlay.current_state == "listening"
    assert overlay.status_label.text() == "Listening..."
    assert not overlay.waveform.isHidden()


@pytest.mark.parametrize("state_name,expected_color", [
    ("listening", QColor(0, 210, 255, 220)),
    ("transcribing", QColor(255, 170, 0, 220)),
    ("pasted", QColor(50, 215, 75, 220)),
    ("error", QColor(255, 69, 58, 220)),
])
def test_overlay_ui_state_transitions_and_colors(qapp, state_name, expected_color):
    """Tier 1: Verifies state transitions update internal state and color mapping."""
    overlay = OverlayWidget()
    overlay.set_state(state_name, f"Status: {state_name}")

    assert overlay.current_state == state_name
    assert overlay.status_label.text() == f"Status: {state_name}"
    assert overlay.STATE_COLORS[state_name] == expected_color


def test_overlay_ui_state_changed_signal(qapp):
    """Tier 1: Verifies state_changed signal emission on set_state call."""
    overlay = OverlayWidget()
    emitted = []
    overlay.state_changed.connect(lambda st, msg: emitted.append((st, msg)))

    overlay.set_state("transcribing", "Processing speech...")

    assert len(emitted) == 1
    assert emitted[0] == ("transcribing", "Processing speech...")


def test_overlay_ui_waveform_audio_level_updates(qapp):
    """Tier 1: Verifies update_audio_level updates waveform level in listening state."""
    overlay = OverlayWidget()
    overlay.set_state("listening")

    overlay.update_audio_level(0.75)
    assert overlay.waveform.audio_level == 0.75

    # Should not update waveform audio level when in transcribing or pasted state
    overlay.set_state("pasted", "Text Pasted!")
    overlay.update_audio_level(0.99)
    assert overlay.waveform.audio_level == 0.0


def test_overlay_ui_center_bottom_positioning(qapp):
    """Tier 1: Verifies positioning calculation places widget near bottom-center of screen."""
    overlay = OverlayWidget()
    overlay.center_bottom_position()

    screen = QApplication.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        expected_x = geo.x() + (geo.width() - overlay.width()) // 2
        expected_y = geo.y() + geo.height() - overlay.height() - 100
        assert overlay.x() == expected_x
        assert overlay.y() == expected_y


# ============================================================================
# Tier 2: Boundary, Corner & Stress Tests
# ============================================================================

def test_overlay_ui_waveform_audio_level_clamping(qapp):
    """Tier 2: Verifies boundary clamping for waveform audio level inputs (<0 and >1)."""
    visualizer = WaveformVisualizer()

    # Negative level clamped to 0.0
    visualizer.set_level(-0.5)
    assert visualizer.audio_level == 0.0

    # Over 1.0 clamped to 1.0
    visualizer.set_level(2.5)
    assert visualizer.audio_level == 1.0


def test_overlay_ui_unknown_state_fallback(qapp):
    """Tier 2: Verifies unknown state strings fall back gracefully to 'listening'."""
    overlay = OverlayWidget()
    overlay.set_state("invalid_state_xyz", "Custom fallback msg")

    assert overlay.current_state == "listening"
    assert overlay.status_label.text() == "Custom fallback msg"


def test_overlay_ui_auto_hide_timer_for_pasted_and_error(qapp):
    """Tier 2: Verifies auto-hide timer is armed on 'pasted' and 'error' state transitions."""
    overlay = OverlayWidget()

    # Pasted arms auto-hide timer with 1500ms timeout
    overlay.set_state("pasted", "Pasted")
    assert overlay._auto_hide_timer.isActive()
    assert overlay._auto_hide_timer.interval() == 1500

    # Listening stops auto-hide timer
    overlay.set_state("listening", "Listening")
    assert not overlay._auto_hide_timer.isActive()

    # Error arms auto-hide timer with 3000ms timeout
    overlay.set_state("error", "Failed")
    assert overlay._auto_hide_timer.isActive()
    assert overlay._auto_hide_timer.interval() == 3000


def test_overlay_ui_rapid_state_toggling_stress(qapp):
    """Tier 2: Verifies widget stability under rapid sequential state toggles."""
    overlay = OverlayWidget()
    states = ["listening", "transcribing", "pasted", "error", "listening", "pasted"]

    for st in states:
        overlay.set_state(st, f"Rapid state: {st}")
        assert overlay.current_state == st

    assert overlay.isVisible()


def test_overlay_ui_paint_event_execution(qapp):
    """Tier 2: Verifies paintEvent executes without raising errors."""
    overlay = OverlayWidget()
    overlay.set_state("listening", "Paint Test")
    pixmap = QPixmap(overlay.size())
    overlay.render(pixmap)
    assert not pixmap.isNull()
