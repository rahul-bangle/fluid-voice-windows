"""
Tier 1 Tests for fluid_voice.stt_groq (Groq Whisper STT Client).

Covers happy path REST API integration for primary model (whisper-large-v3-turbo),
dynamic fallback to whisper-large-v3, zero-shot Hinglish prompt parameter validation,
connection pooling session reuse, full exception hierarchy mapping, and client payload construction latency.
"""

import time
import pytest
import requests
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
    GROQ_STT_ENDPOINT,
)
from tests.conftest import generate_wav_bytes


@pytest.fixture
def stt_client() -> GroqSTTClient:
    """Fixture providing a fresh GroqSTTClient instance."""
    client = GroqSTTClient(api_key="gsk_tier1_test_key_12345")
    yield client
    client.close()


def test_tier1_primary_model_happy_path(stt_client: GroqSTTClient):
    """Tier 1: Happy path transcription using primary whisper-large-v3-turbo model."""
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "text": "Bhai, meeting kal subah 10:00 AM ko shift kar do.",
        "model": PRIMARY_MODEL,
    }

    with patch.object(stt_client._session, "post", return_value=mock_resp) as mock_post:
        result = stt_client.transcribe(audio_bytes)
        assert result == "Bhai, meeting kal subah 10:00 AM ko shift kar do."
        
        # Verify endpoint and multipart payload arguments
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == GROQ_STT_ENDPOINT
        assert kwargs["data"]["model"] == PRIMARY_MODEL
        assert kwargs["data"]["language"] == "en"
        assert kwargs["data"]["temperature"] == "0.0"
        assert kwargs["data"]["prompt"] == DEFAULT_HINGLISH_PROMPT


def test_tier1_dynamic_model_fallback_on_server_error(stt_client: GroqSTTClient):
    """Tier 1: Dynamic fallback from whisper-large-v3-turbo to whisper-large-v3 when primary fails (500)."""
    audio_bytes = generate_wav_bytes(duration_sec=1.0)

    resp_500 = MagicMock()
    resp_500.status_code = 500
    resp_500.text = '{"error": "Groq LPU node overload"}'

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {"text": "Fallback model successful output"}

    with patch.object(stt_client._session, "post", side_effect=[resp_500, resp_200]) as mock_post:
        transcript = stt_client.transcribe(audio_bytes)
        assert transcript == "Fallback model successful output"
        assert mock_post.call_count == 2

        # First call: Primary model
        call1_data = mock_post.call_args_list[0][1]["data"]
        assert call1_data["model"] == PRIMARY_MODEL

        # Second call: Fallback model
        call2_data = mock_post.call_args_list[1][1]["data"]
        assert call2_data["model"] == FALLBACK_MODEL


def test_tier1_connection_pooling_session_reuse():
    """Tier 1: Verify persistent connection pooling re-uses HTTP session headers across requests."""
    client = GroqSTTClient(api_key="gsk_pool_test_key")
    audio_bytes = generate_wav_bytes(duration_sec=0.5)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"text": "Hello world"}

    # Issue multiple sequential transcribe calls
    with patch.object(client._session, "post", return_value=mock_resp) as mock_post:
        res1 = client.transcribe(audio_bytes)
        res2 = client.transcribe(audio_bytes)
        res3 = client.transcribe(audio_bytes)

        assert res1 == res2 == res3 == "Hello world"
        assert mock_post.call_count == 3
        # Ensure session headers are preserved
        assert client._session.headers["Authorization"] == "Bearer gsk_pool_test_key"
        assert client._session.headers["User-Agent"] == "FluidVoice-Windows/1.0"

    client.close()


def test_tier1_zero_shot_hinglish_prompt_contract():
    """Tier 1: Zero-shot Hinglish system prompt specifies Latin script enforcement for Indian English/Hinglish."""
    custom_hinglish_prompt = (
        "Transcribe Indian English and Hinglish audio accurately, maintaining English characters (Latin script)."
    )
    client = GroqSTTClient(api_key="gsk_test", prompt=custom_hinglish_prompt)
    audio_bytes = generate_wav_bytes(duration_sec=0.5)

    form_data = client._build_form_data(audio_bytes, PRIMARY_MODEL)
    assert form_data["prompt"] == custom_hinglish_prompt
    assert form_data["language"] == "en"
    assert form_data["temperature"] == "0.0"

    client.close()


def test_tier1_exception_hierarchy_mapping(stt_client: GroqSTTClient):
    """Tier 1: Comprehensive verification of REST API HTTP error status code to domain exception mapping."""
    audio_bytes = generate_wav_bytes(duration_sec=0.5)

    error_mappings = [
        (401, InvalidAPIKeyError),
        (429, RateLimitError),
        (400, AudioFormatError),
    ]

    for status_code, expected_exception in error_mappings:
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.text = f"Error {status_code}"

        with patch.object(stt_client._session, "post", return_value=mock_resp):
            with pytest.raises(expected_exception) as exc_info:
                stt_client.transcribe(audio_bytes)
            assert exc_info.value.status_code == status_code


def test_tier1_network_timeout_and_offline_exceptions(stt_client: GroqSTTClient):
    """Tier 1: Network timeout and connection drop raise NetworkTimeoutError and NoInternetError respectively."""
    audio_bytes = generate_wav_bytes(duration_sec=0.5)

    # Timeout
    with patch.object(stt_client._session, "post", side_effect=requests.exceptions.Timeout("Connection read timeout")):
        with pytest.raises(NetworkTimeoutError):
            stt_client.transcribe(audio_bytes)

    # Connection failure (DNS / offline)
    with patch.object(stt_client._session, "post", side_effect=requests.exceptions.ConnectionError("Failed to resolve host")):
        with pytest.raises(NoInternetError):
            stt_client.transcribe(audio_bytes)


def test_tier1_client_payload_construction_latency(stt_client: GroqSTTClient):
    """Tier 1 Performance Budget: Client side request payload & header preparation time must be < 2ms."""
    audio_bytes = generate_wav_bytes(duration_sec=3.0)

    start_time = time.perf_counter()
    iterations = 100
    for _ in range(iterations):
        _ = stt_client._build_form_data(audio_bytes, PRIMARY_MODEL)
        _ = stt_client._build_files(audio_bytes)

    avg_prep_latency_ms = ((time.perf_counter() - start_time) / iterations) * 1000.0
    assert avg_prep_latency_ms < 2.0, f"Payload preparation latency {avg_prep_latency_ms:.3f}ms exceeded 2.0ms budget!"
