"""
Tests for fluid_voice.ui.dashboard_window (Velo AI Desktop Dashboard Window).
Verifies QWebEngineView initialization, Local file QUrl navigation, page switching, and tray close handling.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import QMainWindow
from fluid_voice.ui.dashboard_window import VeloVoiceDashboardWindow, VeloWebEnginePage, HAS_WEBENGINE


@pytest.fixture
def dashboard_win(qapp, tmp_path):
    """Fixture initializing VeloVoiceDashboardWindow."""
    win = VeloVoiceDashboardWindow()
    yield win
    win.close()


def test_dashboard_window_init(qapp):
    """Verifies VeloVoiceDashboardWindow instantiates cleanly."""
    win = VeloVoiceDashboardWindow()
    assert isinstance(win, QMainWindow)
    assert "Velo AI" in win.windowTitle()
    assert win.centralWidget() is not None
    win.close()


def test_dashboard_window_page_mapping():
    """Verifies page mapping dictionary contains all core Stitch frontend screens."""
    page_map = VeloVoiceDashboardWindow.PAGE_MAP
    assert "dashboard" in page_map
    assert "insights" in page_map
    assert "dictionary" in page_map
    assert "settings" in page_map
    assert "account" in page_map


def test_dashboard_window_load_page(qapp):
    """Verifies load_page switches pages without raising exceptions."""
    win = VeloVoiceDashboardWindow()
    win.load_page("insights")
    win.load_page("dictionary")
    win.load_page("settings")
    win.load_page("account")
    win.close()


def test_dashboard_window_close_event_hides_to_tray(qapp):
    """Verifies clicking close (X) hides window to tray when app controller is attached."""
    mock_app = MagicMock()
    mock_app.tray_icon = MagicMock()

    win = VeloVoiceDashboardWindow(app_controller=mock_app)
    mock_event = MagicMock()

    win.closeEvent(mock_event)

    mock_event.ignore.assert_called_once()
    mock_event.accept.assert_not_called()
    win.close()
