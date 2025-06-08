"""Unified job management API endpoints."""

import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_
from sqlalchemy.orm import selectinload

from storytime.api.auth import get_current_user
from storytime.database import get_db, Job, JobStep, User, JobStatus, JobType, SourceType
from storytime.models import (
    CreateJobRequest, JobResponse, JobListResponse, JobFilters,
    ContentAnalysisResult, JobStepResponse
)
from storytime.services.content_analyzer import ContentAnalyzer
from storytime.infrastructure.spaces import SpacesClient

# Import JobProcessor conditionally to avoid workflow initialization issues
try:
    from storytime.services.job_processor import JobProcessor
    JOB_PROCESSOR_AVAILABLE = True
except Exception as e:
    print(f"Warning: JobProcessor not available due to workflow dependencies: {e}")
    JobProcessor = None
    JOB_PROCESSOR_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.post("", response_model=JobResponse)
async def create_job(
    request: CreateJobRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> JobResponse:
    """Create a new job with automatic type detection."""
    logger.info(f"Creating job for user {current_user.id}: {request.title}")
    
    try:
        # Validate input
        if not request.content and not request.file_key:
            raise HTTPException(status_code=400, detail="Either content or file_key must be provided")
        
        # Auto-detect job type if not specified
        job_type = request.job_type
        if not job_type:
            content_analyzer = ContentAnalyzer()
            
            # Get content for analysis
            if request.content:
                content = request.content
            elif request.file_key:
                spaces_client = SpacesClient()
                content = await spaces_client.download_text_file(request.file_key)
            else:
                raise HTTPException(status_code=400, detail="No content available for analysis")
            
            # Analyze content and suggest job type
            analysis = await content_analyzer.analyze_content(content, request.source_type)
            job_type = analysis.suggested_job_type
            
            logger.info(f"Auto-detected job type: {job_type} (confidence: {analysis.confidence})")
        
        # Create job record
        job = Job(
            id=str(uuid4()),
            user_id=current_user.id,
            book_id=request.book_id,
            job_type=job_type,
            source_type=request.source_type,
            title=request.title,
            description=request.description,
            status=JobStatus.PENDING,
            progress=0.0,
            config={
                "content": request.content,
                "voice_config": request.voice_config.dict() if request.voice_config else {},
                "processing_config": request.processing_config.dict() if request.processing_config else {}
            },
            input_file_key=request.file_key
        )
        
        db.add(job)
        await db.commit()
        await db.refresh(job)
        
        # Schedule job processing in Celery (if available)
        try:
            from storytime.worker.tasks import process_job
            process_job.delay(job.id)
            logger.info(f"Job {job.id} scheduled for processing")
        except Exception as e:
            logger.warning(f"Could not schedule job processing: {e}")
            # Job is created but not scheduled - can be processed later
        
        # Return job response
        return await _get_job_response(job.id, db)
        
    except Exception as e:
        logger.error(f"Failed to create job: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)}")


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[JobStatus] = Query(None, description="Filter by job status"),
    job_type: Optional[JobType] = Query(None, description="Filter by job type"),
    source_type: Optional[SourceType] = Query(None, description="Filter by source type"),
    book_id: Optional[str] = Query(None, description="Filter by book ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> JobListResponse:
    """List jobs for the current user with filtering and pagination."""
    logger.info(f"Listing jobs for user {current_user.id}")
    
    try:
        # Build query with filters
        query = select(Job).where(Job.user_id == current_user.id)
        
        if status:
            query = query.where(Job.status == status)
        if job_type:
            query = query.where(Job.job_type == job_type)
        if source_type:
            query = query.where(Job.source_type == source_type)
        if book_id:
            query = query.where(Job.book_id == book_id)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
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
            jobs=job_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Failed to list jobs: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list jobs: {str(e)}")


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
        logger.error(f"Failed to get job {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job: {str(e)}")


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict[str, str]:
    """Cancel a job."""
    logger.info(f"Cancelling job {job_id} for user {current_user.id}")
    
    try:
        # Verify job exists and belongs to user
        job = await _get_user_job(job_id, current_user.id, db)
        
        # Only allow cancellation of pending or processing jobs
        if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot cancel job with status {job.status}"
            )
        
        # Update job status to cancelled
        await db.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.CANCELLED,
                updated_at=datetime.utcnow(),
                completed_at=datetime.utcnow()
            )
        )
        await db.commit()
        
        return {"message": "Job cancelled successfully"}
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to cancel job: {str(e)}")


@router.get("/{job_id}/steps", response_model=list[JobStepResponse])
async def get_job_steps(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
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
                duration=step.duration
            )
            for step in steps
        ]
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get job steps for {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job steps: {str(e)}")


@router.get("/{job_id}/audio")
async def get_job_audio(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Download or stream the audio result from a completed job."""
    logger.info(f"Getting audio for job {job_id} for user {current_user.id}")
    
    try:
        # Verify job exists and belongs to user
        job = await _get_user_job(job_id, current_user.id, db)
        
        # Check if job is completed and has audio output
        if job.status != JobStatus.COMPLETED:
            raise HTTPException(
                status_code=400, 
                detail=f"Job is not completed (status: {job.status})"
            )
        
        if not job.output_file_key:
            raise HTTPException(status_code=404, detail="No audio output available for this job")
        
        # Get presigned URL for audio download
        spaces_client = SpacesClient()
        download_url = await spaces_client.get_presigned_download_url(job.output_file_key)
        
        return {"download_url": download_url, "file_key": job.output_file_key}
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get audio for job {job_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get job audio: {str(e)}")


@router.post("/analyze-content", response_model=ContentAnalysisResult)
async def analyze_content(
    content: str,
    source_type: SourceType = SourceType.TEXT,
    current_user: User = Depends(get_current_user)
) -> ContentAnalysisResult:
    """Analyze content and suggest appropriate job type without creating a job."""
    logger.info(f"Analyzing content for user {current_user.id}")
    
    try:
        content_analyzer = ContentAnalyzer()
        result = await content_analyzer.analyze_content(content, source_type)
        return result
        
    except Exception as e:
        logger.error(f"Failed to analyze content: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze content: {str(e)}")


# Helper functions

async def _get_user_job(job_id: str, user_id: str, db: AsyncSession) -> Job:
    """Get job and verify it belongs to the user."""
    result = await db.execute(
        select(Job).where(and_(Job.id == job_id, Job.user_id == user_id))
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise ValueError(f"Job {job_id} not found or access denied")
    
    return job


async def _get_job_response(job_id: str, db: AsyncSession) -> JobResponse:
    """Get job with steps as response model."""
    # Get job
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
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
            duration=step.duration
        )
        for step in steps
    ]
    
    return JobResponse(
        id=job.id,
        user_id=job.user_id,
        book_id=job.book_id,
        title=job.title,
        description=job.description,
        job_type=job.job_type,
        source_type=job.source_type,
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
        steps=step_responses
    )


