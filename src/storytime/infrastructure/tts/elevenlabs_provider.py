from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs import Voice as ElevenVoice  # Renamed to avoid clash
from elevenlabs.client import ElevenLabs

from storytime.infrastructure.tts.base import ResponseFormat, TTSProvider, Voice

load_dotenv()


class ElevenLabsProvider(TTSProvider):
    """TTS provider for ElevenLabs API."""

    name: str = "eleven"

    def __init__(self, api_key: str | None = None) -> None:
        # Accept both ELEVEN_API_KEY (preferred) and ELEVEN_LABS_API_KEY for compatibility
        key = api_key or os.getenv("ELEVEN_LABS_API_KEY")
        if not key:
            raise ValueError(
                "ElevenLabs API key not found. Set ELEVEN_API_KEY or pass api_key."
            )
        self.client = ElevenLabs(api_key=key)

    def list_voices(self) -> list[Voice]:
        """Return all available voices, mapping from ElevenLabs specific model."""
        eleven_voices = self.client.voices.get_all().voices
        return [self._map_voice(v) for v in eleven_voices]

    def synth(
        self,
        *,
        text: str,
        voice: str,
        style: str | None = None,  # ElevenLabs uses voice settings instead
        format: ResponseFormat = "mp3",  # mp3_44100_128 is typical
        out_path: Path,
    ) -> None:
        """Synthesize audio using ElevenLabs API."""

        # ElevenLabs doesn't have per-request style prompts; it uses voice settings.
        # Format implies the full model ID for Eleven, e.g. mp3_44100_128
        # We'll use a common default but this could be exposed.
        model_id = "eleven_multilingual_v2"  # Or other like eleven_english_sts_v2
        if format != "mp3":  # Simplified, actual mapping is more complex
            print(f"Warning: ElevenLabs primarily uses MP3. Format '{format}' may not be optimal.")

        audio_iterator = self.client.generate(  # type: ignore[attr-defined]
            text=text,
            voice=voice,  # This is the Voice ID string
            model=model_id,
            # output_format=format, # This would require mapping our ResponseFormat to theirs
        )

        # Stream audio to file
        with open(out_path, "wb") as f:
            for chunk in audio_iterator:
                f.write(chunk)

    def _map_voice(self, eleven_voice: ElevenVoice) -> Voice:
        """Convert an ElevenLabs Voice object to our internal `Voice` dataclass."""

        return Voice(
            id=eleven_voice.voice_id,
            name=eleven_voice.name or "Unknown ElevenLabs Voice",
            gender=(eleven_voice.labels or {}).get("gender"),
            description=(eleven_voice.labels or {}).get("description"),
            tags=list(eleven_voice.labels.keys()) if eleven_voice.labels else [],
        ) 