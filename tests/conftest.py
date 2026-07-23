"""
FluidVoice Windows — Shared Pytest Fixtures and Mock Infrastructure

This module provides reusable test fixtures for unit, integration, and E2E tests:
1. qapp: Headless PyQt6 QApplication instance.
2. mock_audio_stream: Simulated sounddevice audio recording stream producing valid WAV PCM data.
3. mock_groq_api: Interceptor & mock builder for Groq REST API (whisper-large-v3-turbo).
4. mock_win32_paster: Win32 active window & clipboard/keyboard auto-paster mock.
5. hinglish_test_dataset: Standardized test cases for Hinglish post-processing verification.
"""

import io
import math
import os
import struct
import sys
import wave
from typing import Any, Dict, Generator, List, Optional
from unittest.mock import MagicMock, patch

import pytest

# Ensure QT operates in headless offscreen mode during tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(autouse=True)
def isolate_test_config(tmp_path, monkeypatch):
    """Isolates config directory, keyring storage, and environment variables for clean test runs."""
    test_config_dir = tmp_path / "FluidVoice_TestConfig"
    test_config_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LOCALAPPDATA", str(test_config_dir))
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    fake_keyring_store = {}

    def fake_set_password(service, username, password):
        fake_keyring_store[(service, username)] = password

    def fake_get_password(service, username):
        return fake_keyring_store.get((service, username))

    def fake_delete_password(service, username):
        fake_keyring_store.pop((service, username), None)

    monkeypatch.setattr("keyring.set_password", fake_set_password, raising=False)
    monkeypatch.setattr("keyring.get_password", fake_get_password, raising=False)
    monkeypatch.setattr("keyring.delete_password", fake_delete_password, raising=False)
    monkeypatch.setattr("fluid_voice.config.keyring.set_password", fake_set_password, raising=False)
    monkeypatch.setattr("fluid_voice.config.keyring.get_password", fake_get_password, raising=False)
    monkeypatch.setattr("fluid_voice.config.keyring.delete_password", fake_delete_password, raising=False)

    yield test_config_dir


# ============================================================================
# 1. Headless PyQt6 Application Fixture
# ============================================================================

@pytest.fixture(scope="session")
def qapp() -> Generator[Any, None, None]:
    """
    Provides a singleton headless PyQt6 QApplication instance for UI testing.
    Falls back gracefully if PyQt6 is not installed or GUI is headless.
    """
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv + ["-platform", "offscreen"])
        yield app
    except ImportError:
        # Fallback dummy app if PyQt6 is not installed in current test environment
        dummy_app = MagicMock(name="DummyQApplication")
        yield dummy_app


# ============================================================================
# 2. Mock Sounddevice Recording Stream Fixture
# ============================================================================

def generate_wav_bytes(
    duration_sec: float = 1.0,
    sample_rate: int = 16000,
    frequency: float = 440.0,
    volume: float = 0.5,
) -> bytes:
    """
    Utility function generating valid 16kHz mono 16-bit PCM WAV audio bytes.
    Used to simulate live mic recording payloads without external audio dependencies.
    """
    num_samples = int(duration_sec * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)       # Mono
        wav_file.setsampwidth(2)      # 16-bit PCM (2 bytes)
        wav_file.setframerate(sample_rate)
        
        # Write sine wave audio samples
        sample_data = bytearray()
        for i in range(num_samples):
            sample_val = int(volume * 32767.0 * math.sin(2.0 * math.pi * frequency * (i / sample_rate)))
            sample_data.extend(struct.pack("<h", max(-32768, min(32767, sample_val))))
        
        wav_file.writeframes(bytes(sample_data))
    
    return buf.getvalue()


def generate_silent_wav_bytes(
    duration_sec: float = 1.0,
    sample_rate: int = 16000,
) -> bytes:
    """Utility function generating silent (zero-amplitude) PCM WAV audio bytes."""
    return generate_wav_bytes(duration_sec=duration_sec, sample_rate=sample_rate, volume=0.0)


