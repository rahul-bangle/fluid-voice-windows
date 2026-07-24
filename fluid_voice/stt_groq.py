"""
Groq Whisper Speech-to-Text (STT) Client for FluidVoice Windows.

Interfaces with Groq's OpenAI-compatible audio transcription REST API:
- Endpoint: https://api.groq.com/openai/v1/audio/transcriptions
- Models: whisper-large-v3-turbo (primary) with fallback to whisper-large-v3
- Optimizations: Connection pooling & request formatting (<400ms API response latency)
- Hinglish Support: Zero-shot prompt maintaining Latin script characters
"""

import logging
import time
from typing import Any, List, Optional, Tuple
import requests

from fluid_voice.config import Top8PromptRanker, DEFAULT_HINGLISH_PROMPT

logger = logging.getLogger(__name__)

# Constants
GROQ_STT_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
PRIMARY_MODEL = "whisper-large-v3-turbo"
FALLBACK_MODEL = "whisper-large-v3"
DEFAULT_TIMEOUT_SECONDS = 1.5

DEFAULT_ENGLISH_PROMPT = (
    "Hi Rahul, how may I help you today? Please deploy the latest Docker container to Kubernetes "
    "and review the pull request. Everything is working smoothly. Thanks!"
)
DEFAULT_HINGLISH_PROMPT = DEFAULT_ENGLISH_PROMPT


class GroqSTTError(Exception):
    """Base exception for Groq STT client errors."""

    def __init__(self, message: str, response: Optional[requests.Response] = None):
        super().__init__(message)
        self.response = response
        self.status_code = response.status_code if response is not None else None


class InvalidAPIKeyError(GroqSTTError):
    """Raised when Groq API key is missing or invalid (401)."""
    pass


class RateLimitError(GroqSTTError):
    """Raised when Groq rate limits or quotas are exceeded (429)."""
    pass


class NetworkTimeoutError(GroqSTTError):
    """Raised when the HTTP request times out."""
    pass


class NoInternetError(GroqSTTError):
    """Raised when network connection fails (DNS/Offline)."""
    pass


class AudioFormatError(GroqSTTError):
    """Raised when audio payload is rejected as invalid (400)."""
    pass


class ModelUnavailableError(GroqSTTError):
    """Raised when primary and fallback models fail on Groq servers."""
    pass


