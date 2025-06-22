import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

from passlib.context import CryptContext
from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

from storytime.api.settings import get_settings
from storytime.models import JobStatus, StepStatus

Base = declarative_base()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Simplified: Only single-voice TTS processing


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    jobs = relationship("Job", back_populates="user")
    progress_records = relationship("PlaybackProgress", back_populates="user")

    def verify_password(self, password: str) -> bool:
        """Verify a password against the hash."""
        return pwd_context.verify(password, self.hashed_password)

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hash a password for storing."""
        return pwd_context.hash(password)


class Job(Base):
    """Simple text-to-audio job entity."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("jobs.id"), nullable=True, index=True
    )

    # Job configuration
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Processing state
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True
    )
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 to 1.0
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Configuration and results (JSON fields)
    config: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )  # Job-specific parameters
    result_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )  # Workflow outputs

    # File references
    input_file_key: Mapped[str | None] = mapped_column(String, nullable=True)  # Source content file
    output_file_key: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # Generated audio file

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="jobs")
    parent = relationship("Job", remote_side="Job.id", back_populates="children")
    children = relationship(
        "Job",
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    steps = relationship("JobStep", back_populates="job", cascade="all, delete-orphan")
    progress_records = relationship("PlaybackProgress", back_populates="job")

    @property
    def duration(self) -> float | None:
        """Calculate job duration in seconds if completed."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class JobStep(Base):
    """Individual steps within a job for granular progress tracking."""

    __tablename__ = "job_steps"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id"), nullable=False, index=True)

    # Step identification
    step_name: Mapped[str] = mapped_column(
        String, nullable=False
    )  # e.g., "LoadTextNode", "GeminiApiNode"
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)  # Execution order within job

    # Step state
    status: Mapped[StepStatus] = mapped_column(
        Enum(StepStatus), nullable=False, default=StepStatus.PENDING
    )
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 to 1.0
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Step-specific data
    step_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )  # Step-specific information

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    job = relationship("Job", back_populates="steps")

    @property
    def duration(self) -> float | None:
        """Calculate step duration in seconds if completed."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class PlaybackProgress(Base):
    """Playback progress tracking for audiobook resume functionality."""

    __tablename__ = "playback_progress"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.id"), nullable=False, index=True)

    # Progress tracking
    position_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duration_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )  # Cached total duration
    percentage_complete: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )  # 0.0 to 1.0

    # Chapter tracking (for multi-chapter books)
    current_chapter_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # For CORE-51 books
    current_chapter_position: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Metadata
    last_played_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user = relationship("User", back_populates="progress_records")
    job = relationship("Job", back_populates="progress_records")

    # Constraints
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="unique_user_job_progress"),
        Index("idx_progress_user_updated", "user_id", "updated_at"),
    )

    @property
    def is_completed(self) -> bool:
        """Check if the audiobook is considered completed (>95% played)."""
        return self.percentage_complete >= 0.95

    @property
    def resume_position(self) -> float:
        """Get the position to resume playback from."""
        return self.position_seconds

    def update_progress(
        self, position_seconds: float, duration_seconds: float | None = None
    ) -> None:
        """Update progress and calculate percentage."""
        self.position_seconds = max(0.0, position_seconds)
        self.last_played_at = datetime.utcnow()

        if duration_seconds is not None:
            self.duration_seconds = duration_seconds

        if self.duration_seconds and self.duration_seconds > 0:
            self.percentage_complete = min(1.0, self.position_seconds / self.duration_seconds)
        else:
            self.percentage_complete = 0.0


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=True, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.getLogger(__name__).info(
        "Database tables created (User, Job, JobStep, PlaybackProgress)"
    )
