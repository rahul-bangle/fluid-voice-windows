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

    def _generate_harmonic_wav_file(
        self, 
        filename: str, 
        frequencies: list[float], 
        duration_ms: int, 
        volume: float = 0.15
    ) -> Path:
        """
        Generates soft, multi-harmonic metallic acoustic chimes (Wispr Flow style)
        with smooth Exponential Attack/Decay envelope (Zero harshness, zero pop).
        """
        sample_rate = 44100
        num_samples = int(sample_rate * (duration_ms / 1000.0))
        audio_data = bytearray()

        for i in range(num_samples):
            t = float(i) / sample_rate
            progress = i / float(num_samples)

            # Wispr Flow Soft Envelope: Fast 5ms attack + Smooth exponential decay
            attack_samples = int(sample_rate * 0.005) # 5ms
            if i < attack_samples:
                envelope = i / float(attack_samples)
            else:
                envelope = math.exp(-6.0 * progress) # Gentle soft decay curve

            # Multi-harmonic chord synthesis (Fades harsh single frequencies into soft glass bell tone)
            mixed_sample = 0.0
            num_freqs = len(frequencies)
            for idx, freq in enumerate(frequencies):
                weight = 1.0 / (idx + 1) # Higher overtones are softer
                mixed_sample += weight * math.sin(2 * math.pi * freq * t)

            sample_val = int(32767 * volume * envelope * (mixed_sample / num_freqs))
            sample_val = max(-32768, min(32767, sample_val))
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
        wav_buf.extend(struct.pack("<I", sample_rate)) # SampleRate 44.1kHz
        wav_buf.extend(struct.pack("<I", sample_rate * 2)) # ByteRate
        wav_buf.extend(struct.pack("<H", 2))           # BlockAlign
        wav_buf.extend(struct.pack("<H", 16))          # BitsPerSample
        wav_buf.extend(b"data")
        wav_buf.extend(struct.pack("<I", data_size))
        wav_buf.extend(audio_data)

        file_path.write_bytes(bytes(wav_buf))
        return file_path

    def _pregenerate_chimes(self) -> None:
        """Pre-generates Wispr Flow style glass-bell harmonic chimes on disk."""
        try:
            # Startup chime: Soft F-Major Glass Bell Chord (F5, A5, C6) - 150ms
            self._sound_files["startup"] = self._generate_harmonic_wav_file("startup", [698.46, 880.0, 1046.50], 150, volume=0.18)
            
            # Start Recording chime: Soft Ascending Dual-Tone (A5, E6) - 90ms (Wispr Flow Listening Chime)
            self._sound_files["start"] = self._generate_harmonic_wav_file("start", [880.0, 1318.51], 90, volume=0.15)
            
            # Stop Recording chime: Soft Descending Dual-Tone (E6, A5) - 80ms
            self._sound_files["stop"] = self._generate_harmonic_wav_file("stop", [1318.51, 880.0], 80, volume=0.12)
            
            # Paste Success chime: Pristine High Bell Ping (C6, E6, G6) - 110ms
            self._sound_files["paste"] = self._generate_harmonic_wav_file("paste", [1046.50, 1318.51, 1567.98], 110, volume=0.18)
            
            # Error chime: Soft Muted Low Note (D4, F4) - 120ms
            self._sound_files["error"] = self._generate_harmonic_wav_file("error", [293.66, 349.23], 120, volume=0.20)
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
