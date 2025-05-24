from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum

class SpeakerType(str, Enum):
    NARRATOR = "narrator"
    CHARACTER = "character"

class TextSegment(BaseModel):
    """
    Represents a segment of text from a novel, ready for TTS processing.
    """
    text: str = Field(..., description="The actual text content to be spoken")
    speaker_type: SpeakerType = Field(..., description="Whether this is narration or character dialogue")
    speaker_name: str = Field(..., description="Name of the speaker ('narrator' for narration, character name for dialogue)")
    sequence_number: int = Field(..., description="Order of this segment in the chapter")
    
    # Optional metadata for TTS processing
    voice_hint: Optional[str] = Field(None, description="Suggested voice characteristics (e.g., 'male', 'female', 'elderly')")
    emotion: Optional[str] = Field(None, description="Emotional tone of the text (e.g., 'angry', 'sad', 'cheerful')")
    
    class Config:
        use_enum_values = True

class Chapter(BaseModel):
    """
    Represents a full chapter broken down into text segments.
    """
    chapter_number: int = Field(..., description="Chapter number")
    title: Optional[str] = Field(None, description="Chapter title if present")
    segments: list[TextSegment] = Field(..., description="List of text segments in order")
    
    def get_narrator_segments(self) -> list[TextSegment]:
        """Get all narrator segments."""
        return [seg for seg in self.segments if seg.speaker_type == SpeakerType.NARRATOR]
    
    def get_character_segments(self) -> list[TextSegment]:
        """Get all character dialogue segments."""
        return [seg for seg in self.segments if seg.speaker_type == SpeakerType.CHARACTER]
    
    def get_unique_characters(self) -> set[str]:
        """Get all unique character names in this chapter."""
        return {seg.speaker_name for seg in self.segments if seg.speaker_type == SpeakerType.CHARACTER}

class Book(BaseModel):
    """
    Represents the entire book structure.
    """
    title: str = Field(..., description="Book title")
    author: str = Field(..., description="Book author")
    chapters: list[Chapter] = Field(..., description="List of chapters")
    
    def get_all_characters(self) -> set[str]:
        """Get all unique characters across all chapters."""
        characters = set()
        for chapter in self.chapters:
            characters.update(chapter.get_unique_characters())
        return characters 