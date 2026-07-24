"""
Unit tests for AutoPaster Engine (fluid_voice.paster).
Tier 1: Feature Coverage (Happy Path)
Tier 2: Boundary and Corner Cases
"""

import pytest
from unittest.mock import MagicMock, patch

from fluid_voice.paster import AutoPaster


# ============================================================================
# Tier 1: Core Functionality Tests
# ============================================================================

def test_paster_initialization(qapp):
    """Tier 1: Verifies AutoPaster default configuration parameters."""
    paster = AutoPaster()
    assert paster.delay_after_paste == 0.01
    assert paster.restore_clipboard_delay == 0.05


def test_paster_get_active_window(qapp):
    """Tier 1: Verifies active window handle and title detection via get_active_window."""
    paster = AutoPaster()

    with patch("win32gui.GetForegroundWindow", return_value=0x12345), \
         patch("win32gui.GetWindowText", return_value="VS Code - app.py"):
        hwnd, title = paster.get_active_window()
        assert hwnd == 0x12345
        assert title == "VS Code - app.py"


def test_paster_get_and_set_clipboard_text(qapp):
    """Tier 1: Verifies setting and getting text from system clipboard using QApplication fixture."""
    paster = AutoPaster()

    success = paster.set_clipboard_text("Test Clipboard Content 123")
    assert success is True

    text = paster.get_clipboard_text()
    assert text == "Test Clipboard Content 123"


def test_paster_inject_paste_keys(qapp):
    """Tier 1: Verifies inject_paste_keys triggers keybd_event or pyautogui or pynput."""
    paster = AutoPaster()

    mock_win32api = MagicMock()
    with patch("fluid_voice.paster.win32api", mock_win32api), \
         patch("fluid_voice.paster.HAS_WIN32", True):
        result = paster.inject_paste_keys()
        assert result is True
        assert mock_win32api.keybd_event.call_count == 4


def test_paster_full_paste_text_pipeline_success(qapp):
    """Tier 1: Verifies complete paste_text workflow with clipboard backup and restore."""
    paster = AutoPaster(delay_after_paste=0.001)

    paster.set_clipboard_text("Original Clipboard Text")

    with patch.object(paster, "inject_paste_keys", return_value=True) as mock_inject:
        success = paster.paste_text("Bhai meeting prepone kar do")
        assert success is True
        mock_inject.assert_called_once()

    # Original clipboard text must be restored after paste
    assert paster.get_clipboard_text() == "Original Clipboard Text"


def test_paster_special_unicode_character_pasting(qapp):
    """Tier 1: Verifies setting special unicode/Hindi/Emoji characters to clipboard and pasting."""
    paster = AutoPaster(delay_after_paste=0.001)

    unicode_text = "Bhai, meeting 3:00 PM ko shift ho gayi hai! 🚀 Namaste 🙏 (रु 15,00,000)"

    with patch.object(paster, "inject_paste_keys", return_value=True):
        success = paster.paste_text(unicode_text)
        assert success is True


def test_paster_simulated_typing_fallback(qapp):
    """Tier 1: Verifies type_text fallback simulates individual key input."""
    paster = AutoPaster()

    mock_pyautogui = MagicMock()
    with patch("fluid_voice.paster.pyautogui", mock_pyautogui), \
         patch("fluid_voice.paster.HAS_PYAUTOGUI", True):
        res = paster.type_text("Hello World", wpm=120)
        assert res is True
        mock_pyautogui.typewrite.assert_called_once()


# ============================================================================
# Tier 2: Boundary, Corner & Stress Tests
# ============================================================================

def test_paster_empty_text_handling(qapp):
    """Tier 2: Verifies passing empty string returns False without altering clipboard or injecting keys."""
    paster = AutoPaster()
    paster.set_clipboard_text("Do Not Touch Clipboard")

    with patch.object(paster, "inject_paste_keys") as mock_inject:
        assert paster.paste_text("") is False
        assert paster.paste_text("    ") is False
        assert paster.paste_text(None) is False
        mock_inject.assert_not_called()

    assert paster.get_clipboard_text() == "Do Not Touch Clipboard"


def test_paster_window_focus_restoration_valid_hwnd(qapp):
    """Tier 2: Verifies restore_active_window calls Win32 SetForegroundWindow for valid hwnd."""
    paster = AutoPaster()

    mock_win32gui = MagicMock()
    mock_win32gui.GetForegroundWindow.return_value = 0x11111
    with patch("fluid_voice.paster.win32gui", mock_win32gui):
        success = paster.restore_active_window(0x99999)
        assert success is True
        mock_win32gui.SetForegroundWindow.assert_called_with(0x99999)


def test_paster_window_focus_null_handle_recovery(qapp):
    """Tier 2: Verifies restore_active_window handles null/0 hwnd handle gracefully without error."""
    paster = AutoPaster()
    assert paster.restore_active_window(0) is False
    assert paster.restore_active_window(None) is False


def test_paster_key_injection_failure_recovery(qapp):
    """Tier 2: Verifies key injection failure is caught and returns False cleanly."""
    paster = AutoPaster(delay_after_paste=0.001)

    with patch.object(paster, "inject_paste_keys", return_value=False):
        success = paster.paste_text("Some text")
        assert success is False


def test_paster_win32_clipboard_fallback_when_qapp_absent(tmp_path):
    """Tier 2: Verifies win32clipboard fallback execution path when QApplication is not active."""
    paster = AutoPaster()

    mock_win32cb = MagicMock()
    mock_win32cb.IsClipboardFormatAvailable.return_value = True
    mock_win32cb.GetClipboardData.return_value = "Win32 Clipboard Fallback Data"
    mock_win32con = MagicMock()
    mock_win32con.CF_UNICODETEXT = 13

    with patch("PyQt6.QtWidgets.QApplication.instance", return_value=None), \
         patch("fluid_voice.paster.win32clipboard", mock_win32cb), \
         patch("fluid_voice.paster.win32con", mock_win32con), \
         patch("fluid_voice.paster.HAS_WIN32", True):

        cb_text = paster.get_clipboard_text()
        assert cb_text == "Win32 Clipboard Fallback Data"


def test_paster_win32_action_executor_120ms_delay(qapp):
    """R3: Verifies paste_text_and_execute_action sleeps 120ms (time.sleep(0.120)) and fires VK_RETURN (0x0D)."""
    from fluid_voice.paster import paste_text_and_execute_action, AutoPaster

    paster = AutoPaster()
    sleep_calls = []

    with patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)), \
         patch.object(paster, "paste_text", return_value=True) as mock_paste, \
         patch.object(paster, "execute_action", return_value=True) as mock_exec:

        res = paster.paste_text_and_execute_action("hello world", action="VK_RETURN")
        assert res is True
        mock_paste.assert_called_once_with("hello world", target_hwnd=None)
        assert 0.120 in sleep_calls
        mock_exec.assert_called_once_with("VK_RETURN")

    with patch("time.sleep"), \
         patch.object(AutoPaster, "paste_text_and_execute_action", return_value=True) as mock_wrapper:
        res2 = paste_text_and_execute_action("submit", action="VK_RETURN")
        assert res2 is True
        mock_wrapper.assert_called_once_with("submit", action="VK_RETURN", target_hwnd=None)

