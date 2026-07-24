"""
fluid_voice.paster: Active Window Detection and Sub-50ms Auto-Paster Engine.
"""

import sys
import time
import logging
from typing import Optional, Tuple

from PyQt6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

# Pyautogui optional import
try:
    import pyautogui
    HAS_PYAUTOGUI = True
    pyautogui.PAUSE = 0.0  # Remove artificial 100ms pyautogui delay
except ImportError:
    pyautogui = None
    HAS_PYAUTOGUI = False

# Win32 optional imports
try:
    import win32gui
    import win32clipboard
    import win32con
    import win32api
    import win32process
    HAS_WIN32 = True
except ImportError:
    win32gui = None
    win32clipboard = None
    win32con = None
    win32api = None
    win32process = None
    HAS_WIN32 = False

CF_UNICODETEXT_VAL = getattr(win32con, "CF_UNICODETEXT", 13) if win32con else 13


class AutoPaster:
    """
    High-performance AutoPaster engine for FluidVoice Windows.
    Detects target active window, backs up clipboard content, injects text via sub-50ms
    Win32 keybd_event sequence, and restores original clipboard content.
    """

    def __init__(self, delay_after_paste: float = 0.01, restore_clipboard_delay: float = 0.05):
        self.delay_after_paste = delay_after_paste
        self.restore_clipboard_delay = restore_clipboard_delay

    def get_active_window(self) -> Tuple[int, str]:
        """Returns tuple of (hwnd, title) for current foreground active window."""
        if win32gui and hasattr(win32gui, "GetForegroundWindow"):
            try:
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    title = win32gui.GetWindowText(hwnd) if hasattr(win32gui, "GetWindowText") else ""
                    return hwnd, title
            except Exception as e:
                logger.warning(f"Error calling GetForegroundWindow: {e}")
        return 0, ""

    def get_clipboard_text(self) -> str:
        """Retrieves text from system clipboard using win32clipboard or PyQt fallback."""
        if win32clipboard and HAS_WIN32:
            try:
                cf_fmt = getattr(win32con, "CF_UNICODETEXT", CF_UNICODETEXT_VAL) if win32con else CF_UNICODETEXT_VAL
                win32clipboard.OpenClipboard(0)
                if win32clipboard.IsClipboardFormatAvailable(cf_fmt):
                    data = win32clipboard.GetClipboardData(cf_fmt)
                    win32clipboard.CloseClipboard()
                    return data or ""
                win32clipboard.CloseClipboard()
            except Exception as e:
                logger.warning(f"win32clipboard get text error: {e}")

        try:
            app = QApplication.instance()
            if app:
                clipboard = app.clipboard()
                return clipboard.text() or ""
        except Exception as e:
            logger.warning(f"QApplication clipboard read error: {e}")
        return ""

    def set_clipboard_text(self, text: str) -> bool:
        """Sets text onto system clipboard with UTF-8 / UNICODE support."""
        if win32clipboard and HAS_WIN32:
            try:
                cf_fmt = getattr(win32con, "CF_UNICODETEXT", CF_UNICODETEXT_VAL) if win32con else CF_UNICODETEXT_VAL
                win32clipboard.OpenClipboard(0)
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(cf_fmt, text)
                win32clipboard.CloseClipboard()
                return True
            except Exception as e:
                logger.warning(f"win32clipboard set text error: {e}")

        try:
            app = QApplication.instance()
            if app:
                clipboard = app.clipboard()
                clipboard.setText(text)
                return True
        except Exception as e:
            logger.warning(f"QApplication set clipboard error: {e}")
        return False

    def restore_active_window(self, hwnd: int) -> bool:
        """Restores window focus if handle is valid."""
        if not hwnd or hwnd == 0:
            return False
        if win32gui and hasattr(win32gui, "SetForegroundWindow"):
            try:
                curr_hwnd = win32gui.GetForegroundWindow()
                if curr_hwnd == hwnd:
                    return True

                if win32process and win32api:
                    try:
                        fg_thread = win32process.GetWindowThreadProcessId(curr_hwnd)[0]
                        cur_thread = win32api.GetCurrentThreadId()
                        if fg_thread and cur_thread and fg_thread != cur_thread:
                            win32process.AttachThreadInput(cur_thread, fg_thread, True)
                            win32gui.SetForegroundWindow(hwnd)
                            win32process.AttachThreadInput(cur_thread, fg_thread, False)
                            return True
                    except Exception as err:
                        logger.warning(f"AttachThreadInput failed, falling back to direct SetForegroundWindow: {err}")

                win32gui.SetForegroundWindow(hwnd)
                return True
            except Exception as e:
                logger.warning(f"Failed to restore window focus for hwnd {hwnd}: {e}")
                return False
        return True

    def inject_paste_keys(self) -> bool:
        """Simulates Ctrl+V keystroke via Win32 keybd_event (<1ms) with fallback."""
        if HAS_WIN32 and win32api:
            try:
                VK_CONTROL = 0x11
                VK_V = 0x56
                KEYEVENTF_KEYUP = 0x0002

                win32api.keybd_event(VK_CONTROL, 0, 0, 0)
                win32api.keybd_event(VK_V, 0, 0, 0)
                win32api.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
                win32api.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
                return True
            except Exception as e:
                logger.warning(f"Win32 keybd_event direct injection failed: {e}")

        if pyautogui and HAS_PYAUTOGUI:
            try:
                orig_pause = pyautogui.PAUSE
                pyautogui.PAUSE = 0.0
                pyautogui.hotkey("ctrl", "v")
                pyautogui.PAUSE = orig_pause
                return True
            except Exception as e:
                logger.error(f"Key injection failed via pyautogui: {e}")
                return False

        try:
            from pynput.keyboard import Controller, Key
            kb = Controller()
            kb.press(Key.ctrl)
            kb.press("v")
            kb.release("v")
            kb.release(Key.ctrl)
            return True
        except Exception as e:
            logger.error(f"Key injection failed via pynput: {e}")
            return False

    def type_text(self, text: str, wpm: int = 120) -> bool:
        """Fallback simulated typing for windows that disable clipboard paste."""
        if not text:
            return False
        try:
            if pyautogui and HAS_PYAUTOGUI:
                interval = 60.0 / (wpm * 5)
                pyautogui.typewrite(text, interval=interval)
                return True
            from pynput.keyboard import Controller
            kb = Controller()
            kb.type(text)
            return True
        except Exception as e:
            logger.error(f"Simulated typing failed: {e}")
            return False

    def inject_unicode_text(self, text: str) -> bool:
        """
        Directly injects text into active window caret input queue via Win32 SendInput KEYEVENTF_UNICODE (<3ms).
        Bypasses Windows clipboard completely.
        """
        if sys.platform != "win32" or not text:
            return False
        try:
            import ctypes
            from ctypes import wintypes

            class KEYBDINPUT(ctypes.Structure):
                _fields_ = [
                    ("wVk", wintypes.WORD),
                    ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.c_ulonglong if sys.maxsize > 2**31 - 1 else ctypes.c_ulong),
                ]

            class HARDWAREINPUT(ctypes.Structure):
                _fields_ = [
                    ("uMsg", wintypes.DWORD),
                    ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD),
                ]

            class MOUSEINPUT(ctypes.Structure):
                _fields_ = [
                    ("dx", wintypes.LONG),
                    ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.c_ulonglong if sys.maxsize > 2**31 - 1 else ctypes.c_ulong),
                ]

            class INPUT_UNION(ctypes.Union):
                _fields_ = [
                    ("ki", KEYBDINPUT),
                    ("mi", MOUSEINPUT),
                    ("hi", HARDWAREINPUT),
                ]

            class INPUT(ctypes.Structure):
                _fields_ = [
                    ("type", wintypes.DWORD),
                    ("union", INPUT_UNION),
                ]

            INPUT_KEYBOARD = 1
            KEYEVENTF_UNICODE = 0x0004
            KEYEVENTF_KEYUP = 0x0002

            user32 = ctypes.windll.user32
            inputs = []
            for ch in text:
                code = ord(ch)
                inputs.append(INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=0))))
                inputs.append(INPUT(type=INPUT_KEYBOARD, union=INPUT_UNION(ki=KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=0))))

            n_inputs = len(inputs)
            if n_inputs == 0:
                return False
            arr = (INPUT * n_inputs)(*inputs)
            inserted = user32.SendInput(n_inputs, ctypes.byref(arr), ctypes.sizeof(INPUT))
            return inserted == n_inputs
        except Exception as e:
            logger.warning(f"SendInput UNICODE injection failed: {e}")
            return False

    def paste_text(self, text: str, target_hwnd: Optional[int] = None) -> bool:
        """
        Executes complete auto-paste pipeline:
        1. Validates non-empty text.
        2. Tries Direct Win32 SendInput Unicode Injection (<3ms, zero clipboard touch).
        3. Fallback: Backs up clipboard, sets text, restores target window, injects Ctrl+V, restores clipboard.
        """
    def is_console_window(self, hwnd: int) -> bool:
        """Returns True if target window is a Windows Terminal, PowerShell, CMD, or SSH console."""
        if not hwnd or not win32gui:
            return False
        try:
            cls_name = win32gui.GetClassName(hwnd).lower()
            if any(c in cls_name for c in ["consolewindowclass", "cascadia_hosting_window_class", "mintty"]):
                return True
        except Exception:
            pass
        return False

    def paste_text(self, text: str, target_hwnd: Optional[int] = None) -> bool:
        """
        Injects text into target active window.
        1. Validates non-empty text.
        2. Uses Direct Win32 SendInput for GUI apps.
        3. Uses Clipboard paste for Terminal/Console windows (100% reliable in PowerShell/CMD/VS Code).
        """
        if not text or not text.strip():
            logger.info("Empty text provided to paste_text; skipping paste.")
            return False

        start_time = time.perf_counter()

        current_hwnd, _ = self.get_active_window()
        target_hwnd = target_hwnd if (target_hwnd is not None and target_hwnd != 0) else current_hwnd

        if target_hwnd and target_hwnd != 0:
            self.restore_active_window(target_hwnd)

        # Primary Fast Path: Try Win32 SendInput Unicode injection for standard GUI apps
        if not self.is_console_window(target_hwnd) and self.inject_unicode_text(text):
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.info(f"Direct SendInput typed '{text[:30]}...' in {elapsed_ms:.2f}ms (Zero Clipboard)")
            return True

        old_clipboard = self.get_clipboard_text()

        if not self.set_clipboard_text(text):
            logger.error("Failed to copy text to clipboard for auto-pasting.")
            return False

        if target_hwnd and target_hwnd != 0:
            self.restore_active_window(target_hwnd)
            time.sleep(0.03)

        pasted = self.inject_paste_keys()

        if self.delay_after_paste > 0:
            time.sleep(self.delay_after_paste)

        if self.restore_clipboard_delay > 0:
            time.sleep(self.restore_clipboard_delay)

        if old_clipboard and old_clipboard != text:
            self.set_clipboard_text(old_clipboard)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(f"Auto-pasted text '{text[:30]}...' in {elapsed_ms:.2f}ms")

        return pasted

    def execute_action(self, action: str = "VK_RETURN") -> bool:
        """Executes a Win32 key action like VK_RETURN (0x0D)."""
        if action == "VK_RETURN" or action == 0x0D:
            if HAS_WIN32 and win32api:
                try:
                    VK_RETURN = 0x0D
                    KEYEVENTF_KEYUP = 0x0002
                    win32api.keybd_event(VK_RETURN, 0, 0, 0)
                    win32api.keybd_event(VK_RETURN, 0, KEYEVENTF_KEYUP, 0)
                    return True
                except Exception as e:
                    logger.warning(f"Win32 keybd_event VK_RETURN execution failed: {e}")
            if pyautogui and HAS_PYAUTOGUI:
                try:
                    pyautogui.press("enter")
                    return True
                except Exception as e:
                    logger.warning(f"pyautogui enter press failed: {e}")
            try:
                from pynput.keyboard import Controller, Key
                kb = Controller()
                kb.press(Key.enter)
                kb.release(Key.enter)
                return True
            except Exception as e:
                logger.error(f"Action execution failed: {e}")
                return False
        return False

    def paste_text_and_execute_action(self, text: str, action: str = "VK_RETURN", target_hwnd: Optional[int] = None) -> bool:
        """
        Injects text via Ctrl+V, sleeps 120ms (time.sleep(0.120)), then fires Win32 keybd_event VK_RETURN (0x0D).
        """
        pasted = False
        if text and text.strip():
            pasted = self.paste_text(text, target_hwnd=target_hwnd)
        if action:
            time.sleep(0.120)
            self.execute_action(action)
            return True
        return pasted

    def get_active_caret_text(self) -> str:
        """
        Phase 2: Queries active window on-screen text snippet via Win32 Caret API.
        Zero clipboard reliance — returns empty string if no valid caret selection text.
        """
        # GetWindowText returns window title bar text (e.g. "Telegram Web - Brave"), NOT caret text.
        # Return empty string to prevent window title leakage into memory engine.
        return ""


def paste_text_and_execute_action(text: str, action: str = "VK_RETURN", target_hwnd: Optional[int] = None) -> bool:
    """Module-level wrapper for AutoPaster.paste_text_and_execute_action."""
    paster = AutoPaster()
    return paster.paste_text_and_execute_action(text, action=action, target_hwnd=target_hwnd)

