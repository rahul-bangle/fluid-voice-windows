"""
Unit tests for SFXEngine (Low-latency audio feedback).
"""

import pytest
from fluid_voice.sfx_engine import SFXEngine


def test_sfx_engine_initialization():
    sfx = SFXEngine(enabled=True)
    assert sfx.enabled is True
    assert "start" in sfx._sound_files
    assert "stop" in sfx._sound_files
    assert "paste" in sfx._sound_files
    assert "error" in sfx._sound_files
    assert sfx._sound_files["start"].exists()


def test_sfx_engine_toggle():
    sfx = SFXEngine(enabled=True)
    sfx.set_enabled(False)
    assert sfx.enabled is False
    # Playing when disabled should be no-op safely
    sfx.play("start")


def test_sfx_engine_play_cached_sounds():
    sfx = SFXEngine(enabled=True)
    # Playing valid and invalid sounds should execute safely without crashing
    sfx.play("start")
    sfx.play("stop")
    sfx.play("paste")
    sfx.play("error")
    sfx.play("non_existent_sound")


def test_sfx_engine_wav_file_format():
    sfx = SFXEngine(enabled=True)
    file_path = sfx._sound_files["start"]
    wav_bytes = file_path.read_bytes()
    assert isinstance(wav_bytes, bytes)
    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes
