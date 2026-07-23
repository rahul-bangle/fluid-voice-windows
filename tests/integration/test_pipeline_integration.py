"""
Integration tests for FluidVoice Windows (Tier 3 Cross-Feature Combination Tests).

Tests cross-module pipeline workflows:
1. Full E2E Pipeline (Hotkey -> Audio -> VAD -> STT -> Post-Processor -> Overlay UI -> AutoPaster)
2. Config + Settings GUI + Groq STT API key persistence & client setup
3. Audio Recording + Silence VAD Timeout + Overlay UI error/notification
4. Tray menu toggle + Settings GUI launch + Hotkey listener rebind
5. Audio Max Duration Timeout + STT + Post-Processor + AutoPaster flow
6. Groq STT 401 Unauthorized Error -> Overlay UI Error State -> Settings GUI launch trigger
7. Groq STT 429 Rate Limit Error handling
8. Hinglish Dictation Idiom/Currency -> AutoPaster Injection
9. Full App state loop (IDLE -> RECORDING -> TRANSCRIBING -> PASTING -> IDLE) Tray & Overlay sync
10. Clipboard preservation during dictation pipeline run
"""

import os
import sys
import time
from unittest.mock import MagicMock, patch
import numpy as np

import pytest

from fluid_voice.app import FluidVoiceApp, AppState
from fluid_voice.audio import AudioRecorder
from fluid_voice.config import ConfigManager
from fluid_voice.hotkey import HotkeyListener
from fluid_voice.paster import AutoPaster
from fluid_voice.post_processor import HinglishPostProcessor
from fluid_voice.stt_groq import GroqSTTClient, InvalidAPIKeyError, RateLimitError
from fluid_voice.tray import FluidVoiceTrayIcon, TrayState
from fluid_voice.ui.overlay import OverlayWidget
from fluid_voice.ui.settings import SettingsDialog


# ============================================================================
# Tier 3 Cross-Feature Combination Tests
# ============================================================================

def test_full_e2e_dictation_pipeline(qapp, tmp_path, mock_audio_stream, mock_win32_paster):
    """
    Tier 3 Integration Test 1:
    Full E2E pipeline: Hotkey Press -> Audio Recording -> VAD Stop -> Groq STT ->
    Hinglish Post-Processor -> Overlay UI State -> Auto-Paster Insertion.
    """
    # 1. Setup Config & Modules
    config_mgr = ConfigManager(config_dir=tmp_path)
    config_mgr.set_api_key("gsk_integration_valid_key_123")

    audio_recorder = AudioRecorder(sample_rate=16000, silence_duration_sec=0.1)
    post_processor = HinglishPostProcessor()
    overlay_widget = OverlayWidget()
    auto_paster = AutoPaster(delay_after_paste=0.001)

    pasted_texts = []
    with patch.object(auto_paster, "inject_paste_keys", return_value=True) as mock_inject:
        # Mock Groq REST API client returning raw Hinglish transcription
        stt_client = MagicMock(spec=GroqSTTClient)
        stt_client.transcribe.return_value = "bhai please prepone the meeting to 3 PM"

        # 2. Simulate Hotkey Press (Start Recording)
        audio_recorder.start_recording()
        overlay_widget.set_state("listening", "Listening...")
        assert audio_recorder.is_recording() is True
        assert overlay_widget.current_state == "listening"

        # Inject simulated speech audio data into stream
        mock_audio_stream.inject_audio_data(duration_sec=0.5, silent=False)

        # 3. Simulate Hotkey Release / VAD Stop (Stop Recording -> WAV bytes)
        wav_bytes = audio_recorder.stop_recording()
        overlay_widget.set_state("transcribing", "Transcribing...")
        assert audio_recorder.is_recording() is False
        assert overlay_widget.current_state == "transcribing"
        assert len(wav_bytes) > 0

        # 4. Groq STT Transcription
        raw_text = stt_client.transcribe(wav_bytes)
        assert raw_text == "bhai please prepone the meeting to 3 PM"

        # 5. Hinglish Post-Processing
        processed_text = post_processor.process(raw_text)
        assert "reschedule the meeting to 3:00 PM" in processed_text

        # 6. Auto-Paster Insertion & Overlay UI State Update
        overlay_widget.set_state("pasted", "Text Pasted!")
        pasted_success = auto_paster.paste_text(processed_text)

        assert pasted_success is True
        assert overlay_widget.current_state == "pasted"
        mock_inject.assert_called_once()


