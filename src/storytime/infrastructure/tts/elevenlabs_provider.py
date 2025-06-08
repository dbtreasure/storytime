from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from elevenlabs import Voice as ElevenVoice

from storytime.infrastructure.tts.base import ResponseFormat, TTSProvider, Voice

load_dotenv()


class ElevenLabsProvider(TTSProvider):
    """TTS provider for ElevenLabs API."""

    name: str = "eleven"

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVEN_LABS_API_KEY")
        if not key:
            raise ValueError("ElevenLabs API key not found. Set ELEVEN_API_KEY or pass api_key.")
        self.client = ElevenLabs(api_key=key)

    def list_voices(self) -> list[Voice]:
        """Return all available voices, mapping from ElevenLabs specific model."""
        eleven_voices = self.client.voices.search().voices
        return [self._map_voice(v) for v in eleven_voices]

    def synth(
        self,
        *,
        text: str,
        voice: str,
        style: str | None = None,
        format: ResponseFormat = "mp3",
        out_path: Path,
    ) -> None:
        """Synthesize audio using ElevenLabs API (2.x)."""
        model_id = "eleven_multilingual_v2"
        if format != "mp3":
            print(f"Warning: ElevenLabs primarily uses MP3. Format '{format}' may not be optimal.")

        audio_stream = self.client.text_to_speech.stream(
            text=text,
            voice_id=voice,
            model_id=model_id,
            output_format=format,
        )
        with open(out_path, "wb") as f:
            for chunk in audio_stream:
                if isinstance(chunk, bytes):
                    f.write(chunk)

    def _map_voice(self, eleven_voice: ElevenVoice) -> Voice:
        """Convert an ElevenLabs Voice object to our internal `Voice` dataclass."""
        voice_id = (
            getattr(eleven_voice, "voice_id", None)
            or getattr(eleven_voice, "id", None)
            or "unknown"
        )
        return Voice(
            id=str(voice_id),
            name=getattr(eleven_voice, "name", "Unknown ElevenLabs Voice"),
            gender=getattr(eleven_voice, "labels", {}).get("gender"),
            description=getattr(eleven_voice, "labels", {}).get("description"),
            tags=list(getattr(eleven_voice, "labels", {}).keys())
            if getattr(eleven_voice, "labels", None)
            else [],
        )
