"""Knowledge API endpoints for content search and Q&A using OpenAI Responses API."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from openai import OpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.api.auth import get_current_user
from storytime.api.settings import get_settings
from storytime.database import User, get_db
from storytime.models import (
    AskJobQuestionRequest,
    SearchJobRequest,
    SearchLibraryRequest,
)
from storytime.services.responses_api_service import ResponsesAPIVectorStoreService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


async def get_responses_api_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ResponsesAPIVectorStoreService:
    """Dependency to get ResponsesAPIVectorStoreService."""
    settings = get_settings()

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OpenAI API key not configured",
        )

    openai_client = OpenAI(api_key=settings.openai_api_key)
    return ResponsesAPIVectorStoreService(openai_client, db)


@router.post("/jobs/{job_id}/search")
async def search_job_content(
    job_id: str,
    request: SearchJobRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    service: Annotated[ResponsesAPIVectorStoreService, Depends(get_responses_api_service)] = None,
) -> dict:
    """Search within specific audiobook content."""
    try:
        result = await service.search_job_content(
            user_id=current_user.id,
            job_id=job_id,
            query=request.query,
            max_results=request.max_results,
        )

        if not result["success"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching job content: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to search job content"
        ) from e


@router.post("/jobs/{job_id}/ask")
async def ask_question_about_job(
    job_id: str,
    request: AskJobQuestionRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    service: Annotated[ResponsesAPIVectorStoreService, Depends(get_responses_api_service)] = None,
) -> dict:
    """Ask a question about specific audiobook content."""
    try:
        result = await service.ask_question_about_job(
            user_id=current_user.id, job_id=job_id, question=request.question
        )

        if not result["success"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error asking question about job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ask question about job",
        ) from e


@router.post("/library/search")
async def search_library(
    request: SearchLibraryRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    service: Annotated[ResponsesAPIVectorStoreService, Depends(get_responses_api_service)] = None,
) -> dict:
    """Search across user's entire audiobook library."""
    try:
        result = await service.search_library(
            user_id=current_user.id, query=request.query, max_results=request.max_results
        )

        if not result["success"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching library: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to search library"
        ) from e
