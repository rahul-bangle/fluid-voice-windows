"""
Unit tests for fluid_voice.stt_groq (Groq Whisper STT Client).

Covers Tier 1 (Happy Path Feature Coverage) & Tier 2 (Boundary & Corner Cases).
Minimum 10 tests.
"""

import requests
import pytest
from unittest.mock import MagicMock, patch

from fluid_voice.stt_groq import (
    GroqSTTClient,
    GroqSTTError,
    InvalidAPIKeyError,
    RateLimitError,
    NetworkTimeoutError,
    NoInternetError,
    AudioFormatError,
    ModelUnavailableError,
    PRIMARY_MODEL,
    FALLBACK_MODEL,
    DEFAULT_HINGLISH_PROMPT,
)
from tests.conftest import generate_wav_bytes


# ============================================================================
# Tier 1: Happy Path Feature Coverage Tests
# ============================================================================

def test_stt_groq_init_valid():
    """Tier 1: Groq API client initialization with valid API key and parameters."""
    client = GroqSTTClient(api_key="gsk_test_12345")
    assert client.api_key == "gsk_test_12345"
    assert client.primary_model == PRIMARY_MODEL
    assert client.fallback_model == FALLBACK_MODEL
    assert client.prompt == DEFAULT_HINGLISH_PROMPT
    assert client.timeout == 1.5
    client.close()


def test_stt_groq_auth_header():
    """Tier 1: API authentication header formatting (Authorization: Bearer <key>)."""
    client = GroqSTTClient(api_key="gsk_secret_key_999")
    assert client._headers["Authorization"] == "Bearer gsk_secret_key_999"
    assert client._headers["User-Agent"] == "FluidVoice-Windows/1.0"
    client.close()


def test_stt_groq_request_formatting_primary():
    """Tier 1: Whisper REST request formatting with primary model and WAV audio payload."""
    client = GroqSTTClient(api_key="gsk_test")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    data = client._build_form_data(audio_bytes, PRIMARY_MODEL)
    files = client._build_files(audio_bytes)

    assert data["model"] == PRIMARY_MODEL
    assert data["temperature"] == "0.0"
    assert data["language"] == "en"
    assert data["response_format"] == "verbose_json"

    assert "file" in files
    assert files["file"][0] == "speech.wav"
    assert files["file"][1] == audio_bytes
    assert files["file"][2] == "audio/wav"
    client.close()


def test_stt_groq_zero_shot_hinglish_prompt():
    """Tier 1: Zero-shot Hinglish system prompt payload is included in form data."""
    custom_prompt = "Transcribe Hinglish audio accurately in English letters."
    client = GroqSTTClient(api_key="gsk_test", prompt=custom_prompt)
    audio_bytes = generate_wav_bytes(duration_sec=0.5)

    data = client._build_form_data(audio_bytes, PRIMARY_MODEL)
    assert data["prompt"] == custom_prompt
    client.close()


def test_stt_groq_response_json_parsing():
    """Tier 1: Successful HTTP 200 response JSON parsing returning transcribed text."""
    client = GroqSTTClient(api_key="gsk_test")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "text": "Bhai meeting prepone kar do 3 PM ko",
        "model": "whisper-large-v3-turbo"
    }

    with patch.object(client._session, "post", return_value=mock_resp) as mock_post:
        result = client.transcribe(audio_bytes)
        assert result == "Bhai meeting prepone kar do 3 PM ko"
        mock_post.assert_called_once()
    client.close()


# ============================================================================
# Tier 2: Boundary & Corner Cases Tests
# ============================================================================

def test_stt_groq_missing_api_key_error():
    """Tier 2: Empty or whitespace-only API key raises InvalidAPIKeyError."""
    with pytest.raises(InvalidAPIKeyError):
        GroqSTTClient(api_key="")

    with pytest.raises(InvalidAPIKeyError):
        GroqSTTClient(api_key="   ")


