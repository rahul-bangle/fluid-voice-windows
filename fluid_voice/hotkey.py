import ctypes
import logging
import sys
import threading
import time
from typing import Callable, Optional, Set
from pynput import keyboard

logger = logging.getLogger(__name__)

# Win32 Virtual Key Constants for rescue polling
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_SPACE = 0x20
VK_MENU = 0x12  # Alt key
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_CONTROL = 0x11
VK_LCONTROL = 0xA0
VK_RCONTROL = 0xA1
VK_SHIFT = 0x10
VK_LSHIFT = 0xA2
VK_RSHIFT = 0xA3


class HotkeyMode:
    PRESS_TO_TALK = "press_to_talk"
    TOGGLE = "toggle"


def _is_win32_key_down(vk_code: int) -> bool:
    """Queries Win32 GetGetAsyncKeyState to check physical key state."""
    if sys.platform != "win32":
        return True
    try:
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)
    except Exception:
        return True


def _get_vk_codes(key: keyboard.Key | keyboard.KeyCode) -> list[int]:
    if isinstance(key, keyboard.Key):
        if key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
            return [VK_LWIN, VK_RWIN]
        elif key in (keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            return [VK_MENU, VK_LMENU, VK_RMENU]
        elif key in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return [VK_CONTROL, VK_LCONTROL, VK_RCONTROL]
        elif key in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r):
            return [VK_SHIFT, VK_LSHIFT, VK_RSHIFT]
        elif key == keyboard.Key.space:
            return [VK_SPACE]
        elif key == keyboard.Key.enter:
            return [0x0D]
        elif key == keyboard.Key.tab:
            return [0x09]
        elif key == keyboard.Key.esc:
            return [0x1B]
    elif isinstance(key, keyboard.KeyCode):
        if key.vk is not None:
            return [key.vk]
        if key.char:
            return [ord(key.char.upper())]
    return []


def parse_hotkey_string(hotkey_str: str) -> Set[keyboard.Key | keyboard.KeyCode]:
    """
    Parses a hotkey string like 'Win+Space' or 'Alt+S' into a set of pynput Keys/KeyCodes.
    Raises ValueError if hotkey_str is invalid or empty.
    """
    if not hotkey_str or not isinstance(hotkey_str, str):
        raise ValueError(f"Invalid hotkey string: {hotkey_str}")

    parts = [p.strip() for p in hotkey_str.split("+") if p.strip()]
    if not parts:
        raise ValueError(f"Invalid hotkey string structure: {hotkey_str}")

    keys: Set[keyboard.Key | keyboard.KeyCode] = set()
    key_map = {
        "win": keyboard.Key.cmd,
        "cmd": keyboard.Key.cmd,
        "super": keyboard.Key.cmd,
        "alt": keyboard.Key.alt,
        "ctrl": keyboard.Key.ctrl,
        "control": keyboard.Key.ctrl,
        "shift": keyboard.Key.shift,
        "space": keyboard.Key.space,
        "enter": keyboard.Key.enter,
        "tab": keyboard.Key.tab,
        "esc": keyboard.Key.esc,
        "escape": keyboard.Key.esc,
    }

    for part in parts:
        lowered = part.lower()
        if lowered in key_map:
            keys.add(key_map[lowered])
        elif len(part) == 1:
            keys.add(keyboard.KeyCode.from_char(part.lower()))
        else:
            if hasattr(keyboard.Key, lowered):
                keys.add(getattr(keyboard.Key, lowered))
            else:
                raise ValueError(f"Unknown key in hotkey string: '{part}'")

    return keys


