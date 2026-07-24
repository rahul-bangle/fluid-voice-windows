"""
fluid_voice.ui.dashboard_window: Pixel-Perfect Desktop Application Window for Velo AI.

Loads the exact HTML mockups from Frontend/stitch_velovoice_desktop_dictation_system
directly into a full-window QWebEngineView with zero extra PyQt sidebars or layout distortions.
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Any

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QMessageBox

logger = logging.getLogger(__name__)

# Check QWebEngineView availability
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    QWebEngineView = None


class VeloVoiceDashboardWindow(QMainWindow):
    """
    Pixel-Perfect Desktop Window hosting Velo AI HTML Mockup Frontend.
    """

    def __init__(self, app_controller: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.app = app_controller
        self.frontend_dir = Path(__file__).resolve().parent.parent.parent / "Frontend" / "stitch_velovoice_desktop_dictation_system"
        
        self.setWindowTitle("Velo AI - Desktop Dashboard")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 680)
        self.setStyleSheet("background-color: #F7F9FB;")

        self._init_ui()

    def _init_ui(self) -> None:
        main_html = self.frontend_dir / "velo_ai_dashboard_light_mode" / "code.html"

        if HAS_WEBENGINE and main_html.exists():
            self.web_view = QWebEngineView(self)
            
            # Enable local content access and smooth rendering
            settings = self.web_view.page().settings()
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
            
            # Load main mockup HTML file directly
            self.web_view.setUrl(QUrl.fromLocalFile(str(main_html)))
            self.setCentralWidget(self.web_view)
            logger.info(f"Loaded pixel-perfect Velo AI HTML mockup from: {main_html}")
        else:
            logger.error(f"WebEngine or HTML mockup not found at {main_html}")
            fallback = QWidget(self)
            self.setCentralWidget(fallback)

    def load_page(self, page_name: str) -> None:
        """Loads a specific frontend page HTML file into the WebEngine view."""
        page_map = {
            "dashboard": "velo_ai_dashboard_light_mode",
            "insights": "velo_ai_insights_dashboard",
            "dictionary": "vocabulary_manager_light_mode",
            "settings": "settings_general",
            "account": "settings_account",
        }
        folder = page_map.get(page_name, "velo_ai_dashboard_light_mode")
        html_file = self.frontend_dir / folder / "code.html"
        if HAS_WEBENGINE and hasattr(self, "web_view") and html_file.exists():
            self.web_view.setUrl(QUrl.fromLocalFile(str(html_file)))

    def closeEvent(self, event) -> None:
        """Hides window to system tray when user clicks close (X)."""
        if getattr(self.app, "tray_icon", None):
            event.ignore()
            self.hide()
            logger.info("Velo AI Dashboard window hidden to System Tray.")
        else:
            event.accept()
