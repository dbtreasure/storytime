"""Tests for the simplified unified job management system."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from storytime.database import Job, User
from storytime.models import (
    CreateJobRequest,
    JobStatus,
    StepStatus,
    VoiceConfig,
)
from storytime.services.job_processor import JobProcessor


class TestJobProcessor:
    """Tests for the job processor service."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_spaces_client(self):
        """Mock spaces client."""
        mock = AsyncMock()
        mock.download_text_file.return_value = "Sample text content for testing."
        mock.upload_audio_file.return_value = True
        mock.upload_json_file.return_value = True
        return mock

    @pytest.fixture
    def job_processor(self, mock_db_session, mock_spaces_client):
        """Create job processor with mocked dependencies."""
        return JobProcessor(db_session=mock_db_session, spaces_client=mock_spaces_client)

    @pytest.fixture
    def sample_job(self):
        """Create a sample job for testing."""
        return Job(
            id=str(uuid4()),
            user_id=str(uuid4()),
            title="Test Job",
            description="Test job description",
            status=JobStatus.PENDING,
            progress=0.0,
            config={
                "content": "This is test content for TTS generation.",
                "voice_config": {"provider": "openai"},
            },
        )

    @pytest.mark.asyncio
    async def test_get_job(self, job_processor, mock_db_session, sample_job):
        """Test getting a job from database."""
        # Mock database response
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        result = await job_processor._get_job(sample_job.id)

        assert result == sample_job
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_job_step(self, job_processor, mock_db_session):
        """Test creating a job step for progress tracking."""
        job_id = str(uuid4())

        # Mock the add and commit operations
        mock_db_session.add = AsyncMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        result = await job_processor._create_job_step(
            job_id, "text_to_audio", 0, "Convert text to audio"
        )

        # Verify job step was added to session
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    @patch("storytime.services.job_processor.TTSGenerator")
    async def test_process_text_to_audio_job(
        self, mock_tts_class, job_processor, mock_db_session, sample_job
    ):
        """Test processing a text-to-audio job."""
        # Mock TTS generator
        mock_tts = AsyncMock()
        mock_tts.generate_simple_audio.return_value = b"fake_audio_data"
        mock_tts_class.return_value = mock_tts

        # Mock database operations and job step creation
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result
        mock_db_session.add = AsyncMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        # Mock job step for progress tracking
        from storytime.database import JobStep

        mock_step = JobStep(
            id=str(uuid4()),
            job_id=sample_job.id,
            step_name="text_to_audio",
            step_order=0,
            status=StepStatus.PENDING,
            progress=0.0,
        )
        mock_db_session.refresh.return_value = mock_step

        # Test processing
        result = await job_processor._process_text_to_audio_job(sample_job)

        # Verify results
        assert result["processing_type"] == "single_voice"
        assert "audio_key" in result
        assert result["text_length"] > 0

        # Verify TTS was called
        mock_tts.generate_simple_audio.assert_called_once()

        # Verify file upload was called
        job_processor.spaces_client.upload_audio_file.assert_called_once()


class TestJobAPI:
    """Tests for the job API endpoints."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user for testing."""
        return User(id=str(uuid4()), email="test@example.com", hashed_password="hashed_password")

    def test_create_job_request_validation(self):
        """Test job creation request validation."""
        # Valid request
        request = CreateJobRequest(
            title="Test Job",
            description="Test description",
            content="Sample text content",
            file_key=None,
            voice_config=None,
        )

        assert request.title == "Test Job"
        assert request.content == "Sample text content"

        # Request with voice config
        voice_config = VoiceConfig(
            provider="openai", voice_id="alloy", voice_settings={"speed": "1.0", "pitch": "normal"}
        )

        request_with_voice = CreateJobRequest(
            title="Voice Test",
            description=None,
            content="Content",
            file_key=None,
            voice_config=voice_config,
        )

        assert request_with_voice.voice_config is not None
        assert request_with_voice.voice_config.provider == "openai"
        assert request_with_voice.voice_config.voice_id == "alloy"

    def test_job_response_model(self):
        """Test job response model serialization."""
        from storytime.models import JobResponse, JobStepResponse

        step = JobStepResponse(
            id=str(uuid4()),
            step_name="test_step",
            step_order=0,
            status=StepStatus.COMPLETED,
            progress=1.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        job = JobResponse(
            id=str(uuid4()),
            user_id=str(uuid4()),
            title="Test Job",
            status=JobStatus.COMPLETED,
            progress=1.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            steps=[step],
        )

        assert job.status == JobStatus.COMPLETED
        assert job.progress == 1.0
        assert len(job.steps) == 1
        assert job.steps[0].step_name == "test_step"


@pytest.mark.asyncio
async def test_end_to_end_job_flow():
    """Integration test for complete job flow."""
    # Mock all external dependencies
    with (
        patch("storytime.services.job_processor.SpacesClient") as mock_spaces,
        patch("storytime.services.job_processor.TTSGenerator") as mock_tts,
        patch("storytime.database.AsyncSessionLocal") as mock_session,
    ):
        # Setup mocks
        mock_spaces_instance = AsyncMock()
        mock_spaces.return_value = mock_spaces_instance
        mock_spaces_instance.download_text_file.return_value = "Test content"
        mock_spaces_instance.upload_audio_file.return_value = True

        mock_tts_instance = AsyncMock()
        mock_tts.return_value = mock_tts_instance
        mock_tts_instance.generate_simple_audio.return_value = b"audio_data"

        mock_session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance

        # Create job processor
        processor = JobProcessor(
            db_session=mock_session_instance, spaces_client=mock_spaces_instance
        )

        # Create test job
        job = Job(
            id=str(uuid4()),
            user_id=str(uuid4()),
            title="Integration Test Job",
            status=JobStatus.PENDING,
            progress=0.0,
            config={"content": "Test content"},
        )

        # Mock database responses
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_session_instance.execute.return_value = mock_result
        mock_session_instance.add = AsyncMock()
        mock_session_instance.commit = AsyncMock()
        mock_session_instance.refresh = AsyncMock()

        # Process job
        result = await processor._process_text_to_audio_job(job)

        # Verify end-to-end flow
        assert result["processing_type"] == "single_voice"
        assert "audio_key" in result

        # Verify all components were called
        mock_tts_instance.generate_simple_audio.assert_called_once()
        mock_spaces_instance.upload_audio_file.assert_called_once()


if __name__ == "__main__":
    # Run basic tests
    asyncio.run(test_end_to_end_job_flow())
    print("✅ All tests completed successfully!")
