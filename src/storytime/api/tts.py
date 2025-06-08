import logging
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from storytime.database import AsyncSessionLocal, BookStatus
from storytime.database import Book as DBBook

router = APIRouter(prefix="/api/v1/tts", tags=["TTS"])

class GenerateRequest(BaseModel):
    chapter_text: str
    chapter_number: int | None = 1
    title: str | None = None
    provider: str | None = "openai"
    # Add more fields as needed

def estimate_cost_by_characters(text: str, provider: str) -> float:
    char_count = len(text)
    if provider.lower() in ("elevenlabs", "eleven"):
        rate = 0.0003  # Example: $0.0003 per character
    else:
        rate = 0.000015  # Example: $0.000015 per character
    return round((char_count * rate), 4)

@router.post("/generate")
async def generate_tts(request: GenerateRequest, background_tasks: BackgroundTasks):
    """Legacy TTS endpoint - routes through new job system for backward compatibility."""
    provider_name = (request.provider or "openai").lower()
    if provider_name not in ("openai", "elevenlabs", "eleven"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider_name}")

    # Create a job using the new unified system
    from storytime.database import Job, JobStatus
    from storytime.models import JobType, SourceType
    from storytime.worker.tasks import process_job

    job_id = str(uuid.uuid4())

    try:
        async with AsyncSessionLocal() as session:
            # Create job record
            job = Job(
                id=job_id,
                user_id="anonymous",  # For backward compatibility - no auth required
                job_type=JobType.SINGLE_VOICE,
                source_type=SourceType.TEXT,
                title=request.title or f"TTS Job {job_id[:8]}",
                description="Legacy TTS job via /generate endpoint",
                status=JobStatus.PENDING,
                progress=0.0,
                config={
                    "content": request.chapter_text,
                    "voice_config": {
                        "provider": provider_name
                    }
                }
            )

            session.add(job)
            await session.commit()
            await session.refresh(job)

            # Also create legacy book record for compatibility
            new_book = DBBook(
                id=job_id,
                title=request.title or f"Book {job_id[:8]}",
                status=BookStatus.UPLOADED,
                progress_pct=0,
                error_msg=None,
                text_key=f"jobs/{job_id}/input.txt",  # Will be created by job processor
            )
            session.add(new_book)
            await session.commit()

    except Exception as e:
        logging.error(f"Database error for job_id={job_id}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    cost = estimate_cost_by_characters(request.chapter_text, provider_name)

    # Enqueue unified job task
    if os.getenv("ENV") == "docker":
        process_job.delay(job_id)
        logging.info(f"Enqueued unified job task for job_id={job_id}")
    else:
        # In development, still use Celery if available
        try:
            process_job.delay(job_id)
            logging.info(f"(Dev) Enqueued unified job task for job_id={job_id}")
        except Exception:
            logging.info(f"(Dev) Celery not available, job {job_id} created but not processed")

    return {"job_id": job_id, "status": "UPLOADED", "estimated_cost": cost}


@router.get("/debug/db-test")
async def test_database_connection():
    """Debug endpoint to test database connectivity and manual insert."""
    test_id = str(uuid.uuid4())

    try:
        async with AsyncSessionLocal() as session:
            # Test 1: Basic connectivity
            result = await session.execute(text("SELECT 1 as test"))
            test_result = result.scalar()
            logging.info(f"Database connectivity test: {test_result}")

            # Test 2: Check if book table exists
            table_check = await session.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='book')")
            )
            table_exists = table_check.scalar()
            logging.info(f"Book table exists: {table_exists}")

            # Test 3: Manual insert via raw SQL
            await session.execute(
                text("INSERT INTO book (id, title, status, progress_pct) VALUES (:id, :title, :status, :progress)"),
                {"id": test_id, "title": "Test Book SQL", "status": "UPLOADED", "progress": 0}
            )
            await session.commit()
            logging.info(f"Manual SQL insert successful: {test_id}")

            # Test 4: Verify the insert
            verify_result = await session.execute(
                text("SELECT id, title, status FROM book WHERE id = :id"),
                {"id": test_id}
            )
            row = verify_result.fetchone()
            logging.info(f"Verification result: {row}")

            # Test 5: Try SQLAlchemy ORM insert
            orm_id = str(uuid.uuid4())
            orm_book = DBBook(
                id=orm_id,
                title="Test Book ORM",
                status=BookStatus.UPLOADED,
                progress_pct=0
            )
            session.add(orm_book)
            await session.commit()
            await session.refresh(orm_book)
            logging.info(f"ORM insert successful: {orm_book.id}")

            return {
                "connectivity": test_result == 1,
                "table_exists": table_exists,
                "manual_insert_id": test_id,
                "orm_insert_id": orm_id,
                "status": "success"
            }

    except Exception as e:
        logging.error(f"Database test failed: {type(e).__name__}: {e}")
        return {"error": str(e), "status": "failed"}
