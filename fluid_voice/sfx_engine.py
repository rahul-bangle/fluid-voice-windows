"""
FluidVoice SFX Feedback Engine.

Provides zero-latency acoustic feedback chimes for key press (recording start),
key release (recording stop), auto-paste completion, and error states.
Saves pre-generated WAV files locally to ensure SND_FILENAME | SND_ASYNC works
reliably on all audio devices (including Bluetooth earbuds).
"""

import math
import wave
import struct
import tempfile
import logging
from pathlib import Path
from typing import Optional

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

logger = logging.getLogger(__name__)


class SFXEngine:
    """Low-latency acoustic feedback engine using Windows winsound SND_FILENAME async playback."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._sound_files = {}
        self._sfx_dir = Path(tempfile.gettempdir()) / "FluidVoice_SFX"
        self._sfx_dir.mkdir(parents=True, exist_ok=True)
        self._pregenerate_chimes()

    def set_enabled(self, enabled: bool) -> None:
        """Toggles SFX audio feedback on/off."""
        self.enabled = enabled

    def _generate_sine_wav_file(self, filename: str, frequency: float, duration_ms: int, volume: float = 0.3) -> Path:
        """Generates a WAV audio file on disk for async SND_FILENAME playback."""
        sample_rate = 22050
        num_samples = int(sample_rate * (duration_ms / 1000.0))
        audio_data = bytearray()

        for i in range(num_samples):
            t = float(i) / sample_rate
            # Apply smooth envelope fade-out to prevent audio pops
            envelope = 1.0
            if i > num_samples - 200:
                envelope = max(0.0, (num_samples - i) / 200.0)

            sample_val = int(32767 * volume * envelope * math.sin(2 * math.pi * frequency * t))
            audio_data.extend(struct.pack("<h", sample_val))

        file_path = self._sfx_dir / f"{filename}.wav"
        data_size = len(audio_data)
        file_size = 36 + data_size

        wav_buf = bytearray()
        wav_buf.extend(b"RIFF")
        wav_buf.extend(struct.pack("<I", file_size))
        wav_buf.extend(b"WAVEfmt ")
        wav_buf.extend(struct.pack("<I", 16))          # Subchunk1Size (16 for PCM)
        wav_buf.extend(struct.pack("<H", 1))           # AudioFormat (1 for PCM)
        wav_buf.extend(struct.pack("<H", 1))           # NumChannels (1 for Mono)
        wav_buf.extend(struct.pack("<I", sample_rate)) # SampleRate
        wav_buf.extend(struct.pack("<I", sample_rate * 2)) # ByteRate
        wav_buf.extend(struct.pack("<H", 2))           # BlockAlign
        wav_buf.extend(struct.pack("<H", 16))          # BitsPerSample
        wav_buf.extend(b"data")
        wav_buf.extend(struct.pack("<I", data_size))
        wav_buf.extend(audio_data)

        file_path.write_bytes(bytes(wav_buf))
        return file_path

    def _pregenerate_chimes(self) -> None:
        """Pre-generates audio chime WAV files on disk."""
        try:
            # Start recording chime: Bright 880Hz (A5) 80ms ping
            self._sound_files["start"] = self._generate_sine_wav_file("start", 880, 80, volume=0.35)
            # Stop recording chime: Soft 660Hz (E5) 80ms tone
            self._sound_files["stop"] = self._generate_sine_wav_file("stop", 660, 80, volume=0.30)
            # Paste success chime: Bright 1046Hz (C6) 100ms ping
            self._sound_files["paste"] = self._generate_sine_wav_file("paste", 1046, 100, volume=0.40)
            # Error chime: Low 330Hz (E4) 120ms warning tone
            self._sound_files["error"] = self._generate_sine_wav_file("error", 330, 120, volume=0.40)
        except Exception as e:
            logger.warning(f"Failed to pregenerate SFX chimes: {e}")

    def play(self, sound_name: str) -> None:
        """Plays a pre-generated acoustic chime asynchronously through Bluetooth/Speakers."""
        if not self.enabled or not HAS_WINSOUND:
            return

        file_path = self._sound_files.get(sound_name)
        if not file_path or not file_path.exists():
            return

        try:
            # PlaySound with SND_FILENAME | SND_ASYNC for zero-latency non-blocking playback
            winsound.PlaySound(str(file_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            logger.warning(f"Failed to play SFX '{sound_name}': {e}")
