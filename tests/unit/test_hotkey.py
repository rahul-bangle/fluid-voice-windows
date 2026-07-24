import time
from unittest.mock import MagicMock, patch
import pytest
from pynput import keyboard

from fluid_voice.hotkey import HotkeyListener, parse_hotkey_string


def test_parse_hotkey_string_valid_combinations():
    """Tier 1: Verifies parsing valid hotkey strings into pynput key sets."""
    # Win+Space
    keys_win_space = parse_hotkey_string("Win+Space")
    assert keyboard.Key.cmd in keys_win_space
    assert keyboard.Key.space in keys_win_space

    # Alt+S
    keys_alt_s = parse_hotkey_string("Alt+S")
    assert keyboard.Key.alt in keys_alt_s
    assert keyboard.KeyCode.from_char("s") in keys_alt_s

    # Ctrl+Shift+Space
    keys_ctrl_shift_space = parse_hotkey_string("Ctrl+Shift+Space")
    assert keyboard.Key.ctrl in keys_ctrl_shift_space
    assert keyboard.Key.shift in keys_ctrl_shift_space
    assert keyboard.Key.space in keys_ctrl_shift_space


@pytest.mark.parametrize("invalid_hotkey", [
    "",
    "   ",
    "InvalidKeyName",
    "Win+UnknownKey123",
    "+++",
    None,
])
def test_parse_hotkey_string_invalid_strings(invalid_hotkey):
    """Tier 2: Verifies ValueError is raised for invalid, empty, or unparseable hotkey strings."""
    with pytest.raises(ValueError):
        parse_hotkey_string(invalid_hotkey)


def test_hotkey_listener_initialization_defaults():
    """Tier 1: Verifies default properties of HotkeyListener instance."""
    listener = HotkeyListener(hotkey_str="Win+Space")
    assert listener.hotkey_str == "Win+Space"
    assert listener.is_running is False
    assert listener.is_pressed is False


def test_hotkey_listener_start_and_stop_lifecycle():
    """Tier 1: Verifies listener thread start and stop lifecycle."""
    mock_pynput_listener = MagicMock()
    mock_pynput_listener.is_alive.return_value = True

    with patch("pynput.keyboard.Listener", return_value=mock_pynput_listener):
        listener = HotkeyListener(hotkey_str="Win+Space")

        started = listener.start()
        assert started is True
        assert listener.is_running is True
        mock_pynput_listener.start.assert_called_once()

        listener.stop()
        assert listener.is_running is False
        mock_pynput_listener.stop.assert_called_once()


def test_hotkey_listener_keydown_keyup_events():
    """Tier 1: Verifies keydown, keyup, and toggle callbacks trigger on key combo sequence."""
    keydown_mock = MagicMock()
    keyup_mock = MagicMock()
    toggle_mock = MagicMock()

    listener = HotkeyListener(
        hotkey_str="Alt+S",
        on_keydown=keydown_mock,
        on_keyup=keyup_mock,
        on_toggle=toggle_mock,
        debounce_ms=0.0,
    )

    alt_key = keyboard.Key.alt
    s_key = keyboard.KeyCode.from_char("s")

    # Press Alt (partial press)
    listener._on_pynput_press(alt_key)
    assert listener.is_pressed is False
    keydown_mock.assert_not_called()

    # Press S (complete combo)
    listener._on_pynput_press(s_key)
    assert listener.is_pressed is True
    keydown_mock.assert_called_once()
    toggle_mock.assert_called_once()

    # Release S (break combo)
    listener._on_pynput_release(s_key)
    assert listener.is_pressed is False
    keyup_mock.assert_called_once()


def test_hotkey_listener_rebind_valid_hotkey():
    """Tier 1: Verifies rebinding to a new valid hotkey combination ('Alt+S')."""
    listener = HotkeyListener(hotkey_str="Win+Space")
    assert listener.hotkey_str == "Win+Space"

    success = listener.rebind("Alt+S")
    assert success is True
    assert listener.hotkey_str == "Alt+S"
    assert keyboard.Key.alt in listener._target_keys
    assert keyboard.KeyCode.from_char("s") in listener._target_keys


def test_hotkey_listener_rebind_invalid_hotkey_raises_error():
    """Tier 2: Verifies rebinding to invalid hotkey raises ValueError without corrupting state."""
    listener = HotkeyListener(hotkey_str="Win+Space")

    with pytest.raises(ValueError):
        listener.rebind("Invalid+Key+Combo")

    # State remains unchanged
    assert listener.hotkey_str == "Win+Space"
    assert keyboard.Key.cmd in listener._target_keys


def test_hotkey_listener_rapid_toggling_debouncing():
    """Tier 2: Verifies rapid key press toggles within debounce window are debounced correctly."""
    toggle_mock = MagicMock()
    listener = HotkeyListener(
        hotkey_str="Win+Space",
        on_toggle=toggle_mock,
        debounce_ms=200.0,
    )

    win_key = keyboard.Key.cmd
    space_key = keyboard.Key.space

    # First press triggers toggle
    listener._on_pynput_press(win_key)
    listener._on_pynput_press(space_key)
    assert toggle_mock.call_count == 1

    # Immediate release & second press within 200ms debounce window should be ignored
    listener._on_pynput_release(space_key)
    listener._on_pynput_press(space_key)
    assert toggle_mock.call_count == 1


