from __future__ import annotations

import os

from dotenv import load_dotenv

# Provider imports are now from the new infrastructure paths
from storytime.infrastructure.tts import (  # __init__ re-exports these
    ElevenLabsProvider,
    OpenAIProvider,
    TTSProvider,
    Voice,
)
from storytime.infrastructure.voice_utils import get_voices

# Simplified for single-voice TTS only

load_dotenv()


class TTSGenerator:
    """Simple TTS generator for single-voice text-to-audio conversion."""

    def __init__(self, provider: TTSProvider | None = None) -> None:
        # Select provider based on env or param
        if provider is None:
            provider_name = os.getenv("TTS_PROVIDER", "openai").lower()
            provider = ElevenLabsProvider() if provider_name == "eleven" else OpenAIProvider()

        self.provider: TTSProvider = provider
        self.provider_name: str = getattr(provider, "name", "openai")

        # Cache voices for simple voice selection
        self._voices: list[Voice] = get_voices(self.provider)

    async def generate_simple_audio(
        self, text: str, voice_config: dict[str, any] | None = None
    ) -> bytes:
        """Generate simple single-voice audio for text-to-audio conversion."""
        voice_config = voice_config or {}

        # Use specified voice or default to 'alloy'
        voice_id = voice_config.get("voice_id")
        if not voice_id:
            voice_id = "alloy"  # Default to alloy voice for simplicity

        # Generate audio using provider
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            self.provider.synth(
                text=text,
                voice=voice_id,
                style="Generate clear, natural speech.",
                format="mp3",
                out_path=tmp_file.name,
            )

            # Read audio data
            with open(tmp_file.name, "rb") as f:
                audio_data = f.read()

            # Clean up temp file
            import os

            os.unlink(tmp_file.name)

            return audio_data

