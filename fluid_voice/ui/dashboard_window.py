"""
fluid_voice.ui.dashboard_window: Master VeloVoice Desktop Dashboard & Control Application.

Hosts all 5 primary frontend UI screens:
1. Dictation History Feed & Search
2. Insights & Latency Analytics
3. Personal Vocabulary & Phonetic Dictionary Manager
4. General Settings & Hotkey Configurator
5. Account & API Key Management

Supports QWebEngineView for rich HTML frontend rendering + QWebChannel IPC bridge.
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Any

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QPushButton,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QLineEdit,
    QFormLayout,
    QHeaderView,
    QMessageBox,
)
from PyQt6.QtGui import QFont, QIcon, QColor

logger = logging.getLogger(__name__)

# Check QWebEngineView availability
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebChannel import QWebChannel
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False
    QWebEngineView = None
    QWebChannel = None


class VeloVoiceDashboardWindow(QMainWindow):
    """
    Main VeloVoice Desktop Application Window.
    Provides single-instance control center for history, vocabulary, analytics, and settings.
    """

    def __init__(self, app_controller: Optional[Any] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.app = app_controller
        self.frontend_dir = Path(__file__).resolve().parent.parent.parent / "Frontend" / "stitch_velovoice_desktop_dictation_system"
        
        self.setWindowTitle("VeloVoice — AI Dictation OS")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)
        
        self._init_ui()

    def _init_ui(self) -> None:
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar Navigation Rail (Fixed 240px)
        sidebar = self._build_sidebar()
        main_layout.addWidget(sidebar)

        # 2. Main Content Area Stack
        self.content_stack = QStackedWidget(self)
        main_layout.addWidget(self.content_stack, stretch=1)

        # Build view pages
        self.view_dashboard = self._build_web_or_native_page("velo_ai_dashboard_light_mode", "History Feed")
        self.view_insights = self._build_web_or_native_page("velo_ai_insights_dashboard", "Analytics & Speed")
        self.view_vocab = self._build_web_or_native_page("vocabulary_manager_light_mode", "Personal Vocabulary")
        self.view_settings = self._build_web_or_native_page("settings_general", "General Settings")
        self.view_account = self._build_web_or_native_page("settings_account", "Account & API Keys")

        self.content_stack.addWidget(self.view_dashboard)
        self.content_stack.addWidget(self.view_insights)
        self.content_stack.addWidget(self.view_vocab)
        self.content_stack.addWidget(self.view_settings)
        self.content_stack.addWidget(self.view_account)

        # Set default dark corporate styling
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #0D0D11;
                color: #E2E8F0;
                font-family: 'Segoe UI', Inter, sans-serif;
            }
            QPushButton {
                background-color: #16161E;
                color: #94A3B8;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 600;
                text-align: left;
            }
            QPushButton:hover {
                background-color: #1F1F2B;
                color: #FFFFFF;
            }
            QPushButton:checked {
                background-color: #004AC6;
                color: #FFFFFF;
            }
        """)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget(self)
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("background-color: #121218; border-right: 1px solid #1F1F2B;")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(8)

        # Brand Title
        brand_lbl = QLabel("⚡ VeloVoice OS", sidebar)
        brand_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        brand_lbl.setStyleSheet("color: #FFFFFF; margin-bottom: 20px;")
        layout.addWidget(brand_lbl)

        # Navigation Buttons Group
        self.btn_history = QPushButton("📜 Dictation History", sidebar)
        self.btn_insights = QPushButton("📊 Speed & Insights", sidebar)
        self.btn_vocab = QPushButton("🔤 Personal Vocabulary", sidebar)
        self.btn_settings = QPushButton("⚙️ General Settings", sidebar)
        self.btn_account = QPushButton("🔑 Account & API Keys", sidebar)

        self.nav_btns = [self.btn_history, self.btn_insights, self.btn_vocab, self.btn_settings, self.btn_account]
        for i, btn in enumerate(self.nav_btns):
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self._switch_page(idx))
            layout.addWidget(btn)

        self.btn_history.setChecked(True)
        layout.addStretch(1)

        # Footer Status
        status_lbl = QLabel("Daemon: Active 🟢", sidebar)
        status_lbl.setStyleSheet("color: #10B981; font-size: 11px; font-weight: 600;")
        layout.addWidget(status_lbl)

        return sidebar

    def _switch_page(self, index: int) -> None:
        for i, btn in enumerate(self.nav_btns):
            btn.setChecked(i == index)
        self.content_stack.setCurrentIndex(index)

    def _build_web_or_native_page(self, folder_name: str, fallback_title: str) -> QWidget:
        html_file = self.frontend_dir / folder_name / "code.html"
        
        if HAS_WEBENGINE and html_file.exists():
            try:
                web_view = QWebEngineView(self)
                web_view.setUrl(QUrl.fromLocalFile(str(html_file)))
                return web_view
            except Exception as e:
                logger.warning(f"Could not load QWebEngineView for {folder_name}: {e}")

        # Native PyQt6 Fallback Panel
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel(f"⚡ {fallback_title}", panel)
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #FFFFFF;")
        layout.addWidget(title)

        info = QLabel(f"Local VeloVoice Desktop UI Screen ({folder_name})", panel)
        info.setStyleSheet("color: #94A3B8; font-size: 13px;")
        layout.addWidget(info)
        layout.addStretch(1)

        return panel

    def closeEvent(self, event) -> None:
        """Hides window to system tray instead of exiting process."""
        if getattr(self.app, "tray_icon", None):
            event.ignore()
            self.hide()
            logger.info("VeloVoice Dashboard window hidden to System Tray.")
        else:
            event.accept()
