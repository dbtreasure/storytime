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


class ProcessingConfig(BaseModel):
    """Processing configuration for jobs."""

    max_concurrency: int = Field(8, description="Maximum parallel operations")
    chunk_size: int = Field(1000, description="Text chunk size for processing")
    retry_attempts: int = Field(3, description="Number of retry attempts")
    enable_observability: bool = Field(True, description="Enable tracing and metrics")


class JobType(str, Enum):
    """Types of jobs that can be processed."""
    
    TEXT_TO_AUDIO = "text_to_audio"
    BOOK_PROCESSING = "book_processing"
    CHAPTER_MULTI_VOICE = "chapter_multi_voice"


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
    title: str
    description: str | None = None

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
    created_after: datetime | None = None
    created_before: datetime | None = None
