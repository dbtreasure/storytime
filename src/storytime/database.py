import enum
import logging
import uuid
from datetime import datetime

from passlib.context import CryptContext
from sqlalchemy import JSON, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from storytime.api.settings import get_settings

Base = declarative_base()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class BookStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class JobType(str, enum.Enum):
    """Types of jobs that can be processed."""

    SINGLE_VOICE = "SINGLE_VOICE"  # Simple TTS generation
    MULTI_VOICE = "MULTI_VOICE"  # Complex character-based TTS
    BOOK_PROCESSING = "BOOK_PROCESSING"  # Full book with chapter splitting
    CHAPTER_PARSING = "CHAPTER_PARSING"  # Text analysis and segment parsing


class SourceType(str, enum.Enum):
    """Source content types for jobs."""

    BOOK = "BOOK"  # Full book file
    CHAPTER = "CHAPTER"  # Single chapter
    TEXT = "TEXT"  # Raw text input


class JobStatus(str, enum.Enum):
    """Job processing states."""

    PENDING = "PENDING"  # Job created, not started
    PROCESSING = "PROCESSING"  # Job in progress
    COMPLETED = "COMPLETED"  # Job finished successfully
    FAILED = "FAILED"  # Job failed with error
    CANCELLED = "CANCELLED"  # Job cancelled by user


class StepStatus(str, enum.Enum):
    """Individual step processing states."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    books = relationship("Book", back_populates="user")
    jobs = relationship("Job", back_populates="user")

    def verify_password(self, password: str) -> bool:
        """Verify a password against the hash."""
        return pwd_context.verify(password, self.hashed_password)

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hash a password for storing."""
        return pwd_context.hash(password)


class Book(Base):
    __tablename__ = "book"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(BookStatus), nullable=False, default=BookStatus.UPLOADED)
    progress_pct = Column(Integer, nullable=False, default=0)
    error_msg = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    text_key = Column(String, nullable=True)
    audio_key = Column(String, nullable=True)

    # Relationships
    user = relationship("User", back_populates="books")
    jobs = relationship("Job", back_populates="book")


class Job(Base):
    """Unified job entity for all processing types."""

    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    book_id = Column(String, ForeignKey("book.id"), nullable=True, index=True)

    # Job configuration
    job_type = Column(Enum(JobType), nullable=False, index=True)
    source_type = Column(Enum(SourceType), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Processing state
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING, index=True)
    progress = Column(Float, nullable=False, default=0.0)  # 0.0 to 1.0
    error_message = Column(Text, nullable=True)

    # Configuration and results (JSON fields)
    config = Column(JSON, nullable=True)  # Job-specific parameters
    result_data = Column(JSON, nullable=True)  # Workflow outputs

    # File references
    input_file_key = Column(String, nullable=True)  # Source content file
    output_file_key = Column(String, nullable=True)  # Generated audio file

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="jobs")
    book = relationship("Book", back_populates="jobs")
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

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False, index=True)

    # Step identification
    step_name = Column(String, nullable=False)  # e.g., "LoadTextNode", "GeminiApiNode"
    step_order = Column(Integer, nullable=False)  # Execution order within job

    # Step state
    status = Column(Enum(StepStatus), nullable=False, default=StepStatus.PENDING)
    progress = Column(Float, nullable=False, default=0.0)  # 0.0 to 1.0
    error_message = Column(Text, nullable=True)

    # Step-specific data
    step_metadata = Column(JSON, nullable=True)  # Step-specific information

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

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
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


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
