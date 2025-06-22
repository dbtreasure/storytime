from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# Simplified: Single-voice text processing only


# Simplified book model removed - focusing on simple text-to-audio


# =============================================================================
# Unified Job Management Models
# =============================================================================


# Simplified: Single voice TTS processing only


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


class Chapter(BaseModel):
    """Chapter information for multi-chapter content."""

    title: str = Field(..., description="Chapter title")
    order: int = Field(..., description="Chapter order/number")
    duration: float | None = Field(None, description="Chapter duration in seconds")
    file_key: str | None = Field(None, description="Storage key for chapter audio file")


class JobConfig(BaseModel):
    """Job configuration data."""

    voice_config: VoiceConfig | None = Field(None, description="Voice configuration")
    provider: str | None = Field(None, description="TTS provider (for backwards compatibility)")


class JobResultData(BaseModel):
    """Job result data."""

    duration: float | None = Field(None, description="Total duration in seconds")
    duration_seconds: float | None = Field(None, description="Total duration in seconds (alias)")
    file_size_bytes: int | None = Field(None, description="File size in bytes")
    chapters: list[Chapter] | None = Field(
        None, description="Chapter information for multi-chapter content"
    )
    child_job_ids: list[str] | None = Field(None, description="Child job IDs for book processing")


class JobType(str, Enum):
    """Types of jobs that can be processed."""

    TEXT_TO_AUDIO = "text_to_audio"
    BOOK_PROCESSING = "book_processing"


class CreateJobRequest(BaseModel):
    """Request model for creating a job."""

    title: str = Field(..., description="Job title")
    description: str | None = Field(None, description="Job description")
    content: str | None = Field(None, description="Text content")
    file_key: str | None = Field(None, description="File key for uploaded text file")

    # Job type configuration
    job_type: JobType = Field(JobType.TEXT_TO_AUDIO, description="Type of job to create")

    # Voice configuration
    voice_config: VoiceConfig | None = Field(None, description="Voice configuration")

    # Book processing specific
    processing_mode: str = Field("single_voice", description="Processing mode for book chapters")


class JobStepResponse(BaseModel):
    """Response model for job steps."""

    id: str
    step_name: str
    step_order: int
    status: StepStatus
    progress: float
    error_message: str | None = None
    step_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration: float | None = None


class JobResponse(BaseModel):
    """Response model for text-to-audio jobs."""

    id: str
    user_id: str
    parent_job_id: str | None = Field(None, description="Parent job ID")
    title: str
    description: str | None = None

    # Processing state
    status: JobStatus
    progress: float
    error_message: str | None = None

    # Configuration and results
    config: JobConfig | None = None
    result_data: JobResultData | None = None

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
    children: list[JobResponse] = Field(default_factory=list, description="Child jobs")
    parent: JobResponse | None = Field(None, description="Parent job (if this is a child)")


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
    created_after: datetime | None = None
    created_before: datetime | None = None


# =============================================================================
# Playback Progress Models
# =============================================================================


class UpdateProgressRequest(BaseModel):
    """Request model for updating playback progress."""

    position_seconds: float = Field(..., ge=0.0, description="Current playback position in seconds")
    duration_seconds: float | None = Field(
        None, ge=0.0, description="Total audio duration in seconds"
    )
    current_chapter_id: str | None = Field(
        None, description="Current chapter ID for multi-chapter books"
    )
    current_chapter_position: float = Field(
        0.0, ge=0.0, description="Position within current chapter"
    )


class PlaybackProgressResponse(BaseModel):
    """Response model for playback progress."""

    id: str
    user_id: str
    job_id: str

    # Progress data
    position_seconds: float
    duration_seconds: float | None = None
    percentage_complete: float

    # Chapter tracking
    current_chapter_id: str | None = None
    current_chapter_position: float

    # Metadata
    is_completed: bool
    last_played_at: datetime
    created_at: datetime
    updated_at: datetime


class ResumeInfoResponse(BaseModel):
    """Response model for resume information."""

    has_progress: bool
    resume_position: float = 0.0
    percentage_complete: float = 0.0
    last_played_at: datetime | None = None
    current_chapter_id: str | None = None
    current_chapter_position: float = 0.0


class StreamingUrlResponse(BaseModel):
    """Response model for audio streaming URLs."""

    streaming_url: str = Field(..., description="Pre-signed URL for streaming audio")
    expires_at: str = Field(..., description="ISO timestamp when URL expires")
    file_key: str = Field(..., description="Storage key for the audio file")
    content_type: str = Field(..., description="MIME type of the audio file")
    resume_info: ResumeInfoResponse = Field(..., description="Resume information for the user")
    source_job_id: str | None = Field(
        None, description="ID of the child job that provided the audio"
    )


class AudioMetadataResponse(BaseModel):
    """Response model for audio metadata."""

    job_id: str
    title: str
    status: JobStatus
    format: str
    duration: float | None = None
    file_size: int | None = None
    created_at: str | None = None
    completed_at: str | None = None
    chapters: list[dict] = Field(default_factory=list)
    resume_position: float = 0.0
    percentage_complete: float = 0.0
    last_played_at: datetime | None = None
    current_chapter_id: str | None = None
    current_chapter_position: float = 0.0


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class JobAudioResponse(BaseModel):
    """Response model for job audio download and streaming URLs."""

    download_url: str
    streaming_url: str
    file_key: str
    content_type: str


class BookChaptersResponse(BaseModel):
    """Aggregated chapter results for a book job."""

    total_chapters: int
    completed_chapters: int
    failed_chapters: int
    total_duration_seconds: float
    chapters: list[dict]