def test_hotkey_listener_callback_exception_resilience():
    """Tier 2: Verifies listener remains stable when callbacks raise unhandled exceptions."""
    faulty_keydown = MagicMock(side_effect=RuntimeError("Callback crash"))
    keyup_mock = MagicMock()

    listener = HotkeyListener(
        hotkey_str="Alt+S",
        on_keydown=faulty_keydown,
        on_keyup=keyup_mock,
        debounce_ms=0.0,
    )

    alt_key = keyboard.Key.alt
    s_key = keyboard.KeyCode.from_char("s")

    # Trigger keydown (should handle exception inside callback without breaking listener)
    listener._on_pynput_press(alt_key)
    listener._on_pynput_press(s_key)
    assert listener.is_pressed is True
    faulty_keydown.assert_called_once()

    # Trigger keyup
    listener._on_pynput_release(s_key)
    assert listener.is_pressed is False
    keyup_mock.assert_called_once()


def test_hotkey_listener_key_normalization():
    """Tier 2: Verifies uppercase key codes are normalized to lowercase for matching."""
    keydown_mock = MagicMock()
    listener = HotkeyListener(
        hotkey_str="Alt+S",
        on_keydown=keydown_mock,
        debounce_ms=0.0,
    )

    alt_key = keyboard.Key.alt
    upper_s_key = keyboard.KeyCode.from_char("S")

    listener._on_pynput_press(alt_key)
    listener._on_pynput_press(upper_s_key)

    assert listener.is_pressed is True
    keydown_mock.assert_called_once()


def test_hotkey_listener_partial_modifier_press_no_trigger():
    """Tier 2: Verifies pressing modifier keys alone does not trigger hotkey events."""
    keydown_mock = MagicMock()
    listener = HotkeyListener(
        hotkey_str="Win+Space",
        on_keydown=keydown_mock,
        debounce_ms=0.0,
    )

    # Press Win key only
    listener._on_pynput_press(keyboard.Key.cmd)
    assert listener.is_pressed is False
    keydown_mock.assert_not_called()

    # Release Win key
    listener._on_pynput_release(keyboard.Key.cmd)
    assert listener.is_pressed is False
    keydown_mock.assert_not_called()


def test_parse_hotkey_string_ctrl_alt_c():
    """Milestone 2: Verifies parsing 'Ctrl+Alt+C' hotkey combination."""
    keys = parse_hotkey_string("Ctrl+Alt+C")
    assert keyboard.Key.ctrl in keys
    assert keyboard.Key.alt in keys
    assert keyboard.KeyCode.from_char("c") in keys


def test_hotkey_listener_secondary_hotkey_registration_and_trigger():
    """Milestone 2: Verifies registering secondary hotkey 'Ctrl+Alt+C' and triggering callbacks."""
    sec_keydown = MagicMock()
    sec_keyup = MagicMock()

    listener = HotkeyListener(hotkey_str="Win+Space", debounce_ms=0.0)
    listener.add_hotkey("Ctrl+Alt+C", on_keydown=sec_keydown, on_keyup=sec_keyup, debounce_ms=0.0)

    ctrl_key = keyboard.Key.ctrl
    alt_key = keyboard.Key.alt
    c_key = keyboard.KeyCode.from_char("c")

    # Press Ctrl + Alt + C
    listener._on_pynput_press(ctrl_key)
    listener._on_pynput_press(alt_key)
    sec_keydown.assert_not_called()

    listener._on_pynput_press(c_key)
    sec_keydown.assert_called_once()

    # Release C key
    listener._on_pynput_release(c_key)
    sec_keyup.assert_called_once()


def test_parse_hotkey_string_alt_shift_j():
    """R3: Verifies parsing 'Alt+Shift+J' hotkey combination and secondary binding trigger."""
    keys = parse_hotkey_string("Alt+Shift+J")
    assert keyboard.Key.alt in keys
    assert keyboard.Key.shift in keys
    assert keyboard.KeyCode.from_char("j") in keys


def test_hotkey_listener_alt_shift_j_toggle():
    """R3: Verifies Alt+Shift+J secondary hotkey registration and mode toggle."""
    toggle_mock = MagicMock()
    listener = HotkeyListener(hotkey_str="Win+Space", debounce_ms=0.0)
    listener.add_hotkey("Alt+Shift+J", on_keydown=toggle_mock, debounce_ms=0.0)

    alt_key = keyboard.Key.alt
    shift_key = keyboard.Key.shift
    j_key = keyboard.KeyCode.from_char("j")

    listener._on_pynput_press(alt_key)
    listener._on_pynput_press(shift_key)
    toggle_mock.assert_not_called()

    listener._on_pynput_press(j_key)
    toggle_mock.assert_called_once()

    assert listener.toggle_jarvis_mode() == "jarvis"
    assert listener.toggle_jarvis_mode() == "press_to_talk"


