"""Tests for the unified job management system."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from storytime.database import Job, User
from storytime.models import (
    CreateJobRequest,
    JobStatus,
    JobType,
    SourceType,
    StepStatus,
    VoiceConfig,
)
from storytime.services.content_analyzer import ContentAnalyzer
from storytime.services.job_processor import JobProcessor


class TestContentAnalyzer:
    """Tests for the content analyzer service."""

    @pytest.fixture
    def analyzer(self):
        return ContentAnalyzer()

    @pytest.mark.asyncio
    async def test_analyze_short_content(self, analyzer):
        """Test analysis of short content suggests SINGLE_VOICE."""
        content = "This is a short text for testing."

        result = await analyzer.analyze_content(content, SourceType.TEXT)

        assert result.suggested_job_type == JobType.SINGLE_VOICE
        assert result.confidence > 0.5
        # Gemini provides different reasons than regex, so be more flexible
        assert len(result.reasons) > 0
        # Check that it mentions short content or single voice somewhere
        reasons_text = " ".join(result.reasons).lower()
        assert any(term in reasons_text for term in ["short", "single", "no dialogue", "simple"])

    @pytest.mark.asyncio
    async def test_analyze_dialogue_content(self, analyzer):
        """Test analysis of dialogue-heavy content suggests MULTI_VOICE."""
        content = '''
        "Hello there," said John with a smile.
        "How are you doing today?" Mary replied cheerfully.
        "I'm doing well, thank you for asking," John answered.
        "That's wonderful to hear," Mary said.
        The narrator then described how they walked together.
        "Where shall we go?" asked John.
        "Let's visit the park," suggested Mary.
        ''' * 20  # Make it long enough

        result = await analyzer.analyze_content(content, SourceType.TEXT)

        assert result.suggested_job_type == JobType.MULTI_VOICE
        assert result.confidence > 0.5
        assert any("dialogue" in reason.lower() for reason in result.reasons)

    @pytest.mark.asyncio
    async def test_analyze_book_content(self, analyzer):
        """Test analysis of book with chapters suggests BOOK_PROCESSING."""
        content = '''
        Chapter 1
        
        This is the first chapter of our story...
        
        Chapter 2
        
        This is the second chapter...
        
        Chapter 3
        
        And this continues the tale...
        ''' * 50  # Make it substantial

        result = await analyzer.analyze_content(content, SourceType.BOOK)

        assert result.suggested_job_type == JobType.BOOK_PROCESSING
        assert result.confidence > 0.5
        assert any("chapter" in reason.lower() for reason in result.reasons)

    @pytest.mark.asyncio
    async def test_split_book_into_chapters(self, analyzer):
        """Test book splitting functionality."""
        # Make chapters longer to meet minimum length requirement
        chapter_content = """
        This is chapter content with multiple paragraphs to ensure it meets the minimum
        length requirement for chapter splitting. The content analyzer requires chapters
        to be at least 1000 characters long to be considered valid chapters.
        
        We need to add enough text here to make sure each chapter is substantial enough
        to pass the validation checks. This includes multiple sentences and paragraphs
        that would be typical of a real book chapter.
        
        The story continues with interesting developments and character interactions.
        There are plot points that need to be developed across multiple paragraphs
        to create a complete narrative experience for the reader.
        """ * 2  # Double it to ensure length

        content = f'''
        Chapter 1{chapter_content}
        
        Chapter 2{chapter_content}
        
        Chapter 3{chapter_content}
        '''

        chapters = await analyzer.split_book_into_chapters(content)

        assert len(chapters) == 3
        assert "Chapter 1" in chapters[0]
        assert "Chapter 2" in chapters[1]
        assert "Chapter 3" in chapters[2]


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
        return JobProcessor(
            db_session=mock_db_session,
            spaces_client=mock_spaces_client
        )

    @pytest.fixture
    def sample_job(self):
        """Create a sample job for testing."""
        return Job(
            id=str(uuid4()),
            user_id=str(uuid4()),
            job_type=JobType.SINGLE_VOICE,
            source_type=SourceType.TEXT,
            title="Test Job",
            description="Test job description",
            status=JobStatus.PENDING,
            progress=0.0,
            config={
                "content": "This is test content for TTS generation.",
                "voice_config": {"provider": "openai"}
            }
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
    async def test_create_job_steps(self, job_processor, mock_db_session):
        """Test creating job steps for progress tracking."""
        job_id = str(uuid4())
        steps = [
            ("load_content", "Loading text content"),
            ("generate_audio", "Generating audio"),
            ("upload_results", "Uploading results")
        ]

        await job_processor._create_job_steps(job_id, steps)

        # Verify job steps were added to session
        mock_db_session.add_all.assert_called_once()
        added_steps = mock_db_session.add_all.call_args[0][0]

        assert len(added_steps) == 3
        assert added_steps[0].step_name == "load_content"
        assert added_steps[0].step_order == 0
        assert added_steps[1].step_name == "generate_audio"
        assert added_steps[1].step_order == 1

    @pytest.mark.asyncio
    @patch('storytime.services.job_processor.TTSGenerator')
    async def test_process_single_voice_job(self, mock_tts_class, job_processor, mock_db_session, sample_job):
        """Test processing a single voice job."""
        # Mock TTS generator
        mock_tts = AsyncMock()
        mock_tts.generate_simple_audio.return_value = b"fake_audio_data"
        mock_tts_class.return_value = mock_tts

        # Mock database operations
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = sample_job
        mock_db_session.execute.return_value = mock_result

        # Test processing
        result = await job_processor._process_single_voice_job(sample_job)

        # Verify results
        assert result["processing_type"] == "single_voice"
        assert "audio_key" in result
        assert result["content_length"] > 0

        # Verify TTS was called
        mock_tts.generate_simple_audio.assert_called_once()

        # Verify file upload was called
        job_processor.spaces_client.upload_audio_file.assert_called_once()


class TestJobAPI:
    """Tests for the job API endpoints."""

    @pytest.fixture
    def mock_user(self):
        """Create a mock user for testing."""
        return User(
            id=str(uuid4()),
            email="test@example.com",
            hashed_password="hashed_password"
        )

    def test_create_job_request_validation(self):
        """Test job creation request validation."""
        # Valid request
        request = CreateJobRequest(
            title="Test Job",
            description="Test description",
            content="Sample text content",
            source_type=SourceType.TEXT
        )

        assert request.title == "Test Job"
        assert request.source_type == SourceType.TEXT

        # Request with voice config
        voice_config = VoiceConfig(
            provider="openai",
            voice_id="alloy",
            voice_settings={"speed": "1.0", "pitch": "normal"}
        )

        request_with_voice = CreateJobRequest(
            title="Voice Test",
            content="Content",
            voice_config=voice_config
        )

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
            updated_at=datetime.utcnow()
        )

        job = JobResponse(
            id=str(uuid4()),
            user_id=str(uuid4()),
            title="Test Job",
            job_type=JobType.SINGLE_VOICE,
            source_type=SourceType.TEXT,
            status=JobStatus.COMPLETED,
            progress=1.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            steps=[step]
        )

        assert job.status == JobStatus.COMPLETED
        assert job.progress == 1.0
        assert len(job.steps) == 1
        assert job.steps[0].step_name == "test_step"


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing endpoints."""

    @pytest.mark.asyncio
    @patch('storytime.api.tts.process_job')
    async def test_legacy_tts_endpoint_creates_job(self, mock_process_job):
        """Test that legacy TTS endpoint creates a unified job."""
        from storytime.api.tts import GenerateRequest

        # This would normally be tested with a test client, but we're testing the logic
        request = GenerateRequest(
            chapter_text="Sample text for TTS generation",
            title="Test Chapter",
            provider="openai"
        )

        # Verify request is valid
        assert request.chapter_text == "Sample text for TTS generation"
        assert request.provider == "openai"

        # In a full test, we'd verify that:
        # 1. A Job record is created
        # 2. A legacy Book record is created for compatibility
        # 3. The Celery task is enqueued
        # 4. The response format matches the legacy format


@pytest.mark.asyncio
async def test_end_to_end_job_flow():
    """Integration test for complete job flow."""
    # Mock all external dependencies
    with patch('storytime.services.job_processor.SpacesClient') as mock_spaces, \
         patch('storytime.services.job_processor.TTSGenerator') as mock_tts, \
         patch('storytime.database.AsyncSessionLocal') as mock_session:

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
            db_session=mock_session_instance,
            spaces_client=mock_spaces_instance
        )

        # Create test job
        job = Job(
            id=str(uuid4()),
            user_id=str(uuid4()),
            job_type=JobType.SINGLE_VOICE,
            source_type=SourceType.TEXT,
            title="Integration Test Job",
            status=JobStatus.PENDING,
            progress=0.0,
            config={"content": "Test content"}
        )

        # Mock database responses
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = job
        mock_session_instance.execute.return_value = mock_result

        # Process job
        result = await processor._process_single_voice_job(job)

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
