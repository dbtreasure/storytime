from __future__ import annotations

from pathlib import Path
from typing import Optional, Literal

import openai
from dotenv import load_dotenv
import os

from .base import TTSProvider

load_dotenv()

class OpenAIProvider:
    """Concrete TTS provider that calls OpenAI TTS endpoints."""

    name = "openai"

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini-tts") -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set and no api_key supplied.")

        self.model = model
        openai.api_key = self.api_key
        self.client = openai.OpenAI(api_key=self.api_key)

    def synth(
        self,
        *,
        text: str,
        voice: str,
        style: Optional[str],
        format: Literal["mp3", "wav", "flac", "aac", "opus", "pcm"],
        out_path: Path,
    ) -> Path:
        response = self.client.audio.speech.create(
            model=self.model,
            voice=voice,
            input=text,
            response_format=format,
            instructions=style or "",
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(response.content)
        return out_path

    # ------------------------------------------------------------------
    # Voice catalogue
    # ------------------------------------------------------------------

    def list_voices(self):
        from tts_providers.base import Voice

        voices = [
            Voice(id="alloy",  name="alloy", gender="male"),
            Voice(id="echo",   name="echo", gender="neutral"),
            Voice(id="fable",  name="fable", gender="male"),
            Voice(id="onyx",   name="onyx", gender="male"),
            Voice(id="nova",   name="nova", gender="female"),
            Voice(id="shimmer",name="shimmer", gender="female"),
        ]
        return voices 