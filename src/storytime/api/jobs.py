"""Unified job management API endpoints."""

import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.api.auth import get_current_user
from storytime.database import Job, JobStatus, JobStep, User, get_db
from storytime.infrastructure.spaces import SpacesClient
from storytime.models import (
    CreateJobRequest,
    JobAudioResponse,
    JobListResponse,
    JobResponse,
    JobStepResponse,
    JobType,
    BookChaptersResponse,
    MessageResponse,
)
from storytime.worker.tasks import process_job

# JobProcessor is now simplified and always available

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.post("", response_model=JobResponse)
async def create_job(
    request: CreateJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Create a new job with automatic type detection."""
    logger.info(f"Creating job for user {current_user.id}: {request.title}")

    try:
        # Validate input
        if not request.content and not request.file_key:
            raise HTTPException(
                status_code=400, detail="Either content or file_key must be provided"
            )

        # Create job record
        job = Job(
            id=str(uuid4()),
            user_id=current_user.id,
            title=request.title,
            description=request.description,
            status=JobStatus.PENDING,
            progress=0.0,
            config={
                "job_type": request.job_type.value,
                "content": request.content,
                "voice_config": request.voice_config.model_dump() if request.voice_config else {},
                "processing_mode": request.processing_mode,
            },
            input_file_key=request.file_key,
        )

        db.add(job)
        await db.commit()
        await db.refresh(job)

        # Schedule job processing in Celery (if available)
        try:
            process_job.delay(job.id)  # type: ignore[attr-defined]
            logger.info(f"Job {job.id} scheduled for processing")
        except Exception as e:
            logger.warning(f"Could not schedule job processing: {e}")
            # Job is created but not scheduled - can be processed later

        # Return job response
        return await _get_job_response(job.id, db)

    except Exception as e:
        logger.error(f"Failed to create job: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create job: {e!s}")


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: JobStatus | None = Query(None, description="Filter by job status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """List jobs for the current user with filtering and pagination."""
    logger.info(f"Listing jobs for user {current_user.id}")

    try:
        # Build query with filters
        query = select(Job).where(Job.user_id == current_user.id)

        if status:
            query = query.where(Job.status == status)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        query = query.order_by(Job.created_at.desc()).offset(offset).limit(page_size)

        # Execute query
        result = await db.execute(query)
        jobs = result.scalars().all()

        # Convert to response models
        job_responses = []
        for job in jobs:
            job_response = await _get_job_response(job.id, db)
            job_responses.append(job_response)

        total_pages = (total + page_size - 1) // page_size

        return JobListResponse(
            jobs=job_responses, total=total, page=page, page_size=page_size, total_pages=total_pages
        )

    except Exception as e:
        logger.error(f"Failed to list jobs: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {e!s}")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> JobResponse:
    """Get detailed job information including steps."""
    logger.info(f"Getting job {job_id} for user {current_user.id}")

    try:
        # Verify job exists and belongs to user
        job = await _get_user_job(job_id, current_user.id, db)
        return await _get_job_response(job_id, db)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job: {e!s}")


@router.delete("/{job_id}", response_model=MessageResponse)
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Cancel a job."""
    logger.info(f"Cancelling job {job_id} for user {current_user.id}")

    try:
        # Verify job exists and belongs to user
        job = await _get_user_job(job_id, current_user.id, db)

        # Only allow cancellation of pending or processing jobs
        if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
            raise HTTPException(
                status_code=400, detail=f"Cannot cancel job with status {job.status}"
            )

        # Update job status to cancelled
        await db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.CANCELLED,
                updated_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
        )
        await db.commit()

        return MessageResponse(message="Job cancelled successfully")

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {e!s}")