class MockAudioStreamController:
    """Simulates sounddevice audio stream controls and state inspection."""
    
    def __init__(self) -> None:
        self.is_recording: bool = False
        self.sample_rate: int = 16000
        self.channels: int = 1
        self.recorded_chunks: List[bytes] = []
        self.silence_detected: bool = False
        self.duration_cap_exceeded: bool = False

    def start(self) -> None:
        self.is_recording = True
        self.recorded_chunks.clear()

    def stop(self) -> bytes:
        self.is_recording = False
        if not self.recorded_chunks:
            return generate_wav_bytes(duration_sec=1.0, sample_rate=self.sample_rate)
        return b"".join(self.recorded_chunks)

    def inject_audio_data(self, duration_sec: float = 1.0, silent: bool = False) -> bytes:
        chunk = generate_silent_wav_bytes(duration_sec, self.sample_rate) if silent else generate_wav_bytes(duration_sec, self.sample_rate)
        self.recorded_chunks.append(chunk)
        return chunk


@pytest.fixture
def mock_audio_stream() -> Generator[MockAudioStreamController, None, None]:
    """
    Pytest fixture providing a mock audio stream controller and patching sounddevice functions.
    """
    controller = MockAudioStreamController()
    
    with patch("sounddevice.InputStream") as mock_input_stream, \
         patch("sounddevice.rec") as mock_rec, \
         patch("sounddevice.stop") as mock_stop, \
         patch("sounddevice.wait") as mock_wait:
        
        mock_rec.side_effect = lambda frames, samplerate, channels: controller.inject_audio_data()
        mock_stop.side_effect = lambda: controller.stop()
        mock_wait.return_value = None
        
        yield controller


# ============================================================================
# 3. Mock Groq REST API Response Fixture
# ============================================================================

class MockGroqHttpResponse:
    """Simulates an HTTP response from Groq API (e.g. requests.Response or httpx.Response)."""
    
    def __init__(self, status_code: int = 200, json_data: Optional[Dict[str, Any]] = None, text: str = "") -> None:
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text or (str(json_data) if json_data else "")

    def json(self) -> Dict[str, Any]:
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            from unittest.mock import Mock
            mock_err = Mock()
            mock_err.status_code = self.status_code
            raise RuntimeError(f"HTTP Error {self.status_code}: {self.text}")


