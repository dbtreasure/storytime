from fastapi import APIRouter, BackgroundTasks, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Dict, Optional, List, Any
import uuid
import time
from pathlib import Path
from fastapi.responses import FileResponse
import os
import asyncio
import logging
import tempfile

from storytime.services.tts_generator import TTSGenerator
from storytime.models import TextSegment, SpeakerType, Chapter, CharacterCatalogue
from storytime.infrastructure.tts import OpenAIProvider, ElevenLabsProvider
from storytime.workflows.audio_generation import build_audio_workflow
from storytime.workflows.chapter_parsing import workflow as chapter_workflow
from storytime.worker.celery_app import celery_app
from storytime.database import AsyncSessionLocal, BookStatus
from storytime.database import Book as DBBook
from sqlalchemy import text
from storytime.infrastructure.spaces import upload_file

router = APIRouter(prefix="/api/v1/tts", tags=["TTS"])

class GenerateRequest(BaseModel):
    chapter_text: str
    chapter_number: Optional[int] = 1
    title: Optional[str] = None
    provider: Optional[str] = "openai"
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
    provider_name = (request.provider or "openai").lower()
    if provider_name not in ("openai", "elevenlabs", "eleven"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider_name}")
    job_id = str(uuid.uuid4())
    text_key = f"uploads/{job_id}.txt"

    # Save chapter_text to a temp file and upload to Spaces
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as tmp:
            tmp.write(request.chapter_text)
            tmp_path = tmp.name
        logging.info(f"[Spaces] Uploading book text for job_id={job_id} to Spaces as {text_key}")
        upload_success = upload_file(tmp_path, text_key, content_type="text/plain")
        if not upload_success:
            logging.error(f"[Spaces] Upload failed for job_id={job_id}")
            # Optionally: set error_msg in DB here
    except Exception as e:
        logging.error(f"[Spaces] Exception during upload for job_id={job_id}: {e}")
        # Optionally: set error_msg in DB here

    # Persist Book row with comprehensive logging
    logging.info(f"Starting database transaction for book_id={job_id}")
    try:
        async with AsyncSessionLocal() as session:
            logging.info(f"Session created, creating DBBook object for job_id={job_id}")
            new_book = DBBook(
                id=job_id,
                title=request.title or f"Book {job_id[:8]}",
                status=BookStatus.UPLOADED,
                progress_pct=0,
                error_msg=None,
                text_key=text_key,
            )
            logging.info(f"DBBook object created: {new_book.id}, {new_book.title}, {new_book.status}, {text_key}")
            session.add(new_book)
            logging.info(f"Book added to session, attempting commit for job_id={job_id}")
            await session.commit()
            logging.info(f"Session committed successfully for job_id={job_id}")
            await session.refresh(new_book)
            logging.info(f"Book verified in database: {new_book.id}, status={new_book.status}")
    except Exception as e:
        logging.error(f"Database error for job_id={job_id}: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    cost = estimate_cost_by_characters(request.chapter_text, provider_name)

    # Enqueue Celery task (only in Docker/prod)
    if os.getenv("ENV") == "docker":
        celery_app.send_task("storytime.worker.tasks.generate_tts", args=[job_id])
        logging.info(f"Enqueued Celery TTS task for book_id={job_id}")
    else:
        background_tasks.add_task(lambda: None)  # No-op for now
        logging.info(f"(Dev) Would enqueue Celery TTS task for book_id={job_id}")

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