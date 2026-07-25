"""
Unit tests for Settings GUI Dialog (fluid_voice.ui.settings).
Tier 1: Feature Coverage (Happy Path)
Tier 2: Boundary and Corner Cases
"""

import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit, QDialog

from fluid_voice.config import ConfigManager
from fluid_voice.ui.settings import SettingsDialog


# ============================================================================
# Tier 1: Core Functionality Tests
# ============================================================================

def test_settings_dialog_initialization(qapp, tmp_path):
    """Tier 1: Verifies initial dialog title, size, and component defaults."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    assert dialog.windowTitle() == "FluidVoice - Settings & Preferences"
    assert dialog.width() == 480
    assert dialog.height() == 480
    assert dialog.api_key_input.text() == ""
    assert dialog.hotkey_combo.currentText() == "Alt+S"
    assert dialog.auto_paste_checkbox.isChecked() is True
    assert dialog.autostart_checkbox.isChecked() is False


def test_settings_dialog_loads_existing_config(qapp, tmp_path):
    """Tier 1: Verifies dialog populates fields from existing ConfigManager values."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    config_mgr.set_api_key("gsk_existing_test_key_12345")
    config_mgr.update(hotkey="Alt+S", auto_paste=False, start_with_windows=True)

    dialog = SettingsDialog(config_manager=config_mgr)

    assert dialog.api_key_input.text() == "gsk_existing_test_key_12345"
    assert dialog.hotkey_combo.currentText() == "Alt+S"
    assert dialog.auto_paste_checkbox.isChecked() is False
    assert dialog.autostart_checkbox.isChecked() is True


def test_settings_dialog_api_key_validation_valid_format(qapp, tmp_path):
    """Tier 1: Verifies validate_api_key returns True for valid gsk_ prefix key."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    dialog.api_key_input.setText("gsk_valid_groq_api_key_token_999")
    with patch("fluid_voice.ui.settings.ApiValidationThread.start"):
        valid = dialog.validate_api_key()
        assert valid is True
        assert "✅" in dialog.api_status_label.text()


def test_settings_dialog_hotkey_selection_change(qapp, tmp_path):
    """Tier 1: Verifies changing hotkey combo dropdown selection."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    dialog.hotkey_combo.setCurrentText("Ctrl+Shift+V")
    assert dialog.hotkey_combo.currentText() == "Ctrl+Shift+V"


def test_settings_dialog_save_settings_emits_signal_and_updates_config(qapp, tmp_path):
    """Tier 1: Verifies clicking Save emits settings_saved signal and updates ConfigManager."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    saved_data = []
    dialog.settings_saved.connect(lambda d: saved_data.append(d))

    dialog.api_key_input.setText("gsk_new_saved_key_777")
    dialog.hotkey_combo.setCurrentText("F9")
    dialog.auto_paste_checkbox.setChecked(False)
    dialog.autostart_checkbox.setChecked(True)

    with patch("fluid_voice.ui.settings.set_autostart_registry"):
        dialog.save_settings()

    assert len(saved_data) == 1
    assert saved_data[0]["groq_api_key"] == "gsk_new_saved_key_777"
    assert saved_data[0]["hotkey"] == "F9"
    assert saved_data[0]["auto_paste"] is False

    # Check ConfigManager state
    assert config_mgr.get_api_key() == "gsk_new_saved_key_777"
    assert config_mgr.data.hotkey == "F9"
    assert config_mgr.data.auto_paste is False
    assert config_mgr.data.start_with_windows is True


def test_settings_dialog_toggle_api_key_visibility(qapp, tmp_path):
    """Tier 1: Verifies toggling password echo mode between Password and Normal."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    assert dialog.api_key_input.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.toggle_key_btn.text() == "Show"

    # Click toggle button
    dialog.toggle_key_btn.click()
    assert dialog.api_key_input.echoMode() == QLineEdit.EchoMode.Normal
    assert dialog.toggle_key_btn.text() == "Hide"

    # Click toggle button again
    dialog.toggle_key_btn.click()
    assert dialog.api_key_input.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.toggle_key_btn.text() == "Show"


# ============================================================================
# Tier 2: Boundary, Corner & Stress Tests
# ============================================================================

def test_settings_dialog_empty_api_key_warning(qapp, tmp_path):
    """Tier 2: Verifies missing API key displays warning label upon initialization."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    assert "Warning" in dialog.api_status_label.text()
    assert "orange" in dialog.api_status_label.styleSheet()


def test_settings_dialog_api_key_validation_empty_input(qapp, tmp_path):
    """Tier 2: Verifies validate_api_key fails on empty string."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    dialog.api_key_input.setText("")
    valid = dialog.validate_api_key()

    assert valid is False
    assert "cannot be empty" in dialog.api_status_label.text()


def test_settings_dialog_test_audio_capture_handler(qapp, tmp_path):
    """Tier 2: Verifies test_audio_capture queries devices and updates status label."""
    import fluid_voice.audio
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    mock_devices = [{"id": 0, "name": "Default Microphone", "max_input_channels": 1}]
    with patch("fluid_voice.audio.AudioRecorder.get_audio_devices", return_value=mock_devices):
        dialog.test_audio_capture()
        assert "Found 1 audio input device(s)" in dialog.audio_status_label.text()


def test_settings_dialog_cancel_button_rejects_without_saving(qapp, tmp_path):
    """Tier 2: Verifies clicking Cancel rejects dialog without updating ConfigManager."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    config_mgr.update(hotkey="Win+Space")

    dialog = SettingsDialog(config_manager=config_mgr)
    dialog.hotkey_combo.setCurrentText("Alt+S")

    dialog.cancel_btn.click()

    # ConfigManager should remain unchanged
    assert config_mgr.data.hotkey == "Win+Space"


def test_settings_dialog_custom_unlisted_hotkey_preservation(qapp, tmp_path):
    """Tier 2: Verifies loading a custom hotkey not in default dropdown list adds it."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    config_mgr.update(hotkey="Ctrl+Alt+Super+X")

    dialog = SettingsDialog(config_manager=config_mgr)
    assert dialog.hotkey_combo.currentText() == "Ctrl+Alt+Super+X"
