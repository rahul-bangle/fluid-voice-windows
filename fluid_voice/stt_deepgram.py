import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

DEEPGRAM_STT_ENDPOINT = "https://api.deepgram.com/v1/listen"

class DeepgramSTTClient:
    """
    Client for Deepgram Speech-to-Text REST API with native Hinglish (hi-latn) support.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        if not self.api_key:
            raise ValueError("Deepgram API key cannot be empty")

    def transcribe(
        self,
        wav_bytes: bytes,
        model: str = "nova-2",
        language: str = "hi-latn",
        smart_format: bool = True,
        timeout: float = 8.0,
    ) -> str:
        """
        Transcribes WAV byte stream via Deepgram REST API.
        
        Args:
            wav_bytes: Raw 16-bit Mono 16kHz WAV byte stream.
            model: Deepgram model (default 'nova-2').
            language: Target language ('hi-latn' for Roman Hinglish).
            smart_format: Enable smart formatting (punctuation, numbers).
            timeout: HTTP request timeout.
            
        Returns:
            Transcribed text string.
        """
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav",
        }

        params = {
            "model": model,
            "smart_format": "true" if smart_format else "false",
            "punctuate": "true",
        }
        if language:
            params["language"] = language

        try:
            resp = requests.post(
                DEEPGRAM_STT_ENDPOINT,
                headers=headers,
                params=params,
                data=wav_bytes,
                timeout=timeout,
            )

            if resp.status_code == 200:
                data = resp.json()
                results = data.get("results", {})
                channels = results.get("channels", [])
                if channels:
                    alternatives = channels[0].get("alternatives", [])
                    if alternatives:
                        transcript = alternatives[0].get("transcript", "").strip()
                        logger.info(f"Deepgram STT Success ({model}, lang={language}): '{transcript}'")
                        return transcript
                return ""
            else:
                logger.error(f"Deepgram STT API Error ({resp.status_code}): {resp.text}")
                raise RuntimeError(f"Deepgram API returned status {resp.status_code}: {resp.text}")

        except Exception as e:
            logger.error(f"Deepgram STT transcription failed: {e}")
            raise
