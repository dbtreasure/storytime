from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Optional, List, Any
import uuid
import time
from pathlib import Path
from fastapi.responses import FileResponse
import os
import asyncio

from storytime.services.tts_generator import TTSGenerator
from storytime.models import TextSegment, SpeakerType, Chapter, CharacterCatalogue
from storytime.infrastructure.tts import OpenAIProvider, ElevenLabsProvider
from storytime.workflows.audio_generation import build_audio_workflow
from storytime.workflows.chapter_parsing import workflow as chapter_workflow

router = APIRouter(prefix="/api/v1/tts", tags=["TTS"])

# In-memory job store (MVP)
class JobStatus(str):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"

class TTSJob(BaseModel):
    job_id: str
    status: str
    result: Optional[dict] = None  # Dict with audio files, playlist, etc.
    error: Optional[str] = None

JOBS: Dict[str, TTSJob] = {}

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

def run_tts_job(job_id: str, request: GenerateRequest):
    job = JOBS.get(job_id)
    if not job or job.status == JobStatus.CANCELED:
        return
    try:
        job.status = JobStatus.RUNNING
        # Run the Junjo-native chapter parsing pipeline synchronously
        async def parse_chapter():
            await chapter_workflow.store.set_state({
                "chapter_text": request.chapter_text,
                "chapter_number": request.chapter_number or 1,
                "title": request.title,
            })
            await chapter_workflow.execute()
            state = await chapter_workflow.store.get_state()
            return state.chapter, state.character_catalogue
        chapter, character_catalogue = asyncio.run(parse_chapter())
        if not chapter:
            job.status = JobStatus.FAILED
            job.error = "Failed to parse chapter with Junjo pipeline."
            return
        # Select provider class
        provider = None
        if request.provider:
            if request.provider.lower() in ("elevenlabs", "eleven"):
                provider = ElevenLabsProvider()
            else:
                provider = OpenAIProvider()
        # --- Parallel audio generation via Junjo ---
        tts = TTSGenerator(provider=provider, character_catalogue=character_catalogue)

        async def run_audio_workflow() -> dict[str, Any]:
            # Build & execute workflow with concurrency from env
            max_con = int(os.getenv("TTS_MAX_CONCURRENCY", "8"))
            wf = build_audio_workflow(chapter, tts, max_concurrency=max_con)
            await wf.execute()
            st = await wf.store.get_state()
            return {
                "audio_files": st.audio_paths or {},
                "playlist": st.playlist_path,
                "stitched": st.stitched_path,
            }

        audio_state = asyncio.run(run_audio_workflow())

        # Compose result dict
        result = {
            "audio_files": audio_state["audio_files"],
            "playlist": audio_state["playlist"],
            "stitched_path": audio_state["stitched"],
            "character_catalogue": character_catalogue.model_dump() if character_catalogue else {},
            "chapter_segments": [s.model_dump() for s in chapter.segments],
            "chapter_number": chapter.chapter_number,
        }
        job.result = result
        job.status = JobStatus.DONE
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)

@router.post("/generate")
def generate_tts(request: GenerateRequest, background_tasks: BackgroundTasks):
    # Validate provider
    provider_name = (request.provider or "openai").lower()
    if provider_name not in ("openai", "elevenlabs", "eleven"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider_name}")
    job_id = str(uuid.uuid4())
    job = TTSJob(job_id=job_id, status=JobStatus.PENDING)
    JOBS[job_id] = job
    cost = estimate_cost_by_characters(request.chapter_text, provider_name)
    background_tasks.add_task(run_tts_job, job_id, request)
    return {"job_id": job_id, "status": job.status, "estimated_cost": cost}

@router.get("/jobs/{job_id}")
def get_job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/jobs/{job_id}/download")
def download_job_audio(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.DONE or not job.result:
        raise HTTPException(status_code=400, detail="Audio not ready")
    # Try to serve the stitched/complete chapter audio file if it exists
    audio_files = job.result.get("audio_files")
    if audio_files:
        # Determine chapter directory (same as first segment)
        first_audio_path = Path(list(audio_files.values())[0])
        chapter_number = job.result.get("chapter_number", 1)
        complete_path = first_audio_path.parent / f"chapter_{chapter_number:02d}_complete.mp3"

        if complete_path.exists():
            return FileResponse(str(complete_path), media_type="audio/mpeg", filename=complete_path.name)

        # Fallback: return the first segment audio file
        if first_audio_path.exists():
            return FileResponse(str(first_audio_path), media_type="audio/mpeg", filename=first_audio_path.name)
    raise HTTPException(status_code=404, detail="Audio file not found")

@router.delete("/jobs/{job_id}")
def cancel_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = JobStatus.CANCELED
    return {"job_id": job_id, "status": job.status} 