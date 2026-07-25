"""
fluid_voice.ui.settings: Settings GUI Configuration Dialog for FluidVoice Windows.
"""

import sys
import logging
from typing import Optional

import requests
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QCheckBox,
    QGroupBox,
    QSlider,
    QDoubleSpinBox,
    QWidget,
)

from fluid_voice.config import ConfigManager

logger = logging.getLogger(__name__)


def set_autostart_registry(enable: bool) -> bool:
    """Sets or deletes the FluidVoice Windows startup registry key (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)."""
    if sys.platform != "win32":
        logger.info("Registry autostart setting ignored on non-win32 platform.")
        return False
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "FluidVoice"

        if getattr(sys, "frozen", False):
            exe_path = f'"{sys.executable}"'
        else:
            exe_path = f'"{sys.executable}" -m fluid_voice'

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
            if enable:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                logger.info(f"Added autostart registry key: {exe_path}")
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    logger.info("Removed autostart registry key")
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        logger.error(f"Failed to update autostart registry key: {e}")
        return False


class ApiValidationThread(QThread):
    """Background worker thread for validating Groq API key connectivity."""
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, api_key: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.api_key = api_key

    def run(self) -> None:
        url = "https://api.groq.com/openai/v1/models"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "FluidVoice-Windows/1.0",
        }
        try:
            resp = requests.get(url, headers=headers, timeout=4.0)
            if resp.status_code == 200:
                self.finished_signal.emit(True, "✅ Groq API Key verified with server.")
            elif resp.status_code == 401:
                self.finished_signal.emit(False, "❌ Invalid API Key (HTTP 401 Unauthorized).")
            elif resp.status_code == 429:
                self.finished_signal.emit(False, "⚠️ Rate limit reached, but API key format valid.")
            else:
                self.finished_signal.emit(False, f"❌ Groq API error (HTTP {resp.status_code}).")
        except requests.exceptions.Timeout:
            self.finished_signal.emit(False, "❌ Connection timed out after 4 seconds.")
        except Exception as e:
            self.finished_signal.emit(False, f"❌ Connection failed: {e}")