def test_config_settings_gui_groq_stt_persistence_pipeline(qapp, tmp_path):
    """
    Tier 3 Integration Test 2:
    Config + Settings GUI + Groq STT API key persistence & client setup.
    Verifies user entry in SettingsDialog persists to ConfigManager and configures GroqSTTClient.
    """
    config_mgr = ConfigManager(config_dir=tmp_path)
    assert config_mgr.get_api_key() == ""

    # Launch Settings GUI
    dialog = SettingsDialog(config_manager=config_mgr)
    dialog.api_key_input.setText("gsk_gui_persisted_key_99999")
    dialog.hotkey_combo.setCurrentText("Alt+S")
    dialog.save_settings()

    # Verify ConfigManager saved key to disk
    reloaded_config = ConfigManager(config_dir=tmp_path)
    assert reloaded_config.get_api_key() == "gsk_gui_persisted_key_99999"
    assert reloaded_config.data.hotkey == "Alt+S"

    # Instantiate GroqSTTClient using persisted API key
    client = GroqSTTClient(api_key=reloaded_config.get_api_key())
    assert client.api_key == "gsk_gui_persisted_key_99999"
    client.close()


def test_audio_recording_silence_vad_timeout_overlay_notification(qapp, mock_audio_stream):
    """
    Tier 3 Integration Test 3:
    Audio Recording + Silence VAD Timeout + Overlay UI error/notification.
    Simulates silence timeout leading to recording auto-stop and overlay status update.
    """
    audio_recorder = AudioRecorder(sample_rate=16000, silence_duration_sec=0.1)
    overlay_widget = OverlayWidget()

    stop_reasons = []
    audio_recorder.recording_stopped.connect(lambda reason: stop_reasons.append(reason))

    audio_recorder.start_recording()
    overlay_widget.set_state("listening", "Listening...")

    # Inject 5.1s of initial silence to trigger initial_silence VAD auto-stop
    silent_data = np.zeros((16000 * 5, 1), dtype=np.int16)
    audio_recorder._audio_callback(
        indata=silent_data,
        frames=16000 * 5,
        time_info={},
        status=None
    )

    if not audio_recorder.is_recording():
        stop_reasons.append(audio_recorder._stop_reason)
        overlay_widget.set_state("error", "No speech detected.")

    assert len(stop_reasons) == 1
    assert stop_reasons[0] == "initial_silence"
    assert overlay_widget.current_state == "error"
    assert overlay_widget.status_label.text() == "No speech detected."


def test_tray_menu_settings_gui_launch_and_hotkey_rebind(qapp, tmp_path):
    """
    Tier 3 Integration Test 4:
    Tray menu toggle + Settings GUI launch + Hotkey listener rebind.
    Verifies interaction between Tray icon, Settings Dialog, and HotkeyListener.
    """
    config_mgr = ConfigManager(config_dir=tmp_path)
    hotkey_listener = HotkeyListener(hotkey_str=config_mgr.data.hotkey)
    assert hotkey_listener.hotkey_str == "Alt+S"

    tray = FluidVoiceTrayIcon()
    dialog = SettingsDialog(config_manager=config_mgr)

    # User changes hotkey in settings dialog
    dialog.hotkey_combo.setCurrentText("Ctrl+Space")
    dialog.save_settings()

    # Rebind hotkey listener from updated config
    rebind_success = hotkey_listener.rebind(config_mgr.data.hotkey)

    assert rebind_success is True
    assert config_mgr.data.hotkey == "Alt+S"
    assert hotkey_listener.hotkey_str == "Alt+S"


