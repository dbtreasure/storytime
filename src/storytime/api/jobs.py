"""Unified job management API endpoints."""

import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.api.auth import get_current_user
from storytime.database import Job, JobStatus, JobStep, User, get_db
from storytime.infrastructure.spaces import SpacesClient
from storytime.models import (
    BookChaptersResponse,
    CreateJobRequest,
    JobAudioResponse,
    JobConfig,
    JobListResponse,
    JobResponse,
    JobResultData,
    JobStepResponse,
    JobType,
    MessageResponse,
)
from storytime.services.content_analyzer import ContentAnalyzer
from storytime.worker.tasks import process_job

from .utils import get_user_job

# JobProcessor is now simplified and always available

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.post("", response_model=JobResponse)
async def create_job(
    request: CreateJobRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Create a new job with automatic type detection."""
    logger.info(f"Creating job for user {current_user.id}: {request.title}")

    try:
        # Validate input (already handled by Pydantic model validator)
        # The CreateJobRequest model ensures exactly one input source is provided
        if not request.content and not request.file_key and not request.url:
            raise HTTPException(
                status_code=400, detail="Either content, file_key, or url must be provided"
            )

        # Auto-detect job type if not provided
        job_type = request.job_type
        if not job_type:
            logger.info("Job type not specified, analyzing content for auto-detection")
            content_analyzer = ContentAnalyzer()

            if content_analyzer.is_available():
                try:
                    # Get content for analysis
                    analysis_content = None
                    if request.content:
                        analysis_content = request.content
                    elif request.file_key:
                        # Load content from file storage for analysis
                        spaces_client = SpacesClient()
                        analysis_content = await spaces_client.download_text_file(request.file_key)
                    elif request.url:
                        # For URLs, we'll analyze after scraping during job processing
                        # For now, default to TEXT_TO_AUDIO and let the processor handle it
                        job_type = JobType.TEXT_TO_AUDIO
                        logger.info("URL provided - defaulting to TEXT_TO_AUDIO, will analyze during processing")

                    if analysis_content and not job_type:
                        detected_type = await content_analyzer.analyze_content(
                            analysis_content,
                            request.title
                        )
                        job_type = detected_type
                        logger.info(f"Auto-detected job type: {job_type.value}")

                except Exception as e:
                    logger.warning(f"Content analysis failed, defaulting to TEXT_TO_AUDIO: {e}")
                    job_type = JobType.TEXT_TO_AUDIO
            else:
                logger.info("Content analyzer not available, defaulting to TEXT_TO_AUDIO")
                job_type = JobType.TEXT_TO_AUDIO

        if not job_type:
            job_type = JobType.TEXT_TO_AUDIO

        # Create job record
        job = Job(
            id=str(uuid4()),
            user_id=current_user.id,
            title=request.title,
            description=request.description,
            status=JobStatus.PENDING,
            progress=0.0,
            config={
                "content": request.content,
                "url": str(request.url) if request.url else None,
                "voice_config": request.voice_config.model_dump() if request.voice_config else None,
                "job_type": job_type.value,
            },
            input_file_key=request.file_key,
        )

        db.add(job)
        await db.commit()
        await db.refresh(job)

        # Schedule job processing in Celery (if available)
        def _enqueue_job(job_id: str) -> None:
            try:
                process_job.delay(job_id)  # type: ignore[attr-defined]
                logger.info(f"Job {job_id} scheduled for processing")
            except Exception as e:
                logger.warning(f"Could not schedule job processing: {e}")

        background_tasks.add_task(_enqueue_job, job.id)

        # Return job response
        return await _get_job_response(job.id, db)

    except Exception as e:
        logger.error(f"Failed to create job: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create job: {e!s}") from e


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

        # Convert to response models (without full relationships for performance)
        job_responses = []
        for job in jobs:
            job_response = await _get_job_response(job.id, db, include_relationships=False)
            job_responses.append(job_response)

        total_pages = (total + page_size - 1) // page_size

        return JobListResponse(
            jobs=job_responses, total=total, page=page, page_size=page_size, total_pages=total_pages
        )

    except Exception as e:
        logger.error(f"Failed to list jobs: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {e!s}") from e


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> JobResponse:
    """Get detailed job information including steps."""
    logger.info(f"Getting job {job_id} for user {current_user.id}")

    try:
        # Verify job exists and belongs to user
        await get_user_job(job_id, current_user.id, db)
        return await _get_job_response(job_id, db)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job: {e!s}") from e


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
        job = await get_user_job(job_id, current_user.id, db)

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
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {e!s}") from e


@router.get("/{job_id}/steps", response_model=list[JobStepResponse])
async def get_job_steps(
    job_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[JobStepResponse]:
    """Get detailed step information for a job."""
    logger.info(f"Getting steps for job {job_id} for user {current_user.id}")

    try:
        # Verify job exists and belongs to user
        await get_user_job(job_id, current_user.id, db)

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
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to get job steps for {job_id}: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job steps: {e!s}") from e


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
        job = await get_user_job(job_id, current_user.id, db)

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
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to get audio for job {job_id}: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job audio: {e!s}") from e


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
        job = await get_user_job(job_id, current_user.id, db)

        # Check if this is a book processing job
        job_type = job.config.get("job_type") if job.config else None
        if job_type != JobType.BOOK_PROCESSING.value:
            raise HTTPException(
                status_code=400, detail="This endpoint is only for book processing jobs"
            )

        # Get aggregated chapter results using unified processor
        from storytime.services.job_processor import JobProcessor

        job_processor = JobProcessor(db, SpacesClient())
        results = await job_processor.aggregate_chapter_results(job_id)

        return BookChaptersResponse(**results)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Failed to get chapters for job {job_id}: {e!s}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get book chapters: {e!s}") from e


# Helper functions


async def _get_job_response(
    job_id: str, db: AsyncSession, include_relationships: bool = True
) -> JobResponse:
    """Get job with steps and relationships as response model."""
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

    # Get parent job if exists
    parent_job = None
    if include_relationships and job.parent_id:
        parent_result = await db.execute(select(Job).where(Job.id == job.parent_id))
        parent_db = parent_result.scalar_one_or_none()
        if parent_db:
            parent_job = await _get_job_response(parent_db.id, db, include_relationships=False)

    # Get child jobs
    children_jobs = []
    if include_relationships:
        children_result = await db.execute(
            select(Job).where(Job.parent_id == job_id).order_by(Job.created_at)
        )
        children_db = children_result.scalars().all()
        for child_db in children_db:
            child_job = await _get_job_response(child_db.id, db, include_relationships=False)
            children_jobs.append(child_job)

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

    # Convert config and result_data to typed models
    config = None
    if job.config:
        # Handle legacy jobs with empty voice_config dict
        config_data = job.config.copy()
        if config_data.get("voice_config") == {}:
            config_data["voice_config"] = None
        config = JobConfig(**config_data)

    result_data = None
    if job.result_data:
        result_data = JobResultData(**job.result_data)

    return JobResponse(
        id=job.id,
        user_id=job.user_id,
        parent_job_id=job.parent_id,
        title=job.title,
        description=job.description,
        status=job.status,
        progress=job.progress,
        error_message=job.error_message,
        config=config,
        result_data=result_data,
        input_file_key=job.input_file_key,
        output_file_key=job.output_file_key,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration=job.duration,
        steps=step_responses,
        children=children_jobs,
        parent=parent_job,
    )
