from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ResponseFormat = Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]


@dataclass
class Voice:
    """Represents a voice option for a TTS provider."""

    id: str
    name: str
    gender: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the (unique) short-name for this provider (e.g. 'openai')."""

    @abstractmethod
    def list_voices(self) -> list[Voice]:
        """Return all available voices for this provider."""

    @abstractmethod
    def synth(
        self,
        *,  # force keyword-only args
        text: str,
        voice: str,  # voice ID
        style: str | None = None,  # style prompt
        format: ResponseFormat = "mp3",
        out_path: Path,
    ) -> None:
        """Synthesise *text* to *out_path* using *voice* and optional *style*."""
 