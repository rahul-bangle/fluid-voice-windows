"""
Unit tests for fluid_voice.audio (Low-RAM Audio Recorder & Silence VAD).

Covers Tier 1 (Happy Path Feature Coverage) & Tier 2 (Boundary & Corner Cases).
Minimum 10 tests.
"""

import io
import wave
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from fluid_voice.audio import AudioRecorder
from tests.conftest import generate_wav_bytes, generate_silent_wav_bytes


# ============================================================================
# Tier 1: Happy Path Feature Coverage Tests
# ============================================================================

def test_audio_recorder_init_defaults():
    """Verify AudioRecorder initialization with default parameters."""
    recorder = AudioRecorder()
    assert recorder._sample_rate == 16000
    assert recorder._channels == 1
    assert recorder._silence_threshold == 200.0
    assert recorder._speech_threshold == 300.0
    assert recorder._silence_duration_sec == 1.2
    assert recorder._max_duration_sec == 30.0
    assert not recorder.is_recording()


def test_audio_recorder_start_stop_happy_path():
    """Tier 1: Audio recorder start and stop lifecycle emitting signals correctly."""
    recorder = AudioRecorder()
    started_emitted = False
    stopped_reason = None

    def on_started():
        nonlocal started_emitted
        started_emitted = True

    def on_stopped(reason):
        nonlocal stopped_reason
        stopped_reason = reason

    recorder.recording_started.connect(on_started)
    recorder.recording_stopped.connect(on_stopped)

    with patch("sounddevice.InputStream") as mock_stream_cls:
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        assert recorder.start_recording() is True
        assert recorder.is_recording() is True
        assert started_emitted is True

        wav_bytes = recorder.stop_recording()
        assert recorder.is_recording() is False
        assert stopped_reason == "manual"
        assert isinstance(wav_bytes, bytes)
        assert len(wav_bytes) > 0


def test_audio_recorder_wav_format_generation():
    """Tier 1: WAV output generation produces valid 16kHz 16-bit PCM mono WAV header and data."""
    recorder = AudioRecorder(sample_rate=16000, channels=1)

    # Inject mock audio chunk into recorder
    pcm_chunk = np.zeros((1600, 1), dtype=np.int16)
    recorder._pcm_chunks.append(pcm_chunk)

    wav_bytes = recorder._encode_wav(recorder._pcm_chunks)

    # Read back WAV bytes to verify audio format compliance
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2  # 16-bit = 2 bytes
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 1600


def test_audio_recorder_buffer_management():
    """Tier 1: Recording buffer management accumulates chunks during callback and resets on new session."""
    recorder = AudioRecorder(sample_rate=16000)

    # Simulate callback chunks
    chunk1 = np.ones((1024, 1), dtype=np.int16) * 500
    chunk2 = np.ones((1024, 1), dtype=np.int16) * 1000

    recorder._is_recording = True
    recorder._audio_callback(chunk1, 1024, {}, None)
    recorder._audio_callback(chunk2, 1024, {}, None)

    assert len(recorder._pcm_chunks) == 2
    assert recorder._total_samples == 2048

    # Verify start_recording clears buffer for new session
    with patch("sounddevice.InputStream"):
        recorder._is_recording = False
        recorder.start_recording()
        assert len(recorder._pcm_chunks) == 0
        assert recorder._total_samples == 0


def test_audio_recorder_level_meter_calculation():
    """Tier 1: Audio level meter calculation converts chunk RMS to 0.0 - 1.0 normalized range."""
    recorder = AudioRecorder()
    emitted_levels = []

    recorder.audio_level_changed.connect(lambda lvl: emitted_levels.append(lvl))
    recorder._is_recording = True

    # Silent chunk (RMS = 0)
    silent_chunk = np.zeros((1024, 1), dtype=np.int16)
    recorder._audio_callback(silent_chunk, 1024, {}, None)
    assert emitted_levels[-1] == 0.0

    # Speech chunk (RMS ~ 1500)
    speech_chunk = np.full((1024, 1), 1500, dtype=np.int16)
    recorder._audio_callback(speech_chunk, 1024, {}, None)
    assert 0.4 <= emitted_levels[-1] <= 0.6

    # High amplitude chunk (Clipped to 1.0)
    loud_chunk = np.full((1024, 1), 32000, dtype=np.int16)
    recorder._audio_callback(loud_chunk, 1024, {}, None)
    assert emitted_levels[-1] == 1.0


