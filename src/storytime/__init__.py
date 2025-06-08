"""
Storytime – audiobook parsing and TTS generation toolkit.

This top-level package exposes the core domain models so that external
code can simply do `from storytime import Chapter` instead of drilling
into sub-modules.
"""

from .models import (
    Book,
    Chapter,
    Character,
    CharacterCatalogue,
    SpeakerType,
    TextSegment,
)

__all__ = [
    "Book",
    "Chapter",
    "Character",
    "CharacterCatalogue",
    "SpeakerType",
    "TextSegment",
]