class SettingsDialog(QDialog):
    """
    Configuration and Setup Dialog for FluidVoice Windows.
    Enables API key management, live connectivity test, hotkey binding, VAD sensitivity tuning, and autostart.
    """

    settings_saved = pyqtSignal(dict)

    HOTKEY_OPTIONS = ["Alt+S", "Ctrl+Shift", "Ctrl+Alt", "Win+Space", "F9", "Ctrl+Shift+V"]

    def __init__(self, config_manager: Optional[ConfigManager] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config_manager = config_manager or ConfigManager()
        self.setWindowTitle("FluidVoice - Settings & Preferences")
        self.setFixedSize(480, 480)
        self.validation_thread: Optional[ApiValidationThread] = None

        self._init_ui()
        self.load_settings()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # 1. Groq API Key Group
        api_group = QGroupBox("Groq Whisper API Credentials", self)
        api_layout = QVBoxLayout(api_group)

        api_input_layout = QHBoxLayout()
        self.api_key_input = QLineEdit(self)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Enter Groq API Key (gsk_...)")

        self.toggle_key_btn = QPushButton("Show", self)
        self.toggle_key_btn.setFixedWidth(60)
        self.toggle_key_btn.clicked.connect(self._toggle_api_key_visibility)

        api_input_layout.addWidget(self.api_key_input)
        api_input_layout.addWidget(self.toggle_key_btn)
        api_layout.addLayout(api_input_layout)

        self.test_api_btn = QPushButton("Validate API Key", self)
        self.test_api_btn.clicked.connect(self.validate_api_key)
        api_layout.addWidget(self.test_api_btn)

        self.api_status_label = QLabel("", self)
        self.api_status_label.setStyleSheet("font-size: 11px;")
        api_layout.addWidget(self.api_status_label)

        main_layout.addWidget(api_group)

        # 2. Hotkey & Audio Controls Group
        hotkey_group = QGroupBox("Hotkeys & Audio Controls", self)
        hotkey_layout = QVBoxLayout(hotkey_group)

        # Hotkey selector
        hk_select_layout = QHBoxLayout()
        hk_label = QLabel("Global Dictation Hotkey:", self)
        self.hotkey_combo = QComboBox(self)
        self.hotkey_combo.addItems(self.HOTKEY_OPTIONS)
        hk_select_layout.addWidget(hk_label)
        hk_select_layout.addWidget(self.hotkey_combo)
        hotkey_layout.addLayout(hk_select_layout)

        # VAD Threshold Slider & Spinbox
        vad_layout = QHBoxLayout()
        vad_label = QLabel("VAD Silence Threshold:", self)
        self.vad_slider = QSlider(Qt.Orientation.Horizontal, self)
        self.vad_slider.setRange(-60, -10)
        self.vad_slider.setValue(-40)

        self.vad_spin = QDoubleSpinBox(self)
        self.vad_spin.setRange(-60.0, -10.0)
        self.vad_spin.setSuffix(" dB")
        self.vad_spin.setValue(-40.0)

        # Synchronize slider & spinbox
        self.vad_slider.valueChanged.connect(lambda v: self.vad_spin.setValue(float(v)))
        self.vad_spin.valueChanged.connect(lambda v: self.vad_slider.setValue(int(v)))

        vad_layout.addWidget(vad_label)
        vad_layout.addWidget(self.vad_slider)
        vad_layout.addWidget(self.vad_spin)
        hotkey_layout.addLayout(vad_layout)

        # Silence Auto-Stop Duration
        dur_layout = QHBoxLayout()
        dur_label = QLabel("Silence Auto-Stop Duration:", self)
        self.vad_dur_spin = QDoubleSpinBox(self)
        self.vad_dur_spin.setRange(0.5, 5.0)
        self.vad_dur_spin.setSingleStep(0.1)
        self.vad_dur_spin.setSuffix(" sec")
        self.vad_dur_spin.setValue(1.5)
        dur_layout.addWidget(dur_label)
        dur_layout.addWidget(self.vad_dur_spin)
        hotkey_layout.addLayout(dur_layout)

        self.test_audio_btn = QPushButton("Test Audio Capture", self)
        self.test_audio_btn.clicked.connect(self.test_audio_capture)
        hotkey_layout.addWidget(self.test_audio_btn)

        self.audio_status_label = QLabel("", self)
        self.audio_status_label.setStyleSheet("font-size: 11px;")
        hotkey_layout.addWidget(self.audio_status_label)

        main_layout.addWidget(hotkey_group)

        # 3. Preferences Group
        pref_group = QGroupBox("Preferences", self)
        pref_layout = QVBoxLayout(pref_group)

        self.auto_paste_checkbox = QCheckBox("Automatically paste transcribed text", self)
        pref_layout.addWidget(self.auto_paste_checkbox)

        self.autostart_checkbox = QCheckBox("Start with Windows", self)
        pref_layout.addWidget(self.autostart_checkbox)

        main_layout.addWidget(pref_group)

        # 4. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.save_btn = QPushButton("Save Settings", self)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.save_settings)

        self.cancel_btn = QPushButton("Cancel", self)
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(btn_layout)

    def load_settings(self) -> None:
        """Loads configuration fields into UI controls."""
        current_key = self.config_manager.get_api_key()
        self.api_key_input.setText(current_key)

        hotkey = self.config_manager.data.hotkey
        if hotkey in self.HOTKEY_OPTIONS:
            self.hotkey_combo.setCurrentText(hotkey)
        else:
            self.hotkey_combo.addItem(hotkey)
            self.hotkey_combo.setCurrentText(hotkey)

        vad_db = self.config_manager.data.vad_silence_threshold_db
        self.vad_spin.setValue(vad_db)
        self.vad_slider.setValue(int(vad_db))

        vad_dur = self.config_manager.data.vad_silence_duration_s
        self.vad_dur_spin.setValue(vad_dur)

        self.auto_paste_checkbox.setChecked(self.config_manager.data.auto_paste)
        self.autostart_checkbox.setChecked(self.config_manager.data.start_with_windows)

        if not current_key:
            self.api_status_label.setText("⚠️ Warning: No Groq API Key configured.")
            self.api_status_label.setStyleSheet("color: orange;")

    def _toggle_api_key_visibility(self) -> None:
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_key_btn.setText("Hide")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_key_btn.setText("Show")

    def validate_api_key(self) -> bool:
        """Validates API key format and launches non-blocking connectivity test worker."""
        key = self.api_key_input.text().strip()
        if not key:
            self.api_status_label.setText("❌ API key cannot be empty.")
            self.api_status_label.setStyleSheet("color: red;")
            return False

        if not key.startswith("gsk_") or len(key) < 15:
            self.api_status_label.setText("⚠️ API Key format warning (should start with gsk_).")
            self.api_status_label.setStyleSheet("color: orange;")
            return False

        self.api_status_label.setText("✅ API Key format valid. Testing connectivity...")
        self.api_status_label.setStyleSheet("color: green;")

        # Spawn background validation worker thread
        self.validation_thread = ApiValidationThread(key, self)
        self.validation_thread.finished_signal.connect(self._on_validation_finished)
        self.validation_thread.start()
        return True

    def _on_validation_finished(self, is_valid: bool, message: str) -> None:
        self.test_api_btn.setEnabled(True)
        self.api_status_label.setText(message)
        if is_valid:
            self.api_status_label.setStyleSheet("color: green;")
        else:
            self.api_status_label.setStyleSheet("color: red;")

    def test_audio_capture(self) -> None:
        """Queries sounddevice microphone devices."""
        try:
            from fluid_voice.audio import AudioRecorder
            recorder = AudioRecorder()
            devices = recorder.get_audio_devices()
            if devices:
                self.audio_status_label.setText(f"✅ Found {len(devices)} audio input device(s).")
                self.audio_status_label.setStyleSheet("color: green;")
            else:
                self.audio_status_label.setText("⚠️ No audio input devices found.")
                self.audio_status_label.setStyleSheet("color: orange;")
        except Exception as e:
            self.audio_status_label.setText(f"❌ Audio error: {e}")
            self.audio_status_label.setStyleSheet("color: red;")

    def save_settings(self) -> None:
        """Persists values to ConfigManager and Windows Registry, then accepts dialog."""
        key = self.api_key_input.text().strip()
        hotkey = self.hotkey_combo.currentText()
        vad_db = float(self.vad_spin.value())
        vad_dur = float(self.vad_dur_spin.value())
        auto_paste = self.auto_paste_checkbox.isChecked()
        autostart = self.autostart_checkbox.isChecked()

        self.config_manager.set_api_key(key)
        self.config_manager.update(
            hotkey=hotkey,
            vad_silence_threshold_db=vad_db,
            vad_silence_duration_s=vad_dur,
            auto_paste=auto_paste,
            start_with_windows=autostart,
        )

        # Update Windows Registry autostart key
        set_autostart_registry(autostart)

        settings_dict = {
            "groq_api_key": key,
            "hotkey": hotkey,
            "vad_silence_threshold_db": vad_db,
            "vad_silence_duration_s": vad_dur,
            "auto_paste": auto_paste,
            "start_with_windows": autostart,
        }

        self.settings_saved.emit(settings_dict)
        self.accept()
