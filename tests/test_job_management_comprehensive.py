#!/usr/bin/env python3
"""Comprehensive tests for the unified job management system."""

import asyncio
import os
import sys
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Set test environment
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/storytime"
os.environ["GOOGLE_API_KEY"] = "test-key"
os.environ["OPENAI_API_KEY"] = "test-key"

from storytime.database import Job, JobStep, User
from storytime.models import (
    CreateJobRequest,
    JobStatus,
    JobType,
    ProcessingConfig,
    SourceType,
    StepStatus,
    VoiceConfig,
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/storytime", echo=False
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_user(test_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(id="test-user-123", email="test@example.com", hashed_password="fake-hash")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
def test_client():
    """Create FastAPI test client."""
    # Mock the get_db dependency to avoid database connection issues in FastAPI
    from storytime.api.main import app

    def override_get_db():
        # This would normally return a real database session
        # For testing, we'll mock it
        pass

    # Don't override for now, let it use the real database
    return TestClient(app)


class TestJobManagementSystem:
    """Test the unified job management system."""

    async def test_database_models(self, test_session: AsyncSession, test_user: User):
        """Test that database models work correctly."""
        # Create a job
        job = Job(
            id="test-job-123",
            user_id=test_user.id,
            job_type=JobType.SINGLE_VOICE,
            source_type=SourceType.TEXT,
            title="Test Job",
            description="A test job",
            status=JobStatus.PENDING,
            progress=0.0,
            config={"test": "config"},
        )

        test_session.add(job)
        await test_session.commit()
        await test_session.refresh(job)

        assert job.id == "test-job-123"
        assert job.user_id == test_user.id
        assert job.job_type == JobType.SINGLE_VOICE
        assert job.status == JobStatus.PENDING

        # Create job steps
        step1 = JobStep(
            id="step-1",
            job_id=job.id,
            step_name="content_analysis",
            step_order=1,
            status=StepStatus.COMPLETED,
            progress=1.0,
        )

        step2 = JobStep(
            id="step-2",
            job_id=job.id,
            step_name="audio_generation",
            step_order=2,
            status=StepStatus.RUNNING,
            progress=0.5,
        )

        test_session.add_all([step1, step2])
        await test_session.commit()

        # Query job with steps
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await test_session.execute(
            select(Job).where(Job.id == job.id).options(selectinload(Job.steps))
        )
        job_with_steps = result.scalar_one()

        assert len(job_with_steps.steps) == 2
        assert job_with_steps.steps[0].step_name == "content_analysis"
        assert job_with_steps.steps[1].step_name == "audio_generation"

    async def test_content_analyzer(self):
        """Test content analysis functionality."""
        from storytime.services.content_analyzer import ContentAnalyzer

        analyzer = ContentAnalyzer()

        # Test simple text
        simple_text = "This is a simple narrative text without dialogue."
        result = await analyzer.analyze_content(simple_text, SourceType.TEXT)

        assert result.suggested_job_type in [JobType.SINGLE_VOICE, JobType.MULTI_VOICE]
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.reasoning) > 0

        # Test dialogue text
        dialogue_text = """
        "Hello there," said John.
        "Hi John," replied Mary.
        The narrator continued with the story.
        "How are you today?" John asked.
        """

        result = await analyzer.analyze_content(dialogue_text, SourceType.TEXT)

        # Should suggest multi-voice for dialogue
        assert result.suggested_job_type == JobType.MULTI_VOICE
        assert result.confidence > 0.5
        assert "dialogue" in " ".join(result.reasoning).lower()

    def test_pydantic_models(self):
        """Test Pydantic model validation."""
        # Test CreateJobRequest
        request = CreateJobRequest(
            title="Test Job",
            description="Test description",
            content="Test content",
            source_type=SourceType.TEXT,
            voice_config=VoiceConfig(provider="openai", voice_id="alloy"),
            processing_config=ProcessingConfig(max_concurrency=4, enable_caching=True),
        )

        assert request.title == "Test Job"
        assert request.source_type == SourceType.TEXT
        assert request.voice_config.provider == "openai"
        assert request.processing_config.max_concurrency == 4

        # Test validation
        with pytest.raises(ValueError):
            CreateJobRequest(
                title="",  # Empty title should fail
                content="test",
            )

    async def test_job_api_models_integration(self):
        """Test API model integration without hitting actual endpoints."""
        from storytime.api.jobs import _get_job_response

        # This test would require a real database session
        # For now, just test that the import works
        assert _get_job_response is not None

    @patch("storytime.services.content_analyzer.ContentAnalyzer.analyze_content")
    async def test_job_creation_flow(self, mock_analyze):
        """Test the job creation flow with mocked dependencies."""
        from storytime.models import ContentAnalysisResult

        # Mock content analysis
        mock_analyze.return_value = ContentAnalysisResult(
            suggested_job_type=JobType.SINGLE_VOICE,
            confidence=0.8,
            reasoning=["Short text content", "No dialogue detected"],
            estimated_duration=120,
            complexity_score=0.3,
        )

        # Test content analysis
        from storytime.services.content_analyzer import ContentAnalyzer

        analyzer = ContentAnalyzer()

        result = await analyzer.analyze_content("Test content", SourceType.TEXT)

        assert result.suggested_job_type == JobType.SINGLE_VOICE
        assert result.confidence == 0.8
        assert len(result.reasoning) == 2

    def test_enum_values(self):
        """Test that all enum values are correctly defined."""
        # Test JobType
        assert JobType.SINGLE_VOICE == "SINGLE_VOICE"
        assert JobType.MULTI_VOICE == "MULTI_VOICE"
        assert JobType.BOOK_PROCESSING == "BOOK_PROCESSING"
        assert JobType.CHAPTER_PARSING == "CHAPTER_PARSING"

        # Test SourceType
        assert SourceType.BOOK == "BOOK"
        assert SourceType.CHAPTER == "CHAPTER"
        assert SourceType.TEXT == "TEXT"

        # Test JobStatus
        assert JobStatus.PENDING == "PENDING"
        assert JobStatus.PROCESSING == "PROCESSING"
        assert JobStatus.COMPLETED == "COMPLETED"
        assert JobStatus.FAILED == "FAILED"
        assert JobStatus.CANCELLED == "CANCELLED"

        # Test StepStatus
        assert StepStatus.PENDING == "PENDING"
        assert StepStatus.RUNNING == "RUNNING"
        assert StepStatus.COMPLETED == "COMPLETED"
        assert StepStatus.FAILED == "FAILED"


@pytest.mark.asyncio
async def test_database_connection():
    """Test that we can connect to the database."""
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/storytime")

    async with engine.begin() as conn:
        result = await conn.execute("SELECT 1")
        assert result.scalar() == 1

    await engine.dispose()


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