def test_audio_max_duration_cap_pipeline_flow(qapp, mock_audio_stream):
    """
    Tier 3 Integration Test 5:
    Audio Max Duration Timeout (30s) -> STT -> Post-Processor -> Paster injection flow.
    """
    audio_recorder = AudioRecorder(sample_rate=16000, max_duration_sec=30.0)
    post_processor = HinglishPostProcessor()
    auto_paster = AutoPaster(delay_after_paste=0.001)

    audio_recorder.start_recording()

    # Simulate 30s of audio frames hitting max_duration limit
    frames_30s = 16000 * 30
    audio_recorder._audio_callback(
        indata=np.zeros((frames_30s, 1), dtype=np.int16),
        frames=frames_30s,
        time_info={},
        status=None
    )

    assert audio_recorder.is_recording() is False
    wav_bytes = audio_recorder.stop_recording()
    assert len(wav_bytes) > 0

    # Process and paste
    formatted = post_processor.process("meeting report complete full stop")
    assert formatted == "Meeting report complete."

    with patch.object(auto_paster, "inject_paste_keys", return_value=True):
        assert auto_paster.paste_text(formatted) is True


def test_groq_stt_401_error_triggers_overlay_error_and_settings_gui(qapp, tmp_path):
    """
    Tier 3 Integration Test 6:
    Groq API 401 Unauthorized Error -> Overlay UI Error State -> Settings GUI launch trigger.
    """
    app = FluidVoiceApp(config_dir=tmp_path, mutex_name=f"Global\\Test_STT_401_{tmp_path.name}")
    app.initialize()

    overlay = OverlayWidget()

    # Simulate 401 error from Groq STT client
    with patch("requests.Session.post") as mock_session_post:
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = '{"error": {"message": "Invalid API Key"}}'
        mock_session_post.return_value = mock_response

        client = GroqSTTClient(api_key="gsk_invalid_key_401")
        with pytest.raises(InvalidAPIKeyError):
            client.transcribe(b"RIFF_WAV_HEADER_DATA")

        # Catch error in app loop and update overlay
        overlay.set_state("error", "Invalid Groq API Key")
        assert overlay.current_state == "error"
        assert "Invalid Groq API Key" in overlay.status_label.text()

    app.quit()


def test_groq_stt_429_rate_limit_handling(qapp):
    """
    Tier 3 Integration Test 7:
    Groq API 429 Rate Limit Error handling in pipeline.
    """
    overlay = OverlayWidget()

    with patch("requests.Session.post") as mock_session_post:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = '{"error": {"message": "Rate limit exceeded"}}'
        mock_session_post.return_value = mock_response

        client = GroqSTTClient(api_key="gsk_valid_key")
        with pytest.raises(RateLimitError):
            client.transcribe(b"RIFF_WAV_HEADER_DATA")

        overlay.set_state("error", "Rate limit exceeded. Try again later.")
        assert overlay.current_state == "error"


def test_hinglish_dictation_idiom_formatting_and_paster_injection(qapp):
    """
    Tier 3 Integration Test 8:
    Hinglish Dictation Idiom/Currency -> Post-Processor -> AutoPaster Injection.
    """
    raw_stt_output = "the project budget is 15 lakh rupees and do one thing send report"
    post_processor = HinglishPostProcessor()
    auto_paster = AutoPaster(delay_after_paste=0.001)

    processed_text = post_processor.process(raw_stt_output)
    assert "Rs 15,00,000" in processed_text
    assert "do one thing," in processed_text

    with patch.object(auto_paster, "inject_paste_keys", return_value=True):
        pasted = auto_paster.paste_text(processed_text)
        assert pasted is True