def test_stt_groq_empty_audio_bytes_error():
    """Tier 2: Passing empty audio bytes payload raises AudioFormatError."""
    client = GroqSTTClient(api_key="gsk_test")
    with pytest.raises(AudioFormatError):
        client.transcribe(b"")
    client.close()


def test_stt_groq_invalid_api_key_401():
    """Tier 2: Invalid API key HTTP 401 response handling raises InvalidAPIKeyError."""
    client = GroqSTTClient(api_key="gsk_invalid_key")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = '{"error": {"message": "Invalid API key"}}'

    with patch.object(client._session, "post", return_value=mock_resp):
        with pytest.raises(InvalidAPIKeyError):
            client.transcribe(audio_bytes)
    client.close()


def test_stt_groq_rate_limit_429():
    """Tier 2: Rate limit HTTP 429 response handling raises RateLimitError."""
    client = GroqSTTClient(api_key="gsk_test")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = '{"error": {"message": "Rate limit exceeded"}}'

    with patch.object(client._session, "post", return_value=mock_resp):
        with pytest.raises(RateLimitError):
            client.transcribe(audio_bytes)
    client.close()


def test_stt_groq_network_timeout_error():
    """Tier 2: Network connection timeout raises NetworkTimeoutError."""
    client = GroqSTTClient(api_key="gsk_test")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    with patch.object(client._session, "post", side_effect=requests.exceptions.Timeout("Request timed out")):
        with pytest.raises(NetworkTimeoutError):
            client.transcribe(audio_bytes)
    client.close()


def test_stt_groq_no_internet_connection_error():
    """Tier 2: Network connection failure raises NoInternetError."""
    client = GroqSTTClient(api_key="gsk_test")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    with patch.object(client._session, "post", side_effect=requests.exceptions.ConnectionError("DNS failure")):
        with pytest.raises(NoInternetError):
            client.transcribe(audio_bytes)
    client.close()


def test_stt_groq_model_fallback_on_500():
    """Tier 2: Network / Server 500 error on primary model triggers automatic fallback to whisper-large-v3."""
    client = GroqSTTClient(api_key="gsk_test")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    resp_500 = MagicMock()
    resp_500.status_code = 500
    resp_500.text = "Internal Server Error"

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"text": "Fallback model successful transcription"}

    with patch.object(client._session, "post", side_effect=[resp_500, resp_200]) as mock_post:
        result = client.transcribe(audio_bytes)
        assert result == "Fallback model successful transcription"
        assert mock_post.call_count == 2
        # Verify second call used fallback model
        second_call_data = mock_post.call_args_list[1][1]["data"]
        assert second_call_data["model"] == FALLBACK_MODEL
    client.close()


def test_stt_groq_malformed_json_response():
    """Tier 2: Malformed JSON response raises AudioFormatError."""
    client = GroqSTTClient(api_key="gsk_test")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON token")

    with patch.object(client._session, "post", return_value=mock_resp):
        with pytest.raises(AudioFormatError):
            client.transcribe(audio_bytes)
    client.close()


def test_stt_groq_empty_transcript_response_handling():
    """Tier 2: Response JSON with empty transcript text returns empty string gracefully."""
    client = GroqSTTClient(api_key="gsk_test")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"text": "   "}

    with patch.object(client._session, "post", return_value=mock_resp):
        result = client.transcribe(audio_bytes)
        assert result == ""
    client.close()


def test_stt_groq_both_models_fail_raises_model_unavailable():
    """Tier 2: Dual model failure (500 on primary and 503 on fallback) raises ModelUnavailableError."""
    client = GroqSTTClient(api_key="gsk_test")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    resp_500 = MagicMock()
    resp_500.status_code = 500
    resp_500.text = "Internal Server Error Primary"

    resp_503 = MagicMock()
    resp_503.status_code = 503
    resp_503.text = "Service Unavailable Fallback"

    with patch.object(client._session, "post", side_effect=[resp_500, resp_503]):
        with pytest.raises(ModelUnavailableError) as exc_info:
            client.transcribe(audio_bytes)
        assert exc_info.value.status_code == 503
        assert "Service Unavailable Fallback" in str(exc_info.value)
    client.close()