class GroqSTTClient:
    """
    High-performance REST API client for Groq Whisper STT.
    
    Supports audio transcription with automatic model fallback, zero-shot Hinglish prompt injection,
    and HTTP connection pooling.
    """

    def __init__(
        self,
        api_key: str,
        primary_model: str = PRIMARY_MODEL,
        fallback_model: str = FALLBACK_MODEL,
        prompt: str = DEFAULT_HINGLISH_PROMPT,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        language: Optional[str] = "en",
        session: Optional[requests.Session] = None,
    ):
        if not api_key or not api_key.strip():
            raise InvalidAPIKeyError("Groq API key must not be empty.")

        self.api_key = api_key.strip()
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.prompt = prompt
        self.timeout = timeout
        self.language = language

        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "FluidVoice-Windows/1.0",
        }
        self._session = session or requests.Session()
        self._session.headers.update(self._headers)

        # Pre-warm TCP/TLS connection in background to eliminate 1.2s cold start delay on first dictation
        import threading
        threading.Thread(target=self._prewarm_connection, daemon=True).start()

    def _prewarm_connection(self) -> None:
        try:
            self._session.head("https://api.groq.com/openai/v1/models", timeout=2.0)
        except Exception:
            pass

    def close(self) -> None:
        """Closes the HTTP session."""
        if self._session:
            self._session.close()

    def update_prompt_from_memory(
        self,
        memory_engine: Optional[Any] = None,
        context: Optional[Any] = None,
        terms: Optional[List[str]] = None,
    ) -> str:
        """
        Updates self.prompt using Context-Aware Top-8 Prompt Ranker (<150 token cap).
        """
        self.prompt = Top8PromptRanker.rank_and_build_prompt(
            base_prompt=self.prompt,
            memory_engine=memory_engine,
            context=context,
            terms=terms,
        )
        return self.prompt

    def _build_form_data(self, audio_bytes: bytes, model: str) -> dict:
        """Constructs multipart form data dictionary for API request."""
        if not audio_bytes:
            raise AudioFormatError("Audio bytes payload cannot be empty.")

        data = {
            "model": model,
            "prompt": self.prompt,
            "temperature": "0.0",
            "response_format": "verbose_json",
        }
        if self.language:
            data["language"] = self.language
        return data

    def _build_files(self, audio_bytes: bytes) -> dict:
        """Constructs files dict for multipart/form-data upload."""
        return {
            "file": ("speech.wav", audio_bytes, "audio/wav")
        }

    def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribe WAV audio bytes synchronously using Groq Whisper REST API.

        Args:
            audio_bytes: In-memory WAV binary data (16kHz 16-bit Mono PCM).
            sample_rate: Audio sampling rate (default 16000).

        Returns:
            Transcribed text string.

        Raises:
            InvalidAPIKeyError, RateLimitError, NetworkTimeoutError,
            NoInternetError, AudioFormatError, ModelUnavailableError
        """
        if not audio_bytes:
            raise AudioFormatError("Audio bytes payload cannot be empty.")

        start_time = time.perf_counter()

        # Primary attempt with whisper-large-v3-turbo
        try:
            return self._send_request(audio_bytes, self.primary_model, start_time)
        except (ModelUnavailableError, requests.HTTPError) as e:
            status_code = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", 500)
            if status_code >= 500 or status_code == 404:
                logger.warning(
                    f"Primary model {self.primary_model} failed (HTTP {status_code}). "
                    f"Retrying with fallback model {self.fallback_model}..."
                )
                return self._send_request(audio_bytes, self.fallback_model, start_time)
            raise

    def _send_request(self, audio_bytes: bytes, model: str, start_time: float) -> str:
        """Executes HTTP POST to Groq API endpoint."""
        files = self._build_files(audio_bytes)
        data = self._build_form_data(audio_bytes, model)

        try:
            response = self._session.post(
                GROQ_STT_ENDPOINT,
                files=files,
                data=data,
                timeout=self.timeout,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.debug(f"Groq API [{model}] response time: {elapsed_ms:.1f}ms (HTTP {response.status_code})")

            if response.status_code == 200:
                try:
                    result = response.json()
                except Exception as json_err:
                    raise AudioFormatError(f"Malformed JSON response from Groq API: {json_err}") from json_err

                if not isinstance(result, dict):
                    raise AudioFormatError("Malformed JSON response structure from Groq API")

                # Parse verbose_json metrics
                no_speech_prob = float(result.get("no_speech_prob", 0.0))
                avg_logprob = float(result.get("avg_logprob", 0.0))
                compression_ratio = float(result.get("compression_ratio", 1.0))

                segments = result.get("segments")
                if segments and isinstance(segments, list) and len(segments) > 0:
                    ns_probs = [float(s.get("no_speech_prob", 0.0)) for s in segments if isinstance(s, dict) and "no_speech_prob" in s]
                    if ns_probs:
                        no_speech_prob = max(ns_probs)

                    logprobs = [float(s.get("avg_logprob", 0.0)) for s in segments if isinstance(s, dict) and "avg_logprob" in s]
                    if logprobs:
                        avg_logprob = sum(logprobs) / len(logprobs)

                    comp_ratios = [float(s.get("compression_ratio", 1.0)) for s in segments if isinstance(s, dict) and "compression_ratio" in s]
                    if comp_ratios:
                        compression_ratio = max(comp_ratios)

                # Silently drop transcription if hallucination metrics exceed threshold
                if no_speech_prob > 0.60 or avg_logprob < -1.0 or compression_ratio > 2.4:
                    logger.info(
                        f"Dropping hallucinated STT transcript: no_speech_prob={no_speech_prob:.2f}, "
                        f"avg_logprob={avg_logprob:.2f}, compression_ratio={compression_ratio:.2f}"
                    )
                    return ""

                text = result.get("text", "")
                return text.strip() if isinstance(text, str) else ""

            self._handle_http_error(response, model)
            return ""

        except requests.exceptions.Timeout as e:
            raise NetworkTimeoutError(f"Groq API request timed out after {self.timeout}s: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise NoInternetError(f"Failed to connect to Groq API ({GROQ_STT_ENDPOINT}): {e}") from e

    def _handle_http_error(self, response: requests.Response, model: str) -> None:
        """Maps HTTP error status codes to domain exceptions."""
        status = response.status_code
        err_text = response.text or ""

        if status == 401:
            raise InvalidAPIKeyError("Invalid or missing Groq API Key. Please check your config.", response=response)
        elif status == 429:
            raise RateLimitError("Groq API rate limit or quota exceeded. Please try again later.", response=response)
        elif status == 400:
            raise AudioFormatError(f"Groq API rejected audio format: {err_text}", response=response)
        elif status >= 500 or status == 404:
            raise ModelUnavailableError(f"Groq model {model} service unavailable (HTTP {status}): {err_text}", response=response)
        else:
            raise GroqSTTError(f"Groq API HTTP {status}: {err_text}", response=response)
