"""Audio streaming API endpoints with resume support."""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.api.auth import get_current_user
from storytime.database import Job, JobStatus, User, PlaybackProgress, get_db
from storytime.infrastructure.spaces import SpacesClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/audio", tags=["Audio Streaming"])


@router.get("/{job_id}/stream")
async def get_streaming_url(
    job_id: str, 
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get pre-signed streaming URL for complete audio file."""
    logger.info(f"Getting streaming URL for job {job_id} for user {current_user.id}")
    
    # Get job and verify ownership
    job = await _get_user_job(job_id, current_user.id, db)
    
    # Check if job is completed and has audio output
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400, 
            detail=f"Job is not completed (status: {job.status})"
        )
    
    if not job.output_file_key:
        raise HTTPException(
            status_code=404, 
            detail="No audio output available for this job"
        )
    
    # Generate streaming URL with appropriate headers
    spaces_client = SpacesClient()
    streaming_url = await spaces_client.get_streaming_url(
        key=job.output_file_key,
        expires_in=3600  # 1 hour default
    )
    
    # Get resume information if available
    resume_info = await _get_resume_info(job_id, current_user.id, db)
    
    return {
        "streaming_url": streaming_url,
        "expires_at": (datetime.utcnow() + timedelta(seconds=3600)).isoformat(),
        "file_key": job.output_file_key,
        "content_type": "audio/mpeg",
        "resume_info": resume_info
    }


@router.get("/{job_id}/metadata")
async def get_audio_metadata(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """Get audio metadata including duration and format."""
    logger.info(f"Getting audio metadata for job {job_id} for user {current_user.id}")
    
    # Get job and verify ownership
    job = await _get_user_job(job_id, current_user.id, db)
    
    # Check if job is completed
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed (status: {job.status})"
        )
    
    # Extract metadata from result_data if available
    metadata = {
        "job_id": job_id,
        "title": job.title,
        "status": job.status,
        "format": "audio/mpeg",
        "duration": None,  # Will be populated from result_data
        "file_size": None,  # Will be populated from result_data
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    }
    
    # Extract additional metadata from result_data if available
    if job.result_data:
        metadata["duration"] = job.result_data.get("duration_seconds")
        metadata["file_size"] = job.result_data.get("file_size_bytes")
        metadata["chapters"] = job.result_data.get("chapters", [])
    
    return metadata


@router.get("/{job_id}/playlist", response_class=Response)
async def get_playlist(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Response:
    """Get M3U playlist for multi-chapter audiobooks."""
    logger.info(f"Getting playlist for job {job_id} for user {current_user.id}")
    
    # Get job and verify ownership
    job = await _get_user_job(job_id, current_user.id, db)
    
    # Check if job is completed
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is not completed (status: {job.status})"
        )
    
    # For single-file audio, generate simple playlist
    if not job.result_data or "chapters" not in job.result_data:
        # Single file playlist
        spaces_client = SpacesClient()
        streaming_url = await spaces_client.get_streaming_url(
            key=job.output_file_key,
            expires_in=3600
        )
        
        playlist = "#EXTM3U\n"
        playlist += f"#EXTINF:-1,{job.title}\n"
        playlist += f"{streaming_url}\n"
        
        return Response(content=playlist, media_type="audio/x-mpegurl")
    
    # Multi-chapter playlist
    chapters = job.result_data.get("chapters", [])
    if not chapters:
        raise HTTPException(
            status_code=404,
            detail="No chapter information available"
        )
    
    spaces_client = SpacesClient()
    playlist = "#EXTM3U\n"
    
    for chapter in chapters:
        # Generate URL for each chapter
        chapter_key = chapter.get("file_key")
        if not chapter_key:
            continue
            
        streaming_url = await spaces_client.get_streaming_url(
            key=chapter_key,
            expires_in=3600
        )
        
        duration = chapter.get("duration", -1)
        title = chapter.get("title", f"Chapter {chapter.get('order', '?')}")
        
        playlist += f"#EXTINF:{duration},{title}\n"
        playlist += f"{streaming_url}\n"
    
    return Response(content=playlist, media_type="audio/x-mpegurl")


# Helper functions

async def _get_user_job(job_id: str, user_id: str, db: AsyncSession) -> Job:
    """Get job and verify it belongs to the user."""
    result = await db.execute(
        select(Job).where(and_(Job.id == job_id, Job.user_id == user_id))
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found or access denied"
        )
    
    return job


async def _get_resume_info(job_id: str, user_id: str, db: AsyncSession) -> dict:
    """Get resume information for the job."""
    result = await db.execute(
        select(PlaybackProgress).where(
            and_(
                PlaybackProgress.job_id == job_id,
                PlaybackProgress.user_id == user_id
            )
        )
    )
    progress = result.scalar_one_or_none()
    
    if not progress:
        return {
            "has_progress": False,
            "resume_position": 0.0,
            "percentage_complete": 0.0
        }
    
    return {
        "has_progress": True,
        "resume_position": progress.resume_position,
        "percentage_complete": progress.percentage_complete,
        "last_played_at": progress.last_played_at.isoformat(),
        "current_chapter_id": progress.current_chapter_id,
        "current_chapter_position": progress.current_chapter_position
    }