def test_stt_groq_400_bad_request_raises_audio_format_error():
    """Tier 2: HTTP 400 response from Groq API raises AudioFormatError with response attached."""
    client = GroqSTTClient(api_key="gsk_test")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = '{"error": {"message": "Invalid audio encoding"}}'

    with patch.object(client._session, "post", return_value=mock_resp):
        with pytest.raises(AudioFormatError) as exc_info:
            client.transcribe(audio_bytes)
        assert exc_info.value.status_code == 400
        assert "Invalid audio encoding" in str(exc_info.value)
    client.close()


def test_stt_groq_non_dict_json_response():
    """Tier 2: JSON response returning a non-dictionary (e.g. list) raises AudioFormatError."""
    client = GroqSTTClient(api_key="gsk_test")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = ["unexpected", "list", "response"]

    with patch.object(client._session, "post", return_value=mock_resp):
        with pytest.raises(AudioFormatError):
            client.transcribe(audio_bytes)
    client.close()


def test_stt_groq_close_session():
    """Tier 1: Explicit client close releases session resources cleanly."""
    client = GroqSTTClient(api_key="gsk_test")
    with patch.object(client._session, "close") as mock_close:
        client.close()
        mock_close.assert_called_once()


def test_stt_groq_exception_hierarchy_attributes():
    """Tier 1: Verify custom exception hierarchy preserves status_code and response object."""
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    err = RateLimitError("Rate limit hit", response=mock_resp)
    assert isinstance(err, GroqSTTError)
    assert err.status_code == 429
    assert err.response == mock_resp


def test_stt_groq_verbose_json_hallucination_dropping():
    """R1: Silently drops transcription if no_speech_prob > 0.60, avg_logprob < -1.0, or compression_ratio > 2.4."""
    client = GroqSTTClient(api_key="gsk_test")
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    # Case 1: no_speech_prob > 0.60
    mock_resp1 = MagicMock()
    mock_resp1.status_code = 200
    mock_resp1.json.return_value = {
        "text": "Hallucinated silence text",
        "no_speech_prob": 0.75,
        "avg_logprob": -0.2,
        "compression_ratio": 1.1,
    }

    with patch.object(client._session, "post", return_value=mock_resp1):
        assert client.transcribe(audio_bytes) == ""

    # Case 2: avg_logprob < -1.0
    mock_resp2 = MagicMock()
    mock_resp2.status_code = 200
    mock_resp2.json.return_value = {
        "text": "Low confidence hallucination",
        "no_speech_prob": 0.10,
        "avg_logprob": -1.35,
        "compression_ratio": 1.1,
    }

    with patch.object(client._session, "post", return_value=mock_resp2):
        assert client.transcribe(audio_bytes) == ""

    # Case 3: compression_ratio > 2.4
    mock_resp3 = MagicMock()
    mock_resp3.status_code = 200
    mock_resp3.json.return_value = {
        "text": "Repeated hallucination phrase " * 10,
        "no_speech_prob": 0.10,
        "avg_logprob": -0.3,
        "compression_ratio": 2.8,
    }

    with patch.object(client._session, "post", return_value=mock_resp3):
        assert client.transcribe(audio_bytes) == ""

    # Case 4: Normal valid response
    mock_resp4 = MagicMock()
    mock_resp4.status_code = 200
    mock_resp4.json.return_value = {
        "text": "Valid user speech",
        "no_speech_prob": 0.05,
        "avg_logprob": -0.2,
        "compression_ratio": 1.2,
    }

    with patch.object(client._session, "post", return_value=mock_resp4):
        assert client.transcribe(audio_bytes) == "Valid user speech"

    client.close()

