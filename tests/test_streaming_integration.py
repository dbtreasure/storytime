"""Integration tests for audio streaming functionality."""

from datetime import datetime

import pytest

from storytime.database import Job, JobStatus
from storytime.infrastructure.spaces import SpacesClient


@pytest.mark.asyncio
async def test_streaming_url_format():
    """Test that streaming URLs have correct format and parameters."""
    spaces_client = SpacesClient()

    # Test key
    test_key = "jobs/test-job-id/audio.mp3"

    # Get both types of URLs
    download_url = await spaces_client.get_presigned_download_url(test_key)
    streaming_url = await spaces_client.get_streaming_url(test_key)

    # Both should be strings starting with https
    assert isinstance(download_url, str)
    assert isinstance(streaming_url, str)
    assert download_url.startswith("https://")
    assert streaming_url.startswith("https://")

    # Streaming URL should have response parameters
    assert "response-content-disposition=inline" in streaming_url
    assert "response-content-type=audio%2Fmpeg" in streaming_url
    assert "response-cache-control=public" in streaming_url

    # Download URL should not have these parameters
    assert "response-content-disposition" not in download_url
    assert "response-content-type" not in download_url.lower()


@pytest.mark.asyncio
async def test_job_audio_endpoint_returns_both_urls(client, auth_headers):
    """Test that the job audio endpoint returns both download and streaming URLs."""
    # Create a completed job with audio output
    job_data = {
        "title": "Test Audio Book",
        "description": "Test description",
        "content": "This is test content for audio generation.",
        "file_key": None,
        "voice_config": None,
    }

    # Create job
    create_response = await client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
    assert create_response.status_code == 200
    job_id = create_response.json()["id"]

    # Simulate job completion (in real scenario, this would be done by the worker)
    # This is a simplified version for testing
    from storytime.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        # Update job to completed status with output file
        from sqlalchemy import update

        await db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.COMPLETED,
                output_file_key=f"jobs/{job_id}/audio.mp3",
                completed_at=datetime.utcnow(),
                result_data={
                    "duration_seconds": 120.5,
                    "file_size_bytes": 1024000,
                },
            )
        )
        await db.commit()

    # Get audio URLs
    audio_response = await client.get(f"/api/v1/jobs/{job_id}/audio", headers=auth_headers)
    assert audio_response.status_code == 200

    audio_data = audio_response.json()
    assert "download_url" in audio_data
    assert "streaming_url" in audio_data
    assert "file_key" in audio_data
    assert "content_type" in audio_data

    # Verify URLs are different
    assert audio_data["download_url"] != audio_data["streaming_url"]

    # Verify content type
    assert audio_data["content_type"] == "audio/mpeg"


@pytest.mark.asyncio
async def test_streaming_endpoints(client, auth_headers):
    """Test the dedicated streaming endpoints."""
    # Create a completed job with audio output
    job_data = {
        "title": "Test Audio Book",
        "description": "Test description",
        "content": "This is test content for audio generation.",
        "file_key": None,
        "voice_config": None,
    }

    # Create job
    create_response = await client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
    assert create_response.status_code == 200
    job_id = create_response.json()["id"]

    # Simulate job completion
    from storytime.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        from sqlalchemy import update

        await db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.COMPLETED,
                output_file_key=f"jobs/{job_id}/audio.mp3",
                completed_at=datetime.utcnow(),
                result_data={
                    "duration_seconds": 120.5,
                    "file_size_bytes": 1024000,
                    "format": "audio/mpeg",
                },
            )
        )
        await db.commit()

    # Test streaming URL endpoint
    stream_response = await client.get(f"/api/v1/audio/{job_id}/stream", headers=auth_headers)
    assert stream_response.status_code == 200

    stream_data = stream_response.json()
    assert "streaming_url" in stream_data
    assert "expires_at" in stream_data
    assert "file_key" in stream_data
    assert "content_type" in stream_data

    # Test metadata endpoint
    metadata_response = await client.get(f"/api/v1/audio/{job_id}/metadata", headers=auth_headers)
    assert metadata_response.status_code == 200

    metadata = metadata_response.json()
    assert metadata["job_id"] == job_id
    assert metadata["title"] == "Test Audio Book"
    assert metadata["format"] == "audio/mpeg"
    assert metadata["duration"] == 120.5
    assert metadata["file_size"] == 1024000

    # Test playlist endpoint
    playlist_response = await client.get(f"/api/v1/audio/{job_id}/playlist", headers=auth_headers)
    assert playlist_response.status_code == 200

    playlist = playlist_response.text
    assert playlist.startswith("#EXTM3U")
    assert "Test Audio Book" in playlist
    assert "https://" in playlist
