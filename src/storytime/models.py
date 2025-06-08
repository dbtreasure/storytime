from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

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


# =============================================================================
# Unified Job Management Models
# =============================================================================

class JobType(str, Enum):
    """Types of jobs that can be processed."""
    SINGLE_VOICE = "SINGLE_VOICE"
    MULTI_VOICE = "MULTI_VOICE"
    BOOK_PROCESSING = "BOOK_PROCESSING"
    CHAPTER_PARSING = "CHAPTER_PARSING"


class SourceType(str, Enum):
    """Source content types for jobs."""
    BOOK = "BOOK"
    CHAPTER = "CHAPTER"
    TEXT = "TEXT"


class JobStatus(str, Enum):
    """Job processing states."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StepStatus(str, Enum):
    """Individual step processing states."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VoiceConfig(BaseModel):
    """Voice configuration for TTS generation."""
    provider: str = Field(..., description="TTS provider (openai, elevenlabs)")
    voice_id: str | None = Field(None, description="Specific voice ID")
    voice_settings: dict[str, str] = Field(
        default_factory=dict, description="Provider-specific voice settings"
    )


class ProcessingConfig(BaseModel):
    """Processing configuration for jobs."""
    max_concurrency: int = Field(8, description="Maximum parallel operations")
    chunk_size: int = Field(1000, description="Text chunk size for processing")
    retry_attempts: int = Field(3, description="Number of retry attempts")
    enable_observability: bool = Field(True, description="Enable tracing and metrics")


class CreateJobRequest(BaseModel):
    """Request model for creating a new job."""
    title: str = Field(..., description="Job title")
    description: str | None = Field(None, description="Job description")
    content: str | None = Field(None, description="Text content (for TEXT source)")
    file_key: str | None = Field(None, description="File key (for BOOK/CHAPTER source)")
    book_id: str | None = Field(None, description="Associated book ID")

    # Optional job configuration
    job_type: JobType | None = Field(None, description="Job type (auto-detected if not provided)")
    source_type: SourceType = Field(SourceType.TEXT, description="Source content type")
    voice_config: VoiceConfig | None = Field(None, description="Voice configuration")
    processing_config: ProcessingConfig | None = Field(None, description="Processing configuration")


class JobStepResponse(BaseModel):
    """Response model for job steps."""
    id: str
    step_name: str
    step_order: int
    status: StepStatus
    progress: float
    error_message: str | None = None
    step_metadata: dict[str, str] | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: float | None = None


class JobResponse(BaseModel):
    """Response model for jobs."""
    id: str
    user_id: str
    book_id: str | None = None
    title: str
    description: str | None = None

    # Job configuration
    job_type: JobType
    source_type: SourceType

    # Processing state
    status: JobStatus
    progress: float
    error_message: str | None = None

    # Configuration and results
    config: dict[str, Any] | None = None
    result_data: dict[str, Any] | None = None

    # File references
    input_file_key: str | None = None
    output_file_key: str | None = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: float | None = None

    # Related data
    steps: list[JobStepResponse] = Field(default_factory=list)


class JobListResponse(BaseModel):
    """Response model for paginated job lists."""
    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class JobFilters(BaseModel):
    """Filters for job listing."""
    status: JobStatus | None = None
    job_type: JobType | None = None
    source_type: SourceType | None = None
    book_id: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


class ContentAnalysisResult(BaseModel):
    """Result of content analysis for job type detection."""
    suggested_job_type: JobType
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    detected_features: dict[str, str] = Field(default_factory=dict)
    estimated_processing_time: int | None = None  # seconds
