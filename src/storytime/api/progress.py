"""Playback progress tracking API endpoints."""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.api.auth import get_current_user
from storytime.database import PlaybackProgress, User, get_db
from storytime.models import (
    MessageResponse,
    PlaybackProgressResponse,
    ResumeInfoResponse,
    UpdateProgressRequest,
)

from .utils import get_user_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/progress", tags=["Playback Progress"])


@router.get("/{job_id}", response_model=PlaybackProgressResponse | None)
async def get_progress(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaybackProgressResponse | None:
    """Get playback progress for a specific job."""
    logger.info(f"Getting progress for job {job_id} for user {current_user.id}")

    # Verify job exists and belongs to user
    await get_user_job(job_id, current_user.id, db)

    # Get progress record
    result = await db.execute(
        select(PlaybackProgress).where(
            and_(PlaybackProgress.job_id == job_id, PlaybackProgress.user_id == current_user.id)
        )
    )
    progress = result.scalar_one_or_none()

    if not progress:
        return None

    return PlaybackProgressResponse(
        id=progress.id,
        user_id=progress.user_id,
        job_id=progress.job_id,
        position_seconds=progress.position_seconds,
        duration_seconds=progress.duration_seconds,
        percentage_complete=progress.percentage_complete,
        current_chapter_id=progress.current_chapter_id,
        current_chapter_position=progress.current_chapter_position,
        is_completed=progress.is_completed,
        last_played_at=progress.last_played_at,
        created_at=progress.created_at,
        updated_at=progress.updated_at,
    )


@router.put("/{job_id}", response_model=PlaybackProgressResponse)
async def update_progress(
    job_id: str,
    request: UpdateProgressRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PlaybackProgressResponse:
    """Update playback progress for a specific job."""
    logger.info(f"Updating progress for job {job_id} for user {current_user.id}")

    # Verify job exists and belongs to user
    await get_user_job(job_id, current_user.id, db)

    # Use UPSERT to handle concurrent requests atomically
    from sqlalchemy.dialects.postgresql import insert

    # Calculate percentage
    percentage_complete = 0.0
    if request.duration_seconds and request.duration_seconds > 0:
        percentage_complete = min(1.0, request.position_seconds / request.duration_seconds)

    now = datetime.utcnow()

    # Use PostgreSQL's INSERT ... ON CONFLICT DO UPDATE for atomic upsert
    stmt = insert(PlaybackProgress).values(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        job_id=job_id,
        position_seconds=request.position_seconds,
        duration_seconds=request.duration_seconds,
        percentage_complete=percentage_complete,
        current_chapter_id=request.current_chapter_id,
        current_chapter_position=request.current_chapter_position or 0.0,
        last_played_at=now,
        created_at=now,
        updated_at=now,
    )

    # On conflict (unique constraint), update the existing record
    stmt = stmt.on_conflict_do_update(
        constraint="unique_user_job_progress",
        set_={
            "position_seconds": stmt.excluded.position_seconds,
            "duration_seconds": stmt.excluded.duration_seconds,
            "percentage_complete": stmt.excluded.percentage_complete,
            "current_chapter_id": stmt.excluded.current_chapter_id,
            "current_chapter_position": stmt.excluded.current_chapter_position,
            "last_played_at": stmt.excluded.last_played_at,
            "updated_at": stmt.excluded.updated_at,
        },
    ).returning(PlaybackProgress)

    result = await db.execute(stmt)
    progress = result.scalar_one()
    await db.commit()

    return PlaybackProgressResponse(
        id=progress.id,
        user_id=progress.user_id,
        job_id=progress.job_id,
        position_seconds=progress.position_seconds,
        duration_seconds=progress.duration_seconds,
        percentage_complete=progress.percentage_complete,
        current_chapter_id=progress.current_chapter_id,
        current_chapter_position=progress.current_chapter_position,
        is_completed=progress.is_completed,
        last_played_at=progress.last_played_at,
        created_at=progress.created_at,
        updated_at=progress.updated_at,
    )


@router.get("/{job_id}/resume", response_model=ResumeInfoResponse)
async def get_resume_info(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResumeInfoResponse:
    """Get resume information for a specific job."""
    logger.info(f"Getting resume info for job {job_id} for user {current_user.id}")

    # Verify job exists and belongs to user
    await get_user_job(job_id, current_user.id, db)

    # Get progress record
    result = await db.execute(
        select(PlaybackProgress).where(
            and_(PlaybackProgress.job_id == job_id, PlaybackProgress.user_id == current_user.id)
        )
    )
    progress = result.scalar_one_or_none()

    if not progress:
        return ResumeInfoResponse(has_progress=False)

    return ResumeInfoResponse(
        has_progress=True,
        resume_position=progress.resume_position,
        percentage_complete=progress.percentage_complete,
        last_played_at=progress.last_played_at,
        current_chapter_id=progress.current_chapter_id,
        current_chapter_position=progress.current_chapter_position,
    )


@router.delete("/{job_id}", response_model=MessageResponse)
async def reset_progress(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Reset playback progress for a specific job."""
    logger.info(f"Resetting progress for job {job_id} for user {current_user.id}")

    # Verify job exists and belongs to user
    await get_user_job(job_id, current_user.id, db)

    # Delete progress record if it exists
    result = await db.execute(
        select(PlaybackProgress).where(
            and_(PlaybackProgress.job_id == job_id, PlaybackProgress.user_id == current_user.id)
        )
    )
    progress = result.scalar_one_or_none()

    if progress:
        await db.delete(progress)
        await db.commit()
        return MessageResponse(message="Progress reset successfully")
    else:
        return MessageResponse(message="No progress found to reset")


@router.get("/user/recent", response_model=list[PlaybackProgressResponse])
async def get_recent_progress(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PlaybackProgressResponse]:
    """Get recent playback progress for the current user."""
    logger.info(f"Getting recent progress for user {current_user.id}")

    # Get recent progress records
    result = await db.execute(
        select(PlaybackProgress)
        .where(PlaybackProgress.user_id == current_user.id)
        .order_by(PlaybackProgress.last_played_at.desc())
        .limit(limit)
    )
    progress_records = result.scalars().all()

    return [
        PlaybackProgressResponse(
            id=progress.id,
            user_id=progress.user_id,
            job_id=progress.job_id,
            position_seconds=progress.position_seconds,
            duration_seconds=progress.duration_seconds,
            percentage_complete=progress.percentage_complete,
            current_chapter_id=progress.current_chapter_id,
            current_chapter_position=progress.current_chapter_position,
            is_completed=progress.is_completed,
            last_played_at=progress.last_played_at,
            created_at=progress.created_at,
            updated_at=progress.updated_at,
        )
        for progress in progress_records
    ]


# Helper functions
