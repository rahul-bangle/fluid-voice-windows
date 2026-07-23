import sys
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fluid_voice.app import FluidVoiceApp, AppState
from fluid_voice.tray import TrayState


def test_app_initialization(qapp, tmp_path):
    mutex_name = f"Global\\Test_FluidVoice_Mutex_{uuid.uuid4().hex}"
    app = FluidVoiceApp(config_dir=tmp_path, mutex_name=mutex_name)

    assert app.current_state == AppState.IDLE
    
    success = app.initialize()
    assert success is True
    assert app.tray_icon is not None
    assert app.tray_icon.current_state == TrayState.IDLE

    # Clean up
    app.quit()


def test_app_state_transitions_and_signals(qapp, tmp_path):
    mutex_name = f"Global\\Test_FluidVoice_Mutex_State_{uuid.uuid4().hex}"
    app = FluidVoiceApp(config_dir=tmp_path, mutex_name=mutex_name)
    app.initialize()
    if app.audio_recorder:
        app.audio_recorder.start_recording = MagicMock(return_value=True)

    emitted_states = []
    app.state_changed.connect(lambda state, msg: emitted_states.append((state, msg)))

    # Test toggle IDLE -> RECORDING
    app.toggle_recording()
    assert app.current_state == AppState.RECORDING
    assert app.tray_icon.current_state == TrayState.RECORDING
    assert emitted_states[-1][0] == AppState.RECORDING

    # Test toggle RECORDING -> TRANSCRIBING
    app.toggle_recording()
    assert app.current_state == AppState.TRANSCRIBING
    assert app.tray_icon.current_state == TrayState.TRANSCRIBING
    assert emitted_states[-1][0] == AppState.TRANSCRIBING

    # Test explicit set_state to PASTING
    app.set_state(AppState.PASTING, "Pasting text...")
    assert app.current_state == AppState.PASTING
    assert app.tray_icon.current_state == TrayState.TRANSCRIBING  # Mapped tray state

    # Test explicit set_state to ERROR
    app.set_state(AppState.ERROR, "Groq API error")
    assert app.current_state == AppState.ERROR
    assert app.tray_icon.current_state == TrayState.ERROR

    app.quit()


def test_single_instance_enforcement(qapp, tmp_path):
    mutex_name = f"Global\\Test_FluidVoice_Mutex_SingleInstance_{tmp_path.name}"
    
    first_app = FluidVoiceApp(config_dir=tmp_path, mutex_name=mutex_name)
    assert first_app.initialize() is True

    # Try starting a second app with identical mutex name
    second_app = FluidVoiceApp(config_dir=tmp_path, mutex_name=mutex_name)
    assert second_app.initialize() is False

    # Cleanup first app
    first_app.quit()

    # After first app quits, second app should now be able to initialize
    third_app = FluidVoiceApp(config_dir=tmp_path, mutex_name=mutex_name)
    assert third_app.initialize() is True
    third_app.quit()


def test_app_lockfile_fallback(qapp, tmp_path):
    mutex_name = f"Global\\Test_FluidVoice_Mutex_Fallback_{tmp_path.name}"
    app = FluidVoiceApp(config_dir=tmp_path, mutex_name=mutex_name)

    # Force Win32 mutex check to fail, driving lockfile fallback path
    with patch("sys.platform", "linux"):
        assert app._check_single_instance() is True
        assert (tmp_path / "app.lock").exists()

        # Second instance while lockfile exists
        second_app = FluidVoiceApp(config_dir=tmp_path, mutex_name=mutex_name)
        assert second_app._check_single_instance() is False

    app.quit()
    assert not (tmp_path / "app.lock").exists()
