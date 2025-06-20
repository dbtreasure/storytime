from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI  # Main client

# Internal - base class and voice model
from storytime.infrastructure.tts.base import ResponseFormat, TTSProvider, Voice

load_dotenv()


class OpenAIProvider(TTSProvider):
    """TTS provider for OpenAI API (v1.0+).

    Uses tts-1-hd by default - OpenAI's high-definition TTS model for better quality.
    """

    name: str = "openai"

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY or pass api_key.")
        self.client = OpenAI(api_key=key)

    def list_voices(self) -> list[Voice]:
        """OpenAI has fixed voices, map them to our internal `Voice` model."""

        # These are standard OpenAI TTS voice names as of late 2023 / early 2024
        # Descriptions are subjective interpretations for voice selection.
        return [
            Voice(
                id="alloy",
                name="Alloy",
                gender="neutral",
                description="Versatile, balanced neutral voice.",
            ),
            Voice(id="echo", name="Echo", gender="male", description="Warm, engaging male voice."),
            Voice(
                id="fable",
                name="Fable",
                gender="male",
                description="Storyteller, classic male narrator voice.",
            ),
            Voice(id="onyx", name="Onyx", gender="male", description="Deep, resonant male voice."),
            Voice(
                id="nova",
                name="Nova",
                gender="female",
                description="Bright, expressive female voice.",
            ),
            Voice(
                id="shimmer",
                name="Shimmer",
                gender="female",
                description="Clear, gentle female voice.",
            ),
        ]

    def synth(
        self,
        *,
        text: str,
        voice: str,  # Matched to one of the IDs above
        style: str | None = None,  # Style parameter is ignored for OpenAI (not supported)
        format: ResponseFormat = "mp3",  # mp3, opus, aac, flac, wav, pcm
        out_path: Path,
        model: str = "tts-1-hd",  # Can be tts-1 or tts-1-hd
    ) -> None:
        """Synthesize audio using OpenAI TTS API."""

        # OpenAI TTS API does not support style parameter
        if style:
            print("Note: Style parameter is not supported by OpenAI TTS API and will be ignored.")

        # Prepare API call parameters (no style parameter for OpenAI)
        api_params = {
            "model": model,
            "voice": voice,  # type: ignore[arg-type]
            "input": text,
            "response_format": format,
        }

        # API call returns a streaming binary response
        response = self.client.audio.speech.create(**api_params)
        response.stream_to_file(out_path)
