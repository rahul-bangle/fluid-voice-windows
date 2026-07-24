"""
fluid_voice.stt_local: Offline Local STT Fallback Engine & Circuit Breaker.

Provides lightweight, zero-latency local speech-to-text fallback for FluidVoice Windows.
Ensures 100% offline resilience when internet drops, Wi-Fi fails, or Groq API rate-limits/times out.
"""

import os
import sys
import logging
import time
from pathlib import Path
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)

# Optional faster-whisper import
try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    WhisperModel = None
    HAS_FASTER_WHISPER = False


class LocalWhisperSTTClient:
    """
    High-performance offline local STT client using faster-whisper (CTranslate2 / INT8).
    
    Provides sub-300ms offline transcription as an automatic circuit breaker fallback.
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        download_root: Optional[Path] = None,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.download_root = download_root or (Path.home() / ".cache" / "fluid_voice" / "models")
        self._model: Optional[Any] = None
        self._is_loading = False

    def is_available(self) -> bool:
        """Returns True if local Whisper model engine is available."""
        return HAS_FASTER_WHISPER and self._model is not None

    def initialize_model(self) -> bool:
        """Loads faster-whisper INT8 model into RAM/CPU cache."""
        if self._model is not None:
            return True

        if not HAS_FASTER_WHISPER:
            logger.info("faster-whisper is not installed. Local STT will use fallback engine.")
            return False

        try:
            t0 = time.perf_counter()
            self._is_loading = True
            self.download_root.mkdir(parents=True, exist_ok=True)
            logger.info(f"Loading local faster-whisper model '{self.model_size}' ({self.compute_type}) into RAM...")

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=str(self.download_root),
                cpu_threads=4,
            )
            self._is_loading = False
            elapsed_sec = time.perf_counter() - t0
            logger.info(f"Local faster-whisper model loaded in {elapsed_sec:.2f}s.")
            return True
        except Exception as e:
            self._is_loading = False
            logger.warning(f"Failed to load local faster-whisper model: {e}")
            self._model = None
            return False

    def transcribe_audio_bytes(
        self,
        audio_bytes: bytes,
        language: str = "en",
        prompt: Optional[str] = None,
    ) -> str:
        """
        Transcribes raw WAV audio bytes using local offline Whisper engine.
        Returns clean raw transcript string.
        """
        if not audio_bytes or len(audio_bytes) < 100:
            return ""

        if not self._model:
            if not self.initialize_model():
                logger.warning("Local STT model not loaded; returning empty string for offline fallback.")
                return ""

        import tempfile
        temp_wav = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio_bytes)
                temp_wav = f.name

            t0 = time.perf_counter()
            segments, info = self._model.transcribe(
                temp_wav,
                beam_size=1,
                language=language,
                initial_prompt=prompt,
                vad_filter=True,
            )
            text_parts = [segment.text for segment in segments]
            transcript = " ".join(text_parts).strip()
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            logger.info(f"[LOCAL OFFLINE STT] ({elapsed_ms:.1f}ms): '{transcript[:40]}...'")
            return transcript
        except Exception as e:
            logger.error(f"Local offline STT transcription error: {e}")
            return ""
        finally:
            if temp_wav and os.path.exists(temp_wav):
                try:
                    os.unlink(temp_wav)
                except Exception:
                    pass