@router.get("/{job_id}/steps", response_model=list[JobStepResponse])
async def get_job_steps(
    job_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[JobStepResponse]:
    """Get detailed step information for a job."""
    logger.info(f"Getting steps for job {job_id} for user {current_user.id}")

    try:
        # Verify job exists and belongs to user
        await _get_user_job(job_id, current_user.id, db)

        # Get job steps
        result = await db.execute(
            select(JobStep).where(JobStep.job_id == job_id).order_by(JobStep.step_order)
        )
        steps = result.scalars().all()

        return [
            JobStepResponse(
                id=step.id,
                step_name=step.step_name,
                step_order=step.step_order,
                status=step.status,
                progress=step.progress,
                error_message=step.error_message,
                step_metadata=step.step_metadata,
                created_at=step.created_at,
                updated_at=step.updated_at,
                started_at=step.started_at,
                completed_at=step.completed_at,
                duration=step.duration,
            )
            for step in steps
        ]

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get job steps for {job_id}: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job steps: {e!s}")


@router.get("/{job_id}/audio", response_model=JobAudioResponse)
async def get_job_audio(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobAudioResponse:
    """Download or stream the audio result from a completed job."""
    logger.info(f"Getting audio for job {job_id} for user {current_user.id}")

    try:
        # Verify job exists and belongs to user
        job = await _get_user_job(job_id, current_user.id, db)

        # Check if job is completed and has audio output
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=400, detail=f"Job is not completed (status: {job.status})"
            )

        if not job.output_file_key:
            raise HTTPException(status_code=404, detail="No audio output available for this job")

        # Get presigned URLs for both download and streaming
        spaces_client = SpacesClient()
        download_url = await spaces_client.get_presigned_download_url(job.output_file_key)
        streaming_url = await spaces_client.get_streaming_url(job.output_file_key)

        return JobAudioResponse(
            download_url=download_url,
            streaming_url=streaming_url,
            file_key=job.output_file_key,
            content_type="audio/mpeg",
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get audio for job {job_id}: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job audio: {e!s}")


@router.get("/{job_id}/chapters", response_model=BookChaptersResponse)
async def get_book_chapters(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BookChaptersResponse:
    """Get chapter processing results for a book job."""
    logger.info(f"Getting chapters for book job {job_id} for user {current_user.id}")

    try:
        # Verify job exists and belongs to user
        job = await _get_user_job(job_id, current_user.id, db)

        # Check if this is a book processing job
        job_type = job.config.get("job_type") if job.config else None
        if job_type != JobType.BOOK_PROCESSING.value:
            raise HTTPException(
                status_code=400, detail="This endpoint is only for book processing jobs"
            )

        # Get aggregated chapter results
        from storytime.services.book_processor import BookProcessor

        book_processor = BookProcessor(db, SpacesClient())
        results = await book_processor.aggregate_chapter_results(job_id)

        return BookChaptersResponse(**results)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get chapters for job {job_id}: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get book chapters: {e!s}")


# Helper functions


async def _get_user_job(job_id: str, user_id: str, db: AsyncSession) -> Job:
    """Get job and verify it belongs to the user."""
    result = await db.execute(select(Job).where(and_(Job.id == job_id, Job.user_id == user_id)))
    job = result.scalar_one_or_none()

    if not job:
        raise ValueError(f"Job {job_id} not found or access denied")

    return job


async def _get_job_response(job_id: str, db: AsyncSession) -> JobResponse:
    """Get job with steps as response model."""
    # Get job
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise ValueError(f"Job {job_id} not found")

    # Get job steps
    steps_result = await db.execute(
        select(JobStep).where(JobStep.job_id == job_id).order_by(JobStep.step_order)
    )
    steps = steps_result.scalars().all()

    step_responses = [
        JobStepResponse(
            id=step.id,
            step_name=step.step_name,
            step_order=step.step_order,
            status=step.status,
            progress=step.progress,
            error_message=step.error_message,
            step_metadata=step.step_metadata,
            created_at=step.created_at,
            updated_at=step.updated_at,
            started_at=step.started_at,
            completed_at=step.completed_at,
            duration=step.duration,
        )
        for step in steps
    ]

    return JobResponse(
        id=job.id,
        user_id=job.user_id,
        title=job.title,
        description=job.description,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        config=job.config,
        result_data=job.result_data,
        input_file_key=job.input_file_key,
        output_file_key=job.output_file_key,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration=job.duration,
        steps=step_responses,
    )
