from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, Form
from pydantic import BaseModel
from typing import List, Dict, Optional
import uuid

from .auth import get_api_key
from ..services.chapter_parser import ChapterParser
from ..services.character_analyzer import CharacterAnalyzer

router = APIRouter(prefix="/api/v1/chapters", tags=["Chapters"])

# In-memory storage for parsed chapters (MVP)
CHAPTERS: Dict[str, dict] = {}

class ParseRequest(BaseModel):
    text: str
    chapter_number: Optional[int] = None

class ParseResponse(BaseModel):
    chapter_id: str
    segments: list

class CharacterResponse(BaseModel):
    chapter_id: str
    characters: list

@router.post("/parse", response_model=ParseResponse)
async def parse_chapter(
    request: ParseRequest,
    api_key: str = Depends(get_api_key),
):
    parser = ChapterParser()
    chapter = parser.parse_chapter_text(request.text, request.chapter_number or 1)
    chapter_id = str(uuid.uuid4())
    CHAPTERS[chapter_id] = {"chapter": chapter, "characters": None}
    return {"chapter_id": chapter_id, "segments": chapter.segments}

@router.post("/parse-with-characters", response_model=CharacterResponse)
async def parse_with_characters(
    request: ParseRequest,
    api_key: str = Depends(get_api_key),
):
    parser = ChapterParser()
    chapter, character_catalogue = parser.parse_chapter_with_characters(request.text, request.chapter_number or 1)
    characters = [c.model_dump() for c in character_catalogue.characters.values()]
    chapter_id = str(uuid.uuid4())
    CHAPTERS[chapter_id] = {"chapter": chapter, "characters": characters}
    return {"chapter_id": chapter_id, "characters": characters}

@router.post("/parse-file", response_model=ParseResponse)
async def parse_chapter_file(
    file: UploadFile = File(...),
    chapter_number: Optional[int] = Form(None),
    api_key: str = Depends(get_api_key),
):
    text = (await file.read()).decode()
    parser = ChapterParser()
    chapter = parser.parse_chapter_text(text, chapter_number or 1)
    chapter_id = str(uuid.uuid4())
    CHAPTERS[chapter_id] = {"chapter": chapter, "characters": None}
    return {"chapter_id": chapter_id, "segments": chapter.segments}

@router.get("/{chapter_id}")
async def get_chapter(
    chapter_id: str,
    api_key: str = Depends(get_api_key),
):
    data = CHAPTERS.get(chapter_id)
    if not data:
        raise HTTPException(status_code=404, detail="Chapter not found")
    chapter = data["chapter"]
    return {"chapter_id": chapter_id, "segments": chapter.segments}

@router.get("/{chapter_id}/characters")
async def get_characters(
    chapter_id: str,
    api_key: str = Depends(get_api_key),
):
    data = CHAPTERS.get(chapter_id)
    if not data:
        raise HTTPException(status_code=404, detail="Chapter not found")
    characters = data["characters"]
    if characters is None:
        raise HTTPException(status_code=404, detail="No character analysis for this chapter")
    return {"chapter_id": chapter_id, "characters": characters} 