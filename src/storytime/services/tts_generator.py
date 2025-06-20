from __future__ import annotations

import logging
import os
import tempfile

from dotenv import load_dotenv
from pydub import AudioSegment

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
logger = logging.getLogger(__name__)


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

        # Check if text needs chunking (OpenAI has 4096 char limit)
        max_chars = self._get_provider_char_limit()
        if len(text) <= max_chars:
            # Text is short enough, process normally
            return await self._generate_single_chunk(text, voice_id)
        else:
            # Text is too long, chunk and concatenate
            logger.info(f"Text too long ({len(text)} chars), chunking for TTS processing")
            return await self._generate_chunked_audio(text, voice_id, max_chars)

    def _get_provider_char_limit(self) -> int:
        """Get character limit for the current TTS provider."""
        if isinstance(self.provider, OpenAIProvider):
            return 4096  # OpenAI's current limit
        elif isinstance(self.provider, ElevenLabsProvider):
            return 5000  # ElevenLabs limit (approximate)
        else:
            return 4096  # Safe default

    async def _generate_single_chunk(self, text: str, voice_id: str) -> bytes:
        """Generate audio for a single text chunk."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_file:
            self.provider.synth(
                text=text,
                voice=voice_id,
                style="Generate clear, natural speech suitable for audiobook narration with appropriate pacing and expression.",
                format="mp3",
                out_path=tmp_file.name,
            )

            # Read audio data
            with open(tmp_file.name, "rb") as f:
                audio_data = f.read()

            # Clean up temp file
            os.unlink(tmp_file.name)

            return audio_data

    async def _generate_chunked_audio(self, text: str, voice_id: str, max_chars: int) -> bytes:
        """Generate audio by chunking text and concatenating results."""
        chunks = self._chunk_text(text, max_chars)
        logger.info(f"Split text into {len(chunks)} chunks for TTS processing")

        audio_segments = []

        for i, chunk in enumerate(chunks):
            logger.debug(f"Processing chunk {i + 1}/{len(chunks)} ({len(chunk)} chars)")
            chunk_audio = await self._generate_single_chunk(chunk, voice_id)

            # Convert to AudioSegment for concatenation
            with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp_file:
                tmp_file.write(chunk_audio)
                tmp_file.flush()
                segment = AudioSegment.from_mp3(tmp_file.name)
                audio_segments.append(segment)

        # Concatenate all segments
        logger.info(f"Concatenating {len(audio_segments)} audio segments")
        combined_audio = audio_segments[0]
        for segment in audio_segments[1:]:
            combined_audio += segment

        # Export to bytes
        with tempfile.NamedTemporaryFile(suffix=".mp3") as tmp_file:
            combined_audio.export(tmp_file.name, format="mp3")
            with open(tmp_file.name, "rb") as f:
                return f.read()

    def _chunk_text(self, text: str, max_chars: int) -> list[str]:
        """Split text into chunks that respect sentence boundaries when possible."""
        if len(text) <= max_chars:
            return [text]

        chunks = []
        current_chunk = ""

        # Split on sentences first
        sentences = text.replace("\n\n", " [PARAGRAPH] ").split(". ")

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Restore paragraph breaks
            sentence = sentence.replace("[PARAGRAPH]", "\n\n")

            # Add period back if it was removed (except for last sentence)
            if (
                not sentence.endswith(".")
                and not sentence.endswith("!")
                and not sentence.endswith("?")
            ):
                sentence += "."

            # Check if adding this sentence would exceed the limit
            test_chunk = current_chunk + (" " if current_chunk else "") + sentence

            if len(test_chunk) <= max_chars:
                current_chunk = test_chunk
            else:
                # Current chunk is full, start a new one
                if current_chunk:
                    chunks.append(current_chunk.strip())

                # If single sentence is too long, split it further
                if len(sentence) > max_chars:
                    word_chunks = self._chunk_by_words(sentence, max_chars)
                    chunks.extend(word_chunks[:-1])  # Add all but the last
                    current_chunk = word_chunks[-1]  # Start new chunk with last part
                else:
                    current_chunk = sentence

        # Add the final chunk
        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _chunk_by_words(self, text: str, max_chars: int) -> list[str]:
        """Split text by words when sentence-based chunking isn't sufficient."""
        words = text.split()
        chunks = []
        current_chunk = ""

        for word in words:
            test_chunk = current_chunk + (" " if current_chunk else "") + word

            if len(test_chunk) <= max_chars:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = word

        if current_chunk:
            chunks.append(current_chunk)

        return chunks