class MockGroqApiClient:
    """Controller for mocking Groq STT API request outcomes."""
    
    def __init__(self) -> None:
        self.default_transcription: str = "Bhai meeting prepone kar do 3 PM ko"
        self.status_code: int = 200
        self.error_message: Optional[str] = None
        self.request_history: List[Dict[str, Any]] = []

    def set_success_response(self, transcribed_text: str) -> None:
        self.status_code = 200
        self.default_transcription = transcribed_text
        self.error_message = None

    def set_error_response(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.error_message = message

    def handle_request(self, url: str, **kwargs: Any) -> MockGroqHttpResponse:
        self.request_history.append({"url": url, "kwargs": kwargs})
        
        if self.status_code == 200:
            return MockGroqHttpResponse(
                status_code=200,
                json_data={"text": self.default_transcription, "model": "whisper-large-v3-turbo"}
            )
        elif self.status_code == 401:
            return MockGroqHttpResponse(
                status_code=401,
                json_data={"error": {"message": self.error_message or "Invalid API Key"}}
            )
        elif self.status_code == 429:
            return MockGroqHttpResponse(
                status_code=429,
                json_data={"error": {"message": self.error_message or "Rate limit exceeded"}}
            )
        else:
            return MockGroqHttpResponse(
                status_code=self.status_code,
                json_data={"error": {"message": self.error_message or "Internal Server Error"}}
            )


@pytest.fixture
def mock_groq_api() -> Generator[MockGroqApiClient, None, None]:
    """
    Pytest fixture patching network requests to Groq REST API endpoint.
    """
    api_mock = MockGroqApiClient()
    
    # Patch HTTP clients (requests.post or httpx.post if present)
    with patch("requests.post", side_effect=api_mock.handle_request), \
         patch("requests.Session.post", side_effect=api_mock.handle_request):
        yield api_mock


# ============================================================================
# 4. Mock Win32 Active Window & Clipboard Auto-Paster Fixture
# ============================================================================

class MockWin32PasterController:
    """Simulates Win32 GetForegroundWindow, clipboard backup/restore, and key injection."""
    
    def __init__(self) -> None:
        self.active_window_handle: int = 0x12345
        self.active_window_title: str = "VS Code - main.py"
        self.clipboard_content: str = "Original Clipboard Content"
        self.pasted_history: List[str] = []
        self.clipboard_restored: bool = False

    def set_active_window(self, handle: int, title: str) -> None:
        self.active_window_handle = handle
        self.active_window_title = title

    def paste_text(self, text: str) -> bool:
        # Backup clipboard, set text, trigger Ctrl+V, restore clipboard
        backup = self.clipboard_content
        self.clipboard_content = text
        self.pasted_history.append(text)
        # Restore clipboard
        self.clipboard_content = backup
        self.clipboard_restored = True
        return True


@pytest.fixture
def mock_win32_paster() -> Generator[MockWin32PasterController, None, None]:
    """
    Pytest fixture patching Win32 GUI calls and keyboard injection.
    """
    controller = MockWin32PasterController()
    
    mock_win32gui = MagicMock()
    mock_win32gui.GetForegroundWindow.side_effect = lambda: controller.active_window_handle
    mock_win32gui.GetWindowText.side_effect = lambda hwnd: controller.active_window_title
    
    with patch.dict("sys.modules", {"win32gui": mock_win32gui, "win32clipboard": MagicMock()}):
        yield controller


# ============================================================================
# 5. Hinglish Test Data Constants Fixture
# ============================================================================

HINGLISH_TEST_DATA = {
    "idioms": [
        {
            "input": "bhai please prepone the meeting to 3 PM",
            "expected": "Bhai, please reschedule the meeting to 3:00 PM.",
            "category": "Indian English Idioms / Time"
        },
        {
            "input": "do one thing send me the code on slack",
            "expected": "Here's an idea: send me the code on Slack.",
            "category": "Indian English Idioms"
        },
        {
            "input": "i will revert back to you by tomorrow",
            "expected": "I will reply to you by tomorrow.",
            "category": "Redundant Expression Normalization"
        },
        {
            "input": "he is currently out of station",
            "expected": "He is currently out of town.",
            "category": "Idiomatic Substitution"
        }
    ],
    "numbers_and_currency": [
        {
            "input": "the budget is 15 lakh rupees",
            "expected": "The budget is Rs 15,00,000.",
            "category": "Lakh Currency Formatting"
        },
        {
            "input": "company revenue crossed 10 crore rupees this year",
            "expected": "Company revenue crossed Rs 100,000,000 this year.",
            "category": "Crore Currency Formatting"
        },
        {
            "input": "add 18 percent gst on 500 rupees",
            "expected": "Add 18% GST on Rs 500.",
            "category": "Percentage and Currency"
        }
    ],
    "code_dictation": [
        {
            "input": "def calculate total function me error handler add karo",
            "expected": "def calculate_total function me error handler add karo.",
            "category": "IDE Code Context"
        },
        {
            "input": "git commit message main feature fix added write karo",
            "expected": "Git commit message 'feature fix added' write karo.",
            "category": "CLI / Git Context"
        }
    ],
    "punctuation_and_capitalization": [
        {
            "input": "hello bhai how are you doing today",
            "expected": "Hello bhai, how are you doing today?",
            "category": "Question Auto-Punctuation"
        },
        {
            "input": "yeah everything is working fine thanks",
            "expected": "Yeah, everything is working fine. Thanks!",
            "category": "Sentence Capitalization"
        }
    ],
    "boundary_cases": [
        {
            "input": "",
            "expected": "",
            "category": "Empty Input"
        },
        {
            "input": "   ",
            "expected": "",
            "category": "Whitespace Only Input"
        },
        {
            "input": "a",
            "expected": "A.",
            "category": "Single Character Input"
        }
    ]
}


@pytest.fixture
def hinglish_test_dataset() -> Dict[str, List[Dict[str, str]]]:
    """
    Returns the comprehensive Hinglish test dataset for post-processor validation.
    """
    return HINGLISH_TEST_DATA
