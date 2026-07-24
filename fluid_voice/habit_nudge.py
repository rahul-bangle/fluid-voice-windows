"""
fluid_voice.habit_nudge: Habit-Breaking Voice Typing Nudge Engine for VeloVoice.

Monitors manual physical keyboard typing. When a user presses > 5 consecutive keys,
triggers a single non-intrusive reminder toast: "💡 Break the habit! Press Alt+S for voice typing".

Enforces strict zero-spam rules:
- Displays ONLY ONCE per typing session.
- Suppressed while user continues manual typing.
- Resets ONLY after user presses Alt+S voice dictation.
"""

import time
import logging
import threading
from typing import Callable, Optional, Any

logger = logging.getLogger(__name__)

try:
    from pynput import keyboard
    HAS_PYNPUT = True
except ImportError:
    keyboard = None
    HAS_PYNPUT = False


def _on_pynput_key_press(key: Any) -> None:
    """Module-level callback compatible with pynput in Python 3.14."""
    if HabitNudgeEngine._active_instance:
        HabitNudgeEngine._active_instance._on_key_press(key)


class HabitNudgeEngine:
    """
    Monitors physical keyboard presses and triggers a single voice nudge toast
    when > 5 manual keys are typed without voice dictation.
    """

    _active_instance: Optional["HabitNudgeEngine"] = None

    def __init__(
        self,
        key_threshold: int = 5,
        time_window_sec: float = 4.0,
        on_nudge_trigger: Optional[Callable[[], None]] = None,
        is_pasting_check: Optional[Callable[[], bool]] = None,
    ):
        self.key_threshold = key_threshold
        self.time_window_sec = time_window_sec
        self.on_nudge_trigger = on_nudge_trigger
        self.is_pasting_check = is_pasting_check

        self._key_count = 0
        self._last_key_time = 0.0
        self._nudge_shown = False
        self._listener: Optional[Any] = None
        self._lock = threading.Lock()
        HabitNudgeEngine._active_instance = self

    def start(self) -> bool:
        """Starts background keyboard listener for manual typing detection."""
        if not HAS_PYNPUT or not keyboard:
            logger.info("pynput not available; HabitNudgeEngine inactive.")
            return False

        if self._listener is not None:
            return True

        try:
            self._listener = keyboard.Listener(on_press=_on_pynput_key_press)
            self._listener.daemon = True
            self._listener.start()
            logger.info("HabitNudgeEngine started (threshold: >5 keys).")
            return True
        except Exception as e:
            logger.warning(f"Failed to start HabitNudgeEngine: {e}")
            return False

    def stop(self) -> None:
        """Stops background keyboard listener."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def reset_nudge_state(self) -> None:
        """
        Resets nudge state after user activates Alt+S voice dictation.
        Allows the nudge to trigger ONCE more during the next manual typing run.
        """
        with self._lock:
            self._key_count = 0
            self._nudge_shown = False
            logger.debug("[HABIT NUDGE] Nudge state reset after Alt+S voice dictation.")

    def _on_key_press(self, key: Any) -> None:
        """Internal callback on physical keyboard key press."""
        with self._lock:
            if self.is_pasting_check:
                try:
                    if self.is_pasting_check():
                        return
                except Exception:
                    pass
            # Ignore shortcut hotkeys when modifier keys (Alt, Ctrl, Win) are held down
            import sys
            if sys.platform == "win32":
                import ctypes
                user32 = ctypes.windll.user32
                is_alt = bool(user32.GetKeyState(0x12) & 0x8000)
                is_ctrl = bool(user32.GetKeyState(0x11) & 0x8000)
                is_win = bool(user32.GetKeyState(0x5B) & 0x8000) or bool(user32.GetKeyState(0x5C) & 0x8000)
                if is_alt or is_ctrl or is_win:
                    return

            # Ignore modifier keys (Alt, Ctrl, Shift, Super)
            key_str = str(key).lower()
            if any(mod in key_str for mod in ["alt", "ctrl", "shift", "cmd", "win", "caps_lock", "tab"]):
                return

            now = time.time()
            if now - self._last_key_time > self.time_window_sec:
                self._key_count = 0

            self._last_key_time = now
            self._key_count += 1

            if self._key_count >= self.key_threshold and not self._nudge_shown:
                self._nudge_shown = True
                logger.info(f"[HABIT NUDGE] Triggered (> {self.key_threshold} manual keys typed).")
                if self.on_nudge_trigger:
                    try:
                        self.on_nudge_trigger()
                    except Exception as e:
                        logger.error(f"Error in nudge trigger callback: {e}")