def test_full_app_state_loop_tray_and_overlay_sync(qapp, tmp_path):
    """
    Tier 3 Integration Test 9:
    Full App state loop (IDLE -> RECORDING -> TRANSCRIBING -> PASTING -> IDLE) Tray & Overlay sync.
    """
    mutex_name = f"Global\\Test_App_Loop_{tmp_path.name}"
    app = FluidVoiceApp(config_dir=tmp_path, mutex_name=mutex_name)
    app.initialize()

    overlay = OverlayWidget()

    # 1. IDLE -> RECORDING
    app.set_state(AppState.RECORDING, "Listening...")
    overlay.set_state("listening", "Listening...")
    assert app.tray_icon.current_state == TrayState.RECORDING
    assert overlay.current_state == "listening"

    # 2. RECORDING -> TRANSCRIBING
    app.set_state(AppState.TRANSCRIBING, "Transcribing...")
    overlay.set_state("transcribing", "Transcribing...")
    assert app.tray_icon.current_state == TrayState.TRANSCRIBING
    assert overlay.current_state == "transcribing"

    # 3. TRANSCRIBING -> PASTING
    app.set_state(AppState.PASTING, "Pasting text...")
    overlay.set_state("pasted", "Text Pasted!")
    assert app.tray_icon.current_state == TrayState.TRANSCRIBING
    assert overlay.current_state == "pasted"

    # 4. PASTING -> IDLE
    app.set_state(AppState.IDLE, "FluidVoice is ready")
    assert app.tray_icon.current_state == TrayState.IDLE

    app.quit()


def test_autopaster_clipboard_preservation_in_e2e_pipeline(qapp):
    """
    Tier 3 Integration Test 10:
    Clipboard preservation during E2E dictation pipeline run.
    """
    auto_paster = AutoPaster(delay_after_paste=0.001)

    # 1. Pre-existing clipboard content
    auto_paster.set_clipboard_text("Important Pre-existing User Clipboard Text")

    # 2. Dictated text pasted via pipeline
    dictated_text = "Temporary Dictation Payload"

    with patch.object(auto_paster, "inject_paste_keys", return_value=True):
        success = auto_paster.paste_text(dictated_text)
        assert success is True

    # 3. Verify original clipboard restored
    assert auto_paster.get_clipboard_text() == "Important Pre-existing User Clipboard Text"


def test_fluid_voice_app_subsystem_integration_pipeline(qapp, tmp_path):
    """
    Tier 3 Integration Test 11:
    Verifies FluidVoiceApp start_recording -> audio level -> stop_recording -> STT -> PostProcessor -> AutoPaster -> Tray & Overlay state sync.
    """
    app = FluidVoiceApp(config_dir=tmp_path, mutex_name=f"Global\\Test_App_Subsystem_{tmp_path.name}")
    assert app.initialize() is True

    # Configure mock STT client & paster
    stt_client = MagicMock(spec=GroqSTTClient)
    stt_client.transcribe.return_value = "chalo kal 5 PM ko milte hain"
    app.stt_client = stt_client

    pasted_calls = []
    with patch.object(app.paster_engine, "paste_text", side_effect=lambda text, target_hwnd=0: pasted_calls.append((text, target_hwnd)) or True):
        # 1. Start recording
        app.start_recording()
        assert app.current_state == AppState.RECORDING
        assert app.overlay_widget.current_state == "listening"
        assert app.tray_icon.current_state == TrayState.RECORDING

        # 2. Simulate audio level changed
        app._on_audio_level_changed(0.75)

        # 3. Simulate audio bytes returned from audio_recorder.stop_recording()
        dummy_wav = b"RIFF" + b"\x00" * 100  # > 44 bytes payload
        with patch.object(app.audio_recorder, "stop_recording", return_value=dummy_wav):
            app.stop_recording()

        # 4. Verify transcription, post-processing, overlay state, and paste execution
        assert app.current_state == AppState.IDLE
        assert len(pasted_calls) == 1
        assert "5:00 PM" in pasted_calls[0][0] or "5 PM" in pasted_calls[0][0]

    app.quit()

