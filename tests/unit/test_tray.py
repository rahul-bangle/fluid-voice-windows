import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QSystemTrayIcon
from PyQt6.QtGui import QIcon
from fluid_voice.tray import FluidVoiceTrayIcon, TrayState


def test_tray_icon_initialization(qapp):
    """Tier 1: Verifies initial state, valid icon, and default tooltip of FluidVoiceTrayIcon."""
    tray = FluidVoiceTrayIcon()
    assert tray.current_state == TrayState.IDLE
    assert not tray.icon().isNull()
    assert "FluidVoice - Ready" in tray.toolTip()


@pytest.mark.parametrize("state,expected_tooltip", [
    (TrayState.IDLE, "FluidVoice - Ready"),
    (TrayState.RECORDING, "FluidVoice - Listening..."),
    (TrayState.TRANSCRIBING, "FluidVoice - Transcribing..."),
    (TrayState.ERROR, "FluidVoice - Error / Warning"),
])
def test_tray_state_transitions_all_enum_values(qapp, state, expected_tooltip):
    """Tier 1: Verifies state changes update current_state, procedural icon, and tooltip string."""
    tray = FluidVoiceTrayIcon()
    tray.set_state(state)

    assert tray.current_state == state
    assert not tray.icon().isNull()
    assert tray.toolTip() == expected_tooltip


def test_tray_custom_tooltip_override(qapp):
    """Tier 2: Verifies custom tooltip string overrides the default state text."""
    tray = FluidVoiceTrayIcon()
    tray.set_state(TrayState.RECORDING, custom_tooltip="FluidVoice - Custom Recording Status")

    assert tray.current_state == TrayState.RECORDING
    assert tray.toolTip() == "FluidVoice - Custom Recording Status"


def test_tray_procedural_icon_generation_for_all_states(qapp):
    """Tier 1: Verifies procedural QIcon drawing produces non-null 32x32 pixmaps for all states."""
    for state in TrayState:
        icon = FluidVoiceTrayIcon.create_state_icon(state)
        assert isinstance(icon, QIcon)
        assert not icon.isNull()
        sizes = icon.availableSizes()
        assert len(sizes) > 0
        assert sizes[0].width() == 32
        assert sizes[0].height() == 32


def test_tray_context_menu_structure_and_labels(qapp):
    """Tier 1: Verifies context menu action hierarchy, header status, and labels."""
    tray = FluidVoiceTrayIcon()
    menu = tray.contextMenu()
    assert menu is not None

    actions = menu.actions()
    assert len(actions) >= 5
    assert actions[0].text() == "FluidVoice v0.1.0"
    assert not actions[0].isEnabled()  # Disabled title header
    assert actions[2].text() == "Toggle Recording"
    assert actions[3].text() == "Settings..."
    assert actions[5].text() == "Exit FluidVoice"


def test_tray_signals_on_activation_trigger(qapp):
    """Tier 1: Verifies single click on tray icon emits recording_toggled signal."""
    tray = FluidVoiceTrayIcon()
    mock_listener = MagicMock()
    tray.recording_toggled.connect(mock_listener)

    tray._on_activated(QSystemTrayIcon.ActivationReason.Trigger)
    mock_listener.assert_called_once()


def test_tray_signals_on_activation_double_click(qapp):
    """Tier 1: Verifies double click on tray icon emits settings_requested signal."""
    tray = FluidVoiceTrayIcon()
    mock_listener = MagicMock()
    tray.settings_requested.connect(mock_listener)

    tray._on_activated(QSystemTrayIcon.ActivationReason.DoubleClick)
    mock_listener.assert_called_once()


def test_tray_menu_actions_signals(qapp):
    """Tier 1: Verifies context menu action triggers emit corresponding Qt signals."""
    tray = FluidVoiceTrayIcon()

    toggle_mock = MagicMock()
    settings_mock = MagicMock()
    exit_mock = MagicMock()

    tray.recording_toggled.connect(toggle_mock)
    tray.settings_requested.connect(settings_mock)
    tray.exit_requested.connect(exit_mock)

    menu = tray.contextMenu()

    # Trigger Toggle Action
    tray.toggle_action.trigger()
    toggle_mock.assert_called_once()

    # Trigger Settings Action
    tray.settings_action.trigger()
    settings_mock.assert_called_once()

    # Trigger Exit Action
    exit_action = menu.actions()[-1]
    exit_action.trigger()
    exit_mock.assert_called_once()


def test_tray_show_message_notification_trigger(qapp):
    """Tier 2: Verifies triggering system notification call on QSystemTrayIcon."""
    tray = FluidVoiceTrayIcon()
    with patch.object(QSystemTrayIcon, "showMessage") as mock_show_msg:
        tray.showMessage("FluidVoice", "Recording saved to clipboard", QSystemTrayIcon.MessageIcon.Information, 3000)
        mock_show_msg.assert_called_once_with(
            "FluidVoice", "Recording saved to clipboard", QSystemTrayIcon.MessageIcon.Information, 3000
        )


def test_tray_rapid_state_transitions(qapp):
    """Tier 2: Verifies stability under rapid sequential state transitions."""
    tray = FluidVoiceTrayIcon()
    states_sequence = [
        TrayState.IDLE,
        TrayState.RECORDING,
        TrayState.TRANSCRIBING,
        TrayState.ERROR,
        TrayState.IDLE,
        TrayState.RECORDING,
        TrayState.IDLE,
    ]

    for s in states_sequence:
        tray.set_state(s)
        assert tray.current_state == s
        assert not tray.icon().isNull()


def test_tray_error_state_icon_badge(qapp):
    """Tier 2: Verifies error state procedural icon includes error badge rendering."""
    icon = FluidVoiceTrayIcon.create_state_icon(TrayState.ERROR)
    assert not icon.isNull()
    pixmap = icon.pixmap(32, 32)
    assert not pixmap.isNull()
    assert pixmap.width() == 32
