"""
Tier 1 Feature Verification Tests for Milestone 6:
Settings GUI Dialog (fluid_voice.ui.settings) and Auto-Paster Engine (fluid_voice.paster).
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from fluid_voice.config import ConfigManager
from fluid_voice.ui.settings import SettingsDialog, ApiValidationThread, set_autostart_registry
from fluid_voice.paster import AutoPaster


# ============================================================================
# Settings GUI Tier 1 Tests
# ============================================================================

def test_tier1_settings_dialog_full_save_flow(qapp, tmp_path):
    """Tier 1: Verifies end-to-end configuration load, modification, registry update, and save signal."""
    config_mgr = ConfigManager(config_dir=tmp_path)
    dialog = SettingsDialog(config_manager=config_mgr)

    emitted_dict = {}
    dialog.settings_saved.connect(lambda d: emitted_dict.update(d))

    dialog.api_key_input.setText("gsk_tier1_test_api_key_987654321")
    dialog.hotkey_combo.setCurrentText("Alt+S")
    dialog.vad_spin.setValue(-32.0)
    dialog.vad_dur_spin.setValue(2.0)
    dialog.auto_paste_checkbox.setChecked(True)
    dialog.autostart_checkbox.setChecked(True)

    with patch("fluid_voice.ui.settings.set_autostart_registry") as mock_reg:
        dialog.save_settings()
        mock_reg.assert_called_once_with(True)

    assert config_mgr.get_api_key() == "gsk_tier1_test_api_key_987654321"
    assert config_mgr.data.hotkey == "Alt+S"
    assert config_mgr.data.vad_silence_threshold_db == -32.0
    assert config_mgr.data.vad_silence_duration_s == 2.0
    assert config_mgr.data.auto_paste is True
    assert config_mgr.data.start_with_windows is True

    assert emitted_dict["groq_api_key"] == "gsk_tier1_test_api_key_987654321"
    assert emitted_dict["hotkey"] == "Alt+S"
    assert emitted_dict["vad_silence_threshold_db"] == -32.0
    assert emitted_dict["vad_silence_duration_s"] == 2.0


def test_tier1_api_validation_worker_flow(qapp):
    """Tier 1: Verifies ApiValidationThread HTTP validation worker signal handling."""
    thread = ApiValidationThread("gsk_valid_key_token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200

    received = []
    thread.finished_signal.connect(lambda valid, msg: received.append((valid, msg)))

    with patch("requests.get", return_value=mock_resp):
        thread.run()

    assert len(received) == 1
    assert received[0][0] is True
    assert "verified" in received[0][1].lower()


def test_tier1_autostart_registry_toggle():
    """Tier 1: Verifies Windows registry autostart handler set_autostart_registry."""
    mock_winreg = MagicMock()
    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key

    with patch("sys.platform", "win32"), \
         patch.dict("sys.modules", {"winreg": mock_winreg}):

        assert set_autostart_registry(True) is True
        mock_winreg.SetValueEx.assert_called_once()

        assert set_autostart_registry(False) is True
        mock_winreg.DeleteValue.assert_called_once()


# ============================================================================
# AutoPaster Engine Tier 1 Tests
# ============================================================================

def test_tier1_paster_sub_50ms_latency_budget(qapp):
    """Tier 1 Latency Budget: AutoPaster.paste_text execution must complete within 50ms."""
    paster = AutoPaster(delay_after_paste=0.005, restore_clipboard_delay=0.0)
    paster.set_clipboard_text("Existing Clipboard Data")

    dictation_text = "Bhai, meeting 3:00 PM ko shift ho gayi hai! Call me soon."

    with patch.object(paster, "inject_paste_keys", return_value=True):
        start_t = time.perf_counter()
        success = paster.paste_text(dictation_text)
        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        assert success is True
        assert elapsed_ms < 50.0, f"AutoPaster latency {elapsed_ms:.2f}ms exceeded 50.0ms budget!"

    assert paster.get_clipboard_text() == "Existing Clipboard Data"


def test_tier1_paster_unicode_hinglish_preservation(qapp):
    """Tier 1: Verifies UTF-8 Unicode, Devanagari Hindi, and currency symbols handling."""
    paster = AutoPaster(delay_after_paste=0.001)

    hinglish_text = "Hinglish test: ₹ 50,000 / dus lakh. Namaste 🙏"
    paster.set_clipboard_text("Pre-existing clipboard")

    with patch.object(paster, "inject_paste_keys", return_value=True):
        success = paster.paste_text(hinglish_text)
        assert success is True

    # Check clipboard backup restoration
    assert paster.get_clipboard_text() == "Pre-existing clipboard"


def test_tier1_paster_foreground_window_focus_restoration(qapp):
    """Tier 1: Verifies restore_active_window with AttachThreadInput for cross-thread focus restoration."""
    paster = AutoPaster()

    mock_win32gui = MagicMock()
    mock_win32gui.GetForegroundWindow.return_value = 0x1000
    mock_win32proc = MagicMock()
    mock_win32proc.GetWindowThreadProcessId.return_value = (2000, 100)
    mock_win32api = MagicMock()
    mock_win32api.GetCurrentThreadId.return_value = 3000

    with patch("fluid_voice.paster.win32gui", mock_win32gui), \
         patch("fluid_voice.paster.win32process", mock_win32proc), \
         patch("fluid_voice.paster.win32api", mock_win32api):

        success = paster.restore_active_window(0x2000)
        assert success is True
        mock_win32proc.AttachThreadInput.assert_any_call(3000, 2000, True)
        mock_win32gui.SetForegroundWindow.assert_called_with(0x2000)
        mock_win32proc.AttachThreadInput.assert_any_call(3000, 2000, False)
