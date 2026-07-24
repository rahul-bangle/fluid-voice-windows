"""
tests/unit/test_stt_local.py
----------------------------
Unit test suite for Phase 3: Offline Local STT Fallback & Circuit Breaker Engine.
"""

import pytest
from unittest.mock import MagicMock, patch

from fluid_voice.stt_local import LocalWhisperSTTClient, HAS_FASTER_WHISPER


def test_local_stt_client_initialization(tmp_path):
    """Verifies LocalWhisperSTTClient instantiation and path creation."""
    client = LocalWhisperSTTClient(download_root=tmp_path / "models")
    assert client.model_size == "small"
    assert client.compute_type == "int8"
    assert client.download_root == tmp_path / "models"


def test_local_stt_client_empty_audio():
    """Verifies that transcribing empty audio bytes returns empty string immediately."""
    client = LocalWhisperSTTClient()
    result = client.transcribe_audio_bytes(b"")
    assert result == ""


def test_local_stt_client_fallback_when_not_installed():
    """Verifies clean fallback behavior when faster-whisper is not loaded."""
    client = LocalWhisperSTTClient()
    client._model = None
    with patch("fluid_voice.stt_local.HAS_FASTER_WHISPER", False):
        result = client.transcribe_audio_bytes(b"RIFF....WAVE")
        assert result == ""