class HotkeyListener:
    """
    Global hotkey listener engine for FluidVoice.
    Manages press-to-talk keydown/keyup events and toggle events using pynput.
    Supports thread-safe start, stop, rebinding, rapid toggling debouncing,
    and Win32 GetGetAsyncKeyState key release rescue polling.
    """

    def __init__(
        self,
        hotkey_str: str = "Win+Space",
        on_keydown: Optional[Callable[[], None]] = None,
        on_keyup: Optional[Callable[[], None]] = None,
        on_toggle: Optional[Callable[[], None]] = None,
        debounce_ms: float = 50.0,
        mode: str = HotkeyMode.PRESS_TO_TALK,
    ):
        self._lock = threading.RLock()
        self.hotkey_str = hotkey_str
        self.on_keydown = on_keydown
        self.on_keyup = on_keyup
        self.on_toggle = on_toggle
        self.debounce_ms = debounce_ms
        self._mode = mode

        self._active_keys: Set[keyboard.Key | keyboard.KeyCode] = set()
        self._target_keys: Set[keyboard.Key | keyboard.KeyCode] = set()
        self._listener: Optional[keyboard.Listener] = None
        self._rescue_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._is_pressed = False
        self._last_toggle_time = 0.0

        self.rebind(hotkey_str)

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running and (self._listener is not None and self._listener.is_alive())

    @property
    def is_pressed(self) -> bool:
        with self._lock:
            return self._is_pressed

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    def set_mode(self, mode_str: str) -> bool:
        if mode_str not in (HotkeyMode.PRESS_TO_TALK, HotkeyMode.TOGGLE):
            return False
        with self._lock:
            self._mode = mode_str
            return True

    def rebind(self, new_hotkey_str: str) -> bool:
        """
        Rebinds the active hotkey combination.
        Returns True if successful, raises ValueError if invalid.
        """
        with self._lock:
            parsed_keys = parse_hotkey_string(new_hotkey_str)
            self._target_keys = parsed_keys
            self.hotkey_str = new_hotkey_str
            self._active_keys.clear()
            self._is_pressed = False
            logger.info(f"Hotkey rebound to: {new_hotkey_str}")
            return True

    def start(self) -> bool:
        """Starts the global keyboard listener thread and Win32 rescue polling loop."""
        with self._lock:
            if self._is_running:
                return True

            try:
                self._listener = keyboard.Listener(
                    on_press=self._on_pynput_press,
                    on_release=self._on_pynput_release,
                )
                self._listener.daemon = True
                self._listener.start()
                self._is_running = True

                if sys.platform == "win32":
                    self._rescue_thread = threading.Thread(
                        target=self._rescue_polling_loop,
                        daemon=True,
                        name="HotkeyRescueLoop"
                    )
                    self._rescue_thread.start()

                logger.info(f"HotkeyListener started for '{self.hotkey_str}' (Mode: {self._mode})")
                return True
            except Exception as e:
                logger.error(f"Failed to start HotkeyListener: {e}")
                self._is_running = False
                return False

    def stop(self) -> None:
        """Stops the global keyboard listener thread and rescue polling loop."""
        with self._lock:
            if not self._is_running:
                return

            self._is_running = False
            if self._listener:
                try:
                    self._listener.stop()
                except Exception as e:
                    logger.warning(f"Error stopping pynput listener: {e}")
                self._listener = None

            self._rescue_thread = None
            self._active_keys.clear()
            self._is_pressed = False
            logger.info("HotkeyListener stopped")

    def _rescue_polling_loop(self) -> None:
        """Win32 rescue check loop for sticky keys during active Press-To-Talk."""
        while self._is_running:
            time.sleep(0.08)  # 80ms poll interval
            if not self._is_pressed:
                continue

            with self._lock:
                if not self._is_running or not self._is_pressed:
                    continue

                if self._mode != HotkeyMode.PRESS_TO_TALK:
                    continue

                # Check physical state of required target keys
                key_released = False
                for target_key in self._target_keys:
                    vk_list = _get_vk_codes(target_key)
                    if vk_list and not any(_is_win32_key_down(vk) for vk in vk_list):
                        key_released = True
                        break

                if key_released:
                    logger.debug(f"Win32 rescue loop detected key release for '{self.hotkey_str}'")
                    self._is_pressed = False
                    self._active_keys.clear()
                    if self.on_keyup:
                        try:
                            self.on_keyup()
                        except Exception as e:
                            logger.error(f"Error in on_keyup callback: {e}")

    def _normalize_key(self, key: keyboard.Key | keyboard.KeyCode | None) -> Optional[keyboard.Key | keyboard.KeyCode]:
        if key is None:
            return None
        if key in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
            return keyboard.Key.alt
        if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
            return keyboard.Key.ctrl
        if key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
            return keyboard.Key.shift
        if key in (keyboard.Key.cmd_l, keyboard.Key.cmd_r):
            return keyboard.Key.cmd
        if isinstance(key, keyboard.KeyCode) and key.char:
            return keyboard.KeyCode.from_char(key.char.lower())
        return key

    def _on_pynput_press(self, key) -> None:
        norm_key = self._normalize_key(key)
        if norm_key is None:
            return

        with self._lock:
            self._active_keys.add(norm_key)

            if self._target_keys and self._target_keys.issubset(self._active_keys):
                now = time.time() * 1000.0
                if now - self._last_toggle_time < self.debounce_ms:
                    logger.debug("Hotkey press ignored due to debounce")
                    return

                self._last_toggle_time = now
                if not self._is_pressed:
                    self._is_pressed = True
                    print(f"\n[HOTKEY TRIGGERED] 🎙️ Activated ({self.hotkey_str}) — Recording Started!")
                    logger.info(f"Hotkey triggered: {self.hotkey_str}")
                    if self.on_keydown:
                        try:
                            self.on_keydown()
                        except Exception as e:
                            logger.error(f"Error in on_keydown callback: {e}")
                    if self.on_toggle:
                        try:
                            self.on_toggle()
                        except Exception as e:
                            logger.error(f"Error in on_toggle callback: {e}")

    def _on_pynput_release(self, key) -> None:
        norm_key = self._normalize_key(key)
        if norm_key is None:
            return

        with self._lock:
            self._active_keys.discard(norm_key)

            if self._is_pressed and not self._target_keys.issubset(self._active_keys):
                self._is_pressed = False
                print(f"[HOTKEY RELEASED] 🛑 Key released ({self.hotkey_str}) — Processing Audio...")
                logger.info(f"Hotkey released: {self.hotkey_str}")
                if self.on_keyup:
                    try:
                        self.on_keyup()
                    except Exception as e:
                        logger.error(f"Error in on_keyup callback: {e}")

