from __future__ import annotations

from pathlib import Path
from typing import Optional, Literal
import os
import requests
from dotenv import load_dotenv

from .base import TTSProvider

load_dotenv()

class ElevenLabsProvider:
    """Concrete provider for ElevenLabs TTS."""

    name = "eleven"
    BASE_URL = "https://api.elevenlabs.io/v1/text-to-speech"

    def __init__(self, api_key: Optional[str] = None, model_id: str = "eleven_multilingual_v2") -> None:
        # Use explicit parameter or ELEVEN_LABS_API_KEY environment variable
        self.api_key = api_key or os.getenv("ELEVEN_LABS_API_KEY")

        if not self.api_key:
            raise ValueError("ELEVEN_LABS_API_KEY environment variable not set and no api_key supplied.")
        self.model_id = model_id

    def synth(
        self,
        *,
        text: str,
        voice: str,  # Expected to be ElevenLabs voice_id
        style: Optional[str],  # Not directly used but included for interface parity
        format: Literal["mp3", "wav", "flac", "aac", "opus", "pcm"],
        out_path: Path,
    ) -> Path:
        url = f"{self.BASE_URL}/{voice}"
        headers = {
            "xi-api-key": self.api_key,
            "Accept": "audio/mpeg" if format == "mp3" else "*/*",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.75,
            },
        }
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(resp.content)
        return out_path

    # ------------------------------------------------------------------
    # Voice catalogue
    # ------------------------------------------------------------------

    def list_voices(self):
        from tts_providers.base import Voice

        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": self.api_key}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        voices: list[Voice] = []
        for v in data.get("voices", []):
            voices.append(
                Voice(
                    id=v.get("voice_id"),
                    name=v.get("name", v.get("voice_id")),
                    gender=v.get("labels", {}).get("gender"),
                    description=v.get("description"),
                )
            )
        return voices 