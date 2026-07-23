"""
fluid_voice.audio: Low-RAM Audio Recorder with Silence VAD and Duration Cap.
"""

import io
import logging
import wave
from typing import List, Optional
import numpy as np
try:
    import sounddevice as sd
except ImportError:
    from unittest.mock import MagicMock
    sd = MagicMock()
from PyQt6.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)


class AudioRecorder(QObject):
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal(str)  # reason: "manual", "vad_silence", "max_duration", "initial_silence"
    audio_level_changed = pyqtSignal(float)  # 0.0 to 1.0 for overlay widget
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        silence_threshold_rms: float = 200.0,
        speech_threshold_rms: float = 300.0,
        silence_duration_sec: float = 1.2,
        max_duration_sec: float = 30.0,
        device: Optional[int] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._sample_rate = sample_rate
        self._channels = channels
        self._silence_threshold = silence_threshold_rms
        self._speech_threshold = speech_threshold_rms
        self._silence_duration_sec = silence_duration_sec
        self._max_duration_sec = max_duration_sec
        self._device = device

        self._stream: Optional[sd.InputStream] = None
        self._is_recording = False
        self._pcm_chunks: List[np.ndarray] = []
        self._total_samples = 0
        self._max_samples = int(sample_rate * max_duration_sec)

        # VAD State Variables
        self._speech_detected = False
        self._silence_samples_count = 0
        self._initial_silence_samples_count = 0
        self._speech_samples_count = 0
        self._stop_reason = "manual"

    def start_recording(self) -> bool:
        if self._is_recording:
            return True

        self._pcm_chunks = []
        self._total_samples = 0
        self._speech_detected = False
        self._silence_samples_count = 0
        self._initial_silence_samples_count = 0
        self._speech_samples_count = 0
        self._stop_reason = "manual"

        try:
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

            self._stream = sd.InputStream(
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="int16",
                blocksize=1024,
                device=self._device,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._is_recording = True
            self.recording_started.emit()
            logger.info("AudioRecorder started recording (fresh clean stream)")
            return True
        except Exception as e:
            err_msg = f"Failed to start audio stream: {e}"
            logger.error(err_msg)
            self.error_occurred.emit(err_msg)
            return False

    def stop_recording(self) -> bytes:
        """Stops audio stream and returns 16-bit Mono 16kHz WAV byte stream."""
        if not self._is_recording:
            return self._encode_wav(self._pcm_chunks)

        self._is_recording = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning(f"Error stopping stream: {e}")
            self._stream = None

        wav_bytes = self._encode_wav(self._pcm_chunks)
        self.recording_stopped.emit(self._stop_reason)
        logger.info(f"AudioRecorder stopped ({self._stop_reason}). Recorded {len(wav_bytes)} WAV bytes.")
        return wav_bytes

    def is_recording(self) -> bool:
        return self._is_recording

    def get_audio_devices(self) -> List[dict]:
        """Query available audio input devices."""
        try:
            devices = sd.query_devices()
            input_devices = []
            for i, dev in enumerate(devices):
                if dev.get("max_input_channels", 0) > 0:
                    input_devices.append({
                        "id": i,
                        "name": dev.get("name", f"Device {i}"),
                        "channels": dev.get("max_input_channels", 1),
                        "default_samplerate": dev.get("default_samplerate", 16000),
                    })
            return input_devices
        except Exception as e:
            logger.error(f"Error querying audio devices: {e}")
            return []

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: dict, status: sd.CallbackFlags):
        if not self._is_recording:
            return

        if status:
            logger.warning(f"Audio stream status flag: {status}")

        chunk = indata.copy()
        self._pcm_chunks.append(chunk)
        self._total_samples += frames

        # Calculate chunk RMS
        samples = chunk.flatten().astype(np.float32)
        rms = float(np.sqrt(np.mean(samples ** 2))) if len(samples) > 0 else 0.0

        # Emit audio level normalized (0.0 to 1.0)
        norm_level = min(1.0, max(0.0, rms / 3000.0))
        self.audio_level_changed.emit(norm_level)

        # 1. Max duration check
        if self._total_samples >= self._max_samples:
            self._stop_reason = "max_duration"
            self._is_recording = False
            return

        # 2. Silence VAD State Machine
        if not self._speech_detected:
            if rms >= self._speech_threshold:
                self._speech_detected = True
                self._speech_samples_count += frames
            else:
                self._initial_silence_samples_count += frames
                # If no speech detected for > 5 seconds, auto-stop
                if self._initial_silence_samples_count >= int(self._sample_rate * 5.0):
                    self._stop_reason = "initial_silence"
                    self._is_recording = False
        else:
            self._speech_samples_count += frames
            if rms < self._silence_threshold:
                self._silence_samples_count += frames
                # Check if silence sustained for required duration (e.g. 1.2s)
                if (
                    self._silence_samples_count >= int(self._sample_rate * self._silence_duration_sec)
                    and self._speech_samples_count >= int(self._sample_rate * 0.4)
                ):
                    self._stop_reason = "vad_silence"
                    self._is_recording = False
            else:
                self._silence_samples_count = 0

    def _encode_wav(self, chunks: List[np.ndarray]) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self._channels)
            wf.setsampwidth(2)  # 16-bit PCM
            wf.setframerate(self._sample_rate)
            if chunks:
                combined = np.concatenate(chunks, axis=0)
                # Automatic Gain Control (AGC) & Software Audio Booster
                max_val = float(np.max(np.abs(combined)))
                if 0 < max_val < 24000.0:
                    # Boost quiet speech up to 4x (400% gain boost) to target ~85% peak level (28,000)
                    boost_factor = min(4.0, 28000.0 / max_val)
                    boosted = np.clip(combined.astype(np.float32) * boost_factor, -32768, 32767).astype(np.int16)
                    pcm_data = boosted.tobytes()
                else:
                    pcm_data = combined.tobytes()
                wf.writeframes(pcm_data)
            else:
                wf.writeframes(b"")
        return buffer.getvalue()
