import io
import wave
import pytest
from fluid_voice.stt_deepgram import DeepgramSTTClient

DEEPGRAM_API_KEY = "e0316b571454eba64e487763b7a4dff87869944e"

def generate_silent_wav(duration_s: float = 1.0, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * int(sample_rate * duration_s))
    return buf.getvalue()

def test_deepgram_api_key_validity():
    client = DeepgramSTTClient(api_key=DEEPGRAM_API_KEY)
    wav_bytes = generate_silent_wav(1.0)
    # Transcribe silent WAV (should return HTTP 200 with empty or minimal transcript)
    transcript = client.transcribe(wav_bytes, model="nova-2", language="hi-latn")
    assert isinstance(transcript, str)
    print(f"\n[DEEPGRAM TEST SUCCESS] API key valid! Response: '{transcript}'")
