"""
Unit tests for Settings GUI Dialog & Autostart Registry (fluid_voice.ui.settings).
"""

import sys
import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit, QDialog

from fluid_voice.config import ConfigManager
from fluid_voice.ui.settings import SettingsDialog, ApiValidationThread, set_autostart_registry


# ============================================================================
# Core Settings GUI Unit Tests
# ============================================================================

def test_settings_dialog_initialization(qapp, tmp_path):
    """Verifies initial dialog title, size, and component defaults."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    assert dialog.windowTitle() == "FluidVoice - Settings & Preferences"
    assert dialog.width() == 480
    assert dialog.height() == 480
    assert dialog.api_key_input.text() == ""
    assert dialog.hotkey_combo.currentText() == "Alt+S"
    assert dialog.vad_spin.value() == -40.0
    assert dialog.vad_slider.value() == -40
    assert dialog.vad_dur_spin.value() == 1.5
    assert dialog.auto_paste_checkbox.isChecked() is True
    assert dialog.autostart_checkbox.isChecked() is False


def test_settings_dialog_loads_existing_config(qapp, tmp_path):
    """Verifies dialog populates fields from existing ConfigManager values."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    config_mgr.set_api_key("gsk_existing_test_key_12345")
    config_mgr.update(
        hotkey="Alt+S",
        vad_silence_threshold_db=-30.0,
        vad_silence_duration_s=2.0,
        auto_paste=False,
        start_with_windows=True,
    )

    dialog = SettingsDialog(config_manager=config_mgr)

    assert dialog.api_key_input.text() == "gsk_existing_test_key_12345"
    assert dialog.hotkey_combo.currentText() == "Alt+S"
    assert dialog.vad_spin.value() == -30.0
    assert dialog.vad_slider.value() == -30
    assert dialog.vad_dur_spin.value() == 2.0
    assert dialog.auto_paste_checkbox.isChecked() is False
    assert dialog.autostart_checkbox.isChecked() is True


def test_settings_dialog_vad_slider_spinbox_synchronization(qapp, tmp_path):
    """Verifies VAD threshold slider and spinbox remain synchronized."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    dialog.vad_slider.setValue(-25)
    assert dialog.vad_spin.value() == -25.0

    dialog.vad_spin.setValue(-50.0)
    assert dialog.vad_slider.value() == -50


def test_settings_dialog_api_key_validation_format_check(qapp, tmp_path):
    """Verifies validate_api_key returns True for valid gsk_ prefix key and launches thread."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    dialog.api_key_input.setText("gsk_valid_groq_api_key_token_999")
    with patch.object(ApiValidationThread, "start") as mock_start:
        valid = dialog.validate_api_key()
        assert valid is True
        assert "✅" in dialog.api_status_label.text()
        mock_start.assert_called_once()


def test_settings_dialog_api_key_validation_empty_or_invalid(qapp, tmp_path):
    """Verifies validate_api_key returns False on empty or invalid format strings."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    # Empty key
    dialog.api_key_input.setText("")
    assert dialog.validate_api_key() is False
    assert "cannot be empty" in dialog.api_status_label.text()

    # Invalid prefix/length
    dialog.api_key_input.setText("short_key")
    assert dialog.validate_api_key() is False
    assert "warning" in dialog.api_status_label.text().lower()


def test_api_validation_thread_success(qapp):
    """Verifies ApiValidationThread emits success signal when HTTP GET returns 200."""
    thread = ApiValidationThread("gsk_mock_valid_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    results = []
    thread.finished_signal.connect(lambda valid, msg: results.append((valid, msg)))

    with patch("requests.get", return_value=mock_resp):
        thread.run()

    assert len(results) == 1
    assert results[0][0] is True
    assert "verified" in results[0][1].lower()


def test_api_validation_thread_unauthorized(qapp):
    """Verifies ApiValidationThread emits error signal when HTTP GET returns 401."""
    thread = ApiValidationThread("gsk_invalid_key")

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    results = []
    thread.finished_signal.connect(lambda valid, msg: results.append((valid, msg)))

    with patch("requests.get", return_value=mock_resp):
        thread.run()

    assert len(results) == 1
    assert results[0][0] is False
    assert "401" in results[0][1]


def test_settings_dialog_save_settings_emits_signal_and_updates_config(qapp, tmp_path):
    """Verifies clicking Save emits settings_saved signal and updates ConfigManager."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    saved_data = []
    dialog.settings_saved.connect(lambda d: saved_data.append(d))

    dialog.api_key_input.setText("gsk_new_saved_key_777")
    dialog.hotkey_combo.setCurrentText("F9")
    dialog.vad_spin.setValue(-35.0)
    dialog.vad_dur_spin.setValue(2.5)
    dialog.auto_paste_checkbox.setChecked(False)
    dialog.autostart_checkbox.setChecked(True)

    with patch("fluid_voice.ui.settings.set_autostart_registry") as mock_registry:
        dialog.save_settings()
        mock_registry.assert_called_once_with(True)

    assert len(saved_data) == 1
    assert saved_data[0]["groq_api_key"] == "gsk_new_saved_key_777"
    assert saved_data[0]["hotkey"] == "F9"
    assert saved_data[0]["vad_silence_threshold_db"] == -35.0
    assert saved_data[0]["vad_silence_duration_s"] == 2.5
    assert saved_data[0]["auto_paste"] is False
    assert saved_data[0]["start_with_windows"] is True

    # Check ConfigManager state
    assert config_mgr.get_api_key() == "gsk_new_saved_key_777"
    assert config_mgr.data.hotkey == "F9"
    assert config_mgr.data.vad_silence_threshold_db == -35.0
    assert config_mgr.data.vad_silence_duration_s == 2.5
    assert config_mgr.data.auto_paste is False
    assert config_mgr.data.start_with_windows is True


def test_set_autostart_registry_non_windows():
    """Verifies set_autostart_registry returns False safely on non-Windows platforms."""
    with patch("sys.platform", "linux"):
        result = set_autostart_registry(True)
        assert result is False


def test_set_autostart_registry_windows_enable_and_disable():
    """Verifies set_autostart_registry calls winreg OpenKey and SetValueEx/DeleteValue on Windows."""
    mock_winreg = MagicMock()
    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key

    with patch("sys.platform", "win32"), \
         patch.dict("sys.modules", {"winreg": mock_winreg}):

        # Enable autostart
        res1 = set_autostart_registry(True)
        assert res1 is True
        mock_winreg.SetValueEx.assert_called_once()

        # Disable autostart
        res2 = set_autostart_registry(False)
        assert res2 is True
        mock_winreg.DeleteValue.assert_called_once()


def test_settings_dialog_toggle_api_key_visibility(qapp, tmp_path):
    """Verifies toggling password echo mode between Password and Normal."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    assert dialog.api_key_input.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.toggle_key_btn.text() == "Show"

    dialog.toggle_key_btn.click()
    assert dialog.api_key_input.echoMode() == QLineEdit.EchoMode.Normal
    assert dialog.toggle_key_btn.text() == "Hide"

    dialog.toggle_key_btn.click()
    assert dialog.api_key_input.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.toggle_key_btn.text() == "Show"


def test_settings_dialog_test_audio_capture_handler(qapp, tmp_path):
    """Verifies test_audio_capture queries devices and updates status label."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    mock_devices = [{"id": 0, "name": "Default Microphone", "max_input_channels": 1}]
    with patch("fluid_voice.audio.AudioRecorder.get_audio_devices", return_value=mock_devices):
        dialog.test_audio_capture()
        assert "Found 1 audio input device(s)" in dialog.audio_status_label.text()