def test_audio_recorder_silence_detection_vad_trigger():
    """Tier 1: Silence detection VAD triggers auto-stop after speech followed by sustained silence."""
    recorder = AudioRecorder(
        sample_rate=16000,
        silence_threshold_rms=200.0,
        speech_threshold_rms=300.0,
        silence_duration_sec=0.1,  # Fast duration for unit test
    )
    recorder._is_recording = True

    # 1. Speech chunk (RMS 1000 > 300) sustained for 0.4s (6400 samples)
    speech_chunk = np.full((6400, 1), 1000, dtype=np.int16)  # 0.4s speech
    recorder._audio_callback(speech_chunk, 6400, {}, None)
    assert recorder._speech_detected is True

    # 2. Silence chunk (RMS 50 < 200) sustained for 0.1s
    silence_chunk = np.full((1600, 1), 50, dtype=np.int16)
    recorder._audio_callback(silence_chunk, 1600, {}, None)

    assert recorder._stop_reason == "vad_silence"
    assert recorder._is_recording is False


def test_audio_recorder_initial_silence_timeout():
    """Tier 1: Initial silence VAD triggers stop if no speech occurs for > 5 seconds."""
    recorder = AudioRecorder(sample_rate=16000)
    recorder._is_recording = True

    # Feed 5.1 seconds of silence (81,600 samples)
    silence_chunk = np.zeros((81600, 1), dtype=np.int16)
    recorder._audio_callback(silence_chunk, 81600, {}, None)

    assert recorder._stop_reason == "initial_silence"
    assert recorder._is_recording is False


# ============================================================================
# Tier 2: Boundary & Corner Cases Tests
# ============================================================================

def test_audio_recorder_empty_audio_capture():
    """Tier 2: Instant stop without feeding audio chunks returns valid empty WAV payload."""
    recorder = AudioRecorder()

    with patch("sounddevice.InputStream"):
        recorder.start_recording()
        wav_bytes = recorder.stop_recording()

    assert isinstance(wav_bytes, bytes)
    # Valid WAV header size for 0 frames is 44 bytes
    assert len(wav_bytes) == 44
    assert wav_bytes.startswith(b"RIFF")


def test_audio_recorder_max_duration_cap_limit():
    """Tier 2: Audio recorder enforces hard duration cap (e.g. 30s limit) automatically."""
    recorder = AudioRecorder(sample_rate=16000, max_duration_sec=1.0)  # 1.0s cap for testing
    recorder._is_recording = True

    # Feed 16,000 samples (exactly 1.0 second)
    chunk = np.ones((16000, 1), dtype=np.int16) * 500
    recorder._audio_callback(chunk, 16000, {}, None)

    assert recorder._stop_reason == "max_duration"
    assert recorder._is_recording is False


def test_audio_recorder_microphone_disconnect_failure():
    """Tier 2: sounddevice InputStream exception handling on microphone disconnect/failure."""
    recorder = AudioRecorder()
    error_msg = None

    def on_error(msg):
        nonlocal error_msg
        error_msg = msg

    recorder.error_occurred.connect(on_error)

    with patch("sounddevice.InputStream", side_effect=RuntimeError("Microphone device disconnected")):
        success = recorder.start_recording()
        assert success is False
        assert recorder.is_recording() is False
        assert error_msg is not None
        assert "Microphone device disconnected" in error_msg


def test_audio_recorder_sounddevice_exception_on_stop():
    """Tier 2: Stream stop/close exception during stop_recording is handled gracefully."""
    recorder = AudioRecorder()

    mock_stream = MagicMock()
    mock_stream.stop.side_effect = RuntimeError("PortAudio device error on stop")
    recorder._stream = mock_stream
    recorder._is_recording = True

    # Should not raise exception
    wav_bytes = recorder.stop_recording()
    assert isinstance(wav_bytes, bytes)
    assert recorder.is_recording() is False


def test_audio_recorder_buffer_overflow_prevention_long_recording():
    """Tier 2: Buffer overflow prevention and stability under long continuous audio recording."""
    recorder = AudioRecorder(sample_rate=16000, max_duration_sec=30.0)
    recorder._is_recording = True

    # Feed 30 blocks of 1024 samples each
    chunk = np.full((1024, 1), 400, dtype=np.int16)
    for _ in range(30):
        if recorder.is_recording():
            recorder._audio_callback(chunk, 1024, {}, None)

    assert len(recorder._pcm_chunks) == 30
    assert recorder._total_samples == 30720
    # Memory check: RAM payload remains under < 1MB
    raw_data = np.concatenate(recorder._pcm_chunks, axis=0)
    assert raw_data.nbytes < 1000000


def test_audio_recorder_device_query_fallback():
    """Tier 2: Get audio devices handles query failures without crashing."""
    recorder = AudioRecorder()

    with patch("sounddevice.query_devices", side_effect=Exception("Driver query failed")):
        devices = recorder.get_audio_devices()
        assert isinstance(devices, list)
        assert len(devices) == 0
