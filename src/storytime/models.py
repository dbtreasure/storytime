from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SpeakerType(str, Enum):
    """Type of speaker in a segment."""

    NARRATOR = "narrator"
    CHARACTER = "character"


class Character(BaseModel):
    """Represents a character identified in the text."""

    name: str = Field(..., description="Character's name as it appears in dialogue tags")
    gender: str | None = Field(
        None, description="Character's gender (male/female/other/unknown)"
    )
    description: str | None = Field(None, description="Brief character description")
    voice_assignments: dict[str, str] = Field(
        default_factory=dict, description="Voice ID per TTS provider"
    )


class CharacterCatalogue(BaseModel):
    """Collection of all characters identified across chapters."""

    characters: dict[str, Character] = Field(
        default_factory=dict, description="Character name -> Character object"
    )

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------
    def add_character(self, character: Character) -> None:
        """Add or update a character in the catalogue."""

        self.characters[character.name] = character

    def get_character(self, name: str) -> Character | None:
        """Return a character by *exact* name, or *None* if absent."""

        return self.characters.get(name)

    def get_character_names(self) -> list[str]:
        """Return an alphabetically sorted list of character names."""

        return sorted(self.characters.keys())


class TextSegment(BaseModel):
    """A contiguous chunk of text to be spoken by one voice."""

    text: str = Field(..., description="The actual text content to be spoken")
    speaker_type: SpeakerType = Field(..., description="Narrator or character dialogue")
    speaker_name: str = Field(
        ..., description="'narrator' for narration, or the character name"
    )
    sequence_number: int = Field(..., description="Order of this segment in the chapter")

    # Optional metadata for TTS processing
    voice_hint: str | None = Field(None, description="Suggested voice characteristics")
    emotion: str | None = Field(None, description="Emotional tone of the text")
    instruction: str | None = Field(None, description="TTS delivery instruction")

    class Config:
        use_enum_values = True


class Chapter(BaseModel):
    """Represents a chapter broken down into ordered segments."""

    chapter_number: int = Field(..., description="Chapter number (1-based)")
    title: str | None = Field(None, description="Chapter title, if present")
    segments: list[TextSegment] = Field(..., description="List of text segments in order")

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def get_narrator_segments(self) -> list[TextSegment]:
        """Return all narration segments."""

        return [s for s in self.segments if s.speaker_type == SpeakerType.NARRATOR]

    def get_character_segments(self) -> list[TextSegment]:
        """Return all character dialogue segments."""

        return [s for s in self.segments if s.speaker_type == SpeakerType.CHARACTER]

    def get_unique_characters(self) -> set[str]:
        """Return the set of unique character names in the chapter."""

        return {
            s.speaker_name
            for s in self.segments
            if s.speaker_type == SpeakerType.CHARACTER
        }


class Book(BaseModel):
    """A full book consisting of multiple chapters."""

    title: str = Field(..., description="Book title")
    author: str = Field(..., description="Book author")
    chapters: list[Chapter] = Field(..., description="List of chapters")
    character_catalogue: CharacterCatalogue = Field(
        default_factory=CharacterCatalogue,
        description="All characters found in the book",
    )

    # ------------------------------------------------------------------
    # Aggregate helpers
    # ------------------------------------------------------------------
    def get_all_characters(self) -> set[str]:
        """Return the set of all unique characters across chapters."""

        characters: set[str] = set()
        for chapter in self.chapters:
            characters.update(chapter.get_unique_characters())
        return characters 