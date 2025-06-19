"""Tests for playback progress tracking API endpoints."""

import pytest
from datetime import datetime
from uuid import uuid4

from storytime.database import Job, JobStatus, User, PlaybackProgress
from storytime.models import (
    UpdateProgressRequest,
    PlaybackProgressResponse,
    ResumeInfoResponse,
)


class TestProgressModel:
    """Test PlaybackProgress model methods."""

    def test_is_completed_property(self):
        """Test is_completed property."""
        progress = PlaybackProgress()
        
        # Not completed
        progress.percentage_complete = 0.5
        assert progress.is_completed is False
        
        # Completed
        progress.percentage_complete = 0.96
        assert progress.is_completed is True

    def test_resume_position_property(self):
        """Test resume_position property."""
        progress = PlaybackProgress()
        progress.position_seconds = 125.5
        
        assert progress.resume_position == 125.5

    def test_update_progress_method(self):
        """Test update_progress method."""
        progress = PlaybackProgress()
        
        # Update with duration
        progress.update_progress(60.0, 120.0)
        
        assert progress.position_seconds == 60.0
        assert progress.duration_seconds == 120.0
        assert progress.percentage_complete == 0.5
        assert isinstance(progress.last_played_at, datetime)

    def test_update_progress_without_duration(self):
        """Test update_progress method without duration."""
        progress = PlaybackProgress()
        progress.duration_seconds = 120.0  # Set existing duration
        
        # Update without new duration
        progress.update_progress(90.0)
        
        assert progress.position_seconds == 90.0
        assert progress.duration_seconds == 120.0
        assert progress.percentage_complete == 0.75

    def test_update_progress_negative_position(self):
        """Test update_progress with negative position."""
        progress = PlaybackProgress()
        
        # Negative position should be clamped to 0
        progress.update_progress(-10.0, 120.0)
        
        assert progress.position_seconds == 0.0
        assert progress.percentage_complete == 0.0


@pytest.mark.asyncio
async def test_progress_api_integration():
    """Simple integration test for progress tracking API endpoints."""
    # Test that we can import and instantiate the models
    request = UpdateProgressRequest(
        position_seconds=60.0,
        duration_seconds=120.0,
        current_chapter_id="chapter-1",
        current_chapter_position=30.0
    )
    
    assert request.position_seconds == 60.0
    assert request.duration_seconds == 120.0
    assert request.current_chapter_id == "chapter-1"
    
    # Test response model creation
    response = PlaybackProgressResponse(
        id=str(uuid4()),
        user_id=str(uuid4()),
        job_id=str(uuid4()),
        position_seconds=60.0,
        duration_seconds=120.0,
        percentage_complete=0.5,
        current_chapter_id="chapter-1",
        current_chapter_position=30.0,
        is_completed=False,
        last_played_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    assert response.position_seconds == 60.0
    assert response.percentage_complete == 0.5
    
    # Test resume info response
    resume_info = ResumeInfoResponse(
        has_progress=True,
        resume_position=60.0,
        percentage_complete=0.5,
        last_played_at=datetime.utcnow(),
        current_chapter_id="chapter-1",
        current_chapter_position=30.0
    )
    
    assert resume_info.has_progress is True
    assert resume_info.resume_position == 60.0