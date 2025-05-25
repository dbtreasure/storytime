from __future__ import annotations

from pathlib import Path
from typing import Protocol, Literal, Optional, List
from dataclasses import dataclass

@dataclass
class Voice:
    """Basic metadata for a TTS voice."""

    id: str          # provider-specific voice identifier
    name: str        # human-readable name (may match id for OpenAI)
    gender: Optional[str] = None
    description: Optional[str] = None


class TTSProvider(Protocol):
    """Protocol every concrete TTS provider must follow."""

    name: str  # short identifier, e.g. "openai" or "eleven"

    def synth(
        self,
        *,
        text: str,
        voice: str,
        style: Optional[str],
        format: Literal["mp3", "wav", "flac", "aac", "opus", "pcm"],
        out_path: Path,
    ) -> Path:
        """Generate speech audio and write it to *out_path*.

        Returns *out_path* for convenience.
        """
        ...

    def list_voices(self) -> List[Voice]:
        """Return all voices the provider makes available to the current user/API key."""
        ... 