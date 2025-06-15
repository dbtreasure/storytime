import enum
import logging
import uuid
from datetime import datetime
from typing import Any

from passlib.context import CryptContext
from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Mapped, declarative_base, relationship, mapped_column

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
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    jobs = relationship("Job", back_populates="user")

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

    # Job configuration
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Processing state
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 to 1.0
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Configuration and results (JSON fields)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # Job-specific parameters
    result_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # Workflow outputs

    # File references
    input_file_key: Mapped[str | None] = mapped_column(String, nullable=True)  # Source content file
    output_file_key: Mapped[str | None] = mapped_column(String, nullable=True)  # Generated audio file

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="jobs")
    steps = relationship("JobStep", back_populates="job", cascade="all, delete-orphan")

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
    step_name: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "LoadTextNode", "GeminiApiNode"
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)  # Execution order within job

    # Step state
    status: Mapped[StepStatus] = mapped_column(Enum(StepStatus), nullable=False, default=StepStatus.PENDING)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 0.0 to 1.0
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Step-specific data
    step_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)  # Step-specific information

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
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


settings = get_settings()
engine = create_async_engine(settings.database_url, echo=True, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.getLogger(__name__).info("Database tables created (User, Book, Job, JobStep)")
