import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..database import User
from .auth import get_current_user

# Import workflow conditionally to avoid initialization issues
try:
    from ..workflows.chapter_parsing import workflow as chapter_workflow
    CHAPTER_WORKFLOW_AVAILABLE = True
except Exception as e:
    chapter_workflow = None
    CHAPTER_WORKFLOW_AVAILABLE = False
    print(f"Warning: Chapter workflow not available: {e}")

router = APIRouter(prefix="/api/v1/chapters", tags=["Chapters"])

# In-memory storage for parsed chapters (MVP)
CHAPTERS: dict[str, dict] = {}

class ParseRequest(BaseModel):
    text: str
    chapter_number: int | None = None

class ParseResponse(BaseModel):
    chapter_id: str
    segments: list

class CharacterResponse(BaseModel):
    chapter_id: str
    characters: list

@router.post("/parse", response_model=ParseResponse)
async def parse_chapter(
    request: ParseRequest,
    current_user: User = Depends(get_current_user),
):
    if not CHAPTER_WORKFLOW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Chapter parsing workflow is not available due to system configuration issues"
        )

    await chapter_workflow.store.set_state({
        "chapter_text": request.text,
        "chapter_number": request.chapter_number or 1,
    })
    await chapter_workflow.execute()
    state = await chapter_workflow.store.get_state()
    if getattr(state, "error", None):
        raise HTTPException(status_code=500, detail=state.error)
    chapter = state.chapter
    chapter_id = str(uuid.uuid4())
    CHAPTERS[chapter_id] = {"chapter": chapter, "characters": None}
    return {"chapter_id": chapter_id, "segments": chapter.segments if chapter else []}

@router.post("/parse-with-characters", response_model=CharacterResponse)
async def parse_with_characters(
    request: ParseRequest,
    current_user: User = Depends(get_current_user),
):
    if not CHAPTER_WORKFLOW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Chapter parsing workflow is not available due to system configuration issues"
        )

    await chapter_workflow.store.set_state({
        "chapter_text": request.text,
        "chapter_number": request.chapter_number or 1,
    })
    await chapter_workflow.execute()
    state = await chapter_workflow.store.get_state()
    if getattr(state, "error", None):
        raise HTTPException(status_code=500, detail=state.error)
    chapter = state.chapter
    catalogue = state.character_catalogue
    characters = [c.model_dump() for c in catalogue.characters.values()] if catalogue else []
    chapter_id = str(uuid.uuid4())
    CHAPTERS[chapter_id] = {"chapter": chapter, "characters": characters}
    return {"chapter_id": chapter_id, "characters": characters}

@router.post("/parse-file", response_model=ParseResponse)
async def parse_chapter_file(
    file: UploadFile = File(...),
    chapter_number: int | None = Form(None),
    current_user: User = Depends(get_current_user),
):
    if not CHAPTER_WORKFLOW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Chapter parsing workflow is not available due to system configuration issues"
        )

    text = (await file.read()).decode()
    await chapter_workflow.store.set_state({
        "chapter_text": text,
        "chapter_number": chapter_number or 1,
    })
    await chapter_workflow.execute()
    state = await chapter_workflow.store.get_state()
    if getattr(state, "error", None):
        raise HTTPException(status_code=500, detail=state.error)
    chapter = state.chapter
    chapter_id = str(uuid.uuid4())
    CHAPTERS[chapter_id] = {"chapter": chapter, "characters": None}
    return {"chapter_id": chapter_id, "segments": chapter.segments if chapter else []}

@router.get("/{chapter_id}")
async def get_chapter(
    chapter_id: str,
    current_user: User = Depends(get_current_user),
):
    data = CHAPTERS.get(chapter_id)
    if not data:
        raise HTTPException(status_code=404, detail="Chapter not found")
    chapter = data["chapter"]
    return {"chapter_id": chapter_id, "segments": chapter.segments if chapter else []}

@router.get("/{chapter_id}/characters")
async def get_characters(
    chapter_id: str,
    current_user: User = Depends(get_current_user),
):
    data = CHAPTERS.get(chapter_id)
    if not data:
        raise HTTPException(status_code=404, detail="Chapter not found")
    characters = data["characters"]
    if characters is None:
        raise HTTPException(status_code=404, detail="No character analysis for this chapter")
    return {"chapter_id": chapter_id, "characters": characters}
