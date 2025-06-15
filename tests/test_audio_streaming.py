"""Tests for audio streaming API endpoints."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.api.streaming import (
    get_streaming_url,
    get_audio_metadata,
    get_playlist,
    _get_user_job,
)
from storytime.database import Job, JobStatus, User


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = MagicMock(spec=User)
    user.id = str(uuid4())
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_completed_job():
    """Create a mock completed job with audio output."""
    job = MagicMock(spec=Job)
    job.id = str(uuid4())
    job.user_id = "test-user-id"
    job.title = "Test Audio Book"
    job.status = JobStatus.COMPLETED
    job.output_file_key = "jobs/test-job-id/audio.mp3"
    job.created_at = datetime.utcnow()
    job.completed_at = datetime.utcnow()
    job.result_data = {
        "duration_seconds": 120.5,
        "file_size_bytes": 1024000,
    }
    return job


@pytest.fixture
def mock_incomplete_job():
    """Create a mock incomplete job."""
    job = MagicMock(spec=Job)
    job.id = str(uuid4())
    job.user_id = "test-user-id"
    job.status = JobStatus.PROCESSING
    job.output_file_key = None
    return job


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
async def test_get_streaming_url_success(mock_user, mock_completed_job, mock_db_session):
    """Test successful streaming URL generation."""
    job_id = mock_completed_job.id
    
    # Mock database query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_completed_job
    mock_db_session.execute.return_value = mock_result
    
    # Mock SpacesClient
    with patch("storytime.api.streaming.SpacesClient") as mock_spaces_client:
        mock_client_instance = mock_spaces_client.return_value
        mock_client_instance.get_streaming_url = AsyncMock(
            return_value="https://example.com/streaming-url"
        )
        
        # Call the endpoint function
        result = await get_streaming_url(job_id, mock_user, mock_db_session)
        
        # Verify the result
        assert "streaming_url" in result
        assert result["streaming_url"] == "https://example.com/streaming-url"
        assert "expires_at" in result
        assert "file_key" in result
        assert result["file_key"] == mock_completed_job.output_file_key
        assert result["content_type"] == "audio/mpeg"
        
        # Verify SpacesClient was called correctly
        mock_client_instance.get_streaming_url.assert_called_once_with(
            key=mock_completed_job.output_file_key,
            expires_in=3600
        )


@pytest.mark.asyncio
async def test_get_streaming_url_job_not_complete(mock_user, mock_incomplete_job, mock_db_session):
    """Test streaming URL request for incomplete job."""
    job_id = mock_incomplete_job.id
    
    # Mock database query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_incomplete_job
    mock_db_session.execute.return_value = mock_result
    
    # Call should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await get_streaming_url(job_id, mock_user, mock_db_session)
    
    assert exc_info.value.status_code == 400
    assert "not completed" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_audio_metadata_success(mock_user, mock_completed_job, mock_db_session):
    """Test successful audio metadata retrieval."""
    job_id = mock_completed_job.id
    
    # Mock database query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_completed_job
    mock_db_session.execute.return_value = mock_result
    
    # Call the endpoint function
    result = await get_audio_metadata(job_id, mock_user, mock_db_session)
    
    # Verify the result
    assert result["job_id"] == job_id
    assert result["title"] == mock_completed_job.title
    assert result["status"] == JobStatus.COMPLETED
    assert result["format"] == "audio/mpeg"
    assert result["duration"] == 120.5
    assert result["file_size"] == 1024000
    assert "created_at" in result
    assert "completed_at" in result


@pytest.mark.asyncio
async def test_get_playlist_single_file(mock_user, mock_completed_job, mock_db_session):
    """Test playlist generation for single-file audio."""
    job_id = mock_completed_job.id
    
    # Mock database query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_completed_job
    mock_db_session.execute.return_value = mock_result
    
    # Mock SpacesClient
    with patch("storytime.api.streaming.SpacesClient") as mock_spaces_client:
        mock_client_instance = mock_spaces_client.return_value
        mock_client_instance.get_streaming_url = AsyncMock(
            return_value="https://example.com/streaming-url"
        )
        
        # Call the endpoint function
        result = await get_playlist(job_id, mock_user, mock_db_session)
        
        # Verify the playlist format
        assert result.startswith("#EXTM3U\n")
        assert f"#EXTINF:-1,{mock_completed_job.title}" in result
        assert "https://example.com/streaming-url" in result


@pytest.mark.asyncio
async def test_get_playlist_multi_chapter(mock_user, mock_completed_job, mock_db_session):
    """Test playlist generation for multi-chapter audio."""
    job_id = mock_completed_job.id
    
    # Add chapter data to the job
    mock_completed_job.result_data = {
        "chapters": [
            {
                "file_key": "jobs/test-job-id/chapter_1.mp3",
                "title": "Chapter 1",
                "duration": 60,
                "order": 1,
            },
            {
                "file_key": "jobs/test-job-id/chapter_2.mp3",
                "title": "Chapter 2",
                "duration": 65,
                "order": 2,
            },
        ]
    }
    
    # Mock database query
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_completed_job
    mock_db_session.execute.return_value = mock_result
    
    # Mock SpacesClient
    with patch("storytime.api.streaming.SpacesClient") as mock_spaces_client:
        mock_client_instance = mock_spaces_client.return_value
        mock_client_instance.get_streaming_url = AsyncMock(
            side_effect=[
                "https://example.com/chapter1-url",
                "https://example.com/chapter2-url",
            ]
        )
        
        # Call the endpoint function
        result = await get_playlist(job_id, mock_user, mock_db_session)
        
        # Verify the playlist format
        assert result.startswith("#EXTM3U\n")
        assert "#EXTINF:60,Chapter 1" in result
        assert "#EXTINF:65,Chapter 2" in result
        assert "https://example.com/chapter1-url" in result
        assert "https://example.com/chapter2-url" in result


@pytest.mark.asyncio
async def test_get_user_job_not_found(mock_user, mock_db_session):
    """Test _get_user_job when job doesn't exist."""
    job_id = str(uuid4())
    user_id = mock_user.id
    
    # Mock database query returning None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_result
    
    # Call should raise HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await _get_user_job(job_id, user_id, mock_db_session)
    
    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail)