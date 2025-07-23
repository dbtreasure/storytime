"""Progress-aware search service for spoiler-free content retrieval."""

import logging
from typing import Any

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.database import Job, ProgressRecord
from storytime.services.responses_api_service import ResponsesAPIVectorStoreService

logger = logging.getLogger(__name__)


class ProgressAwareSearchService:
    """Service for progress-aware content search that prevents spoilers."""
    
    def __init__(self, openai_client: OpenAI, db_session: AsyncSession):
        self.openai_client = openai_client
        self.db_session = db_session
        self.base_service = ResponsesAPIVectorStoreService(openai_client, db_session)
    
    async def search_with_progress_filter(
        self,
        user_id: str,
        job_id: str,
        query: str,
        max_results: int = 5
    ) -> dict[str, Any]:
        """Search job content with progress-based filtering."""
        try:
            # Get user's progress
            progress_result = await self.db_session.execute(
                select(ProgressRecord).where(
                    ProgressRecord.user_id == user_id,
                    ProgressRecord.job_id == job_id
                )
            )
            progress = progress_result.scalar_one_or_none()
            
            # Get job info
            job_result = await self.db_session.execute(
                select(Job).where(Job.id == job_id, Job.user_id == user_id)
            )
            job = job_result.scalar_one_or_none()
            
            if not job:
                return {"success": False, "error": "Job not found", "results": []}
            
            # Calculate content boundary
            progress_percentage = progress.percentage_complete if progress else 0.0
            current_chapter = progress.current_chapter if progress else None
            
            # For now, we'll add progress context to the query
            # In a full implementation, we'd filter chunks by position
            filtered_query = self._build_progress_aware_query(
                query, 
                progress_percentage, 
                current_chapter,
                job.title
            )
            
            # Use base service with filtered query
            result = await self.base_service.search_job_content(
                user_id, job_id, filtered_query, max_results
            )
            
            # Add progress metadata to results
            if result.get("success"):
                result["progress_context"] = {
                    "percentage_complete": progress_percentage,
                    "current_chapter": current_chapter,
                    "filtered": True
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Progress-aware search failed: {e}")
            return {"success": False, "error": str(e), "results": []}
    
    async def ask_question_with_progress_filter(
        self,
        user_id: str,
        job_id: str,
        question: str
    ) -> dict[str, Any]:
        """Ask question about job content with progress filtering."""
        try:
            # Get user's progress
            progress_result = await self.db_session.execute(
                select(ProgressRecord).where(
                    ProgressRecord.user_id == user_id,
                    ProgressRecord.job_id == job_id
                )
            )
            progress = progress_result.scalar_one_or_none()
            
            progress_percentage = progress.percentage_complete if progress else 0.0
            current_chapter = progress.current_chapter if progress else None
            
            # Create progress-aware prompt
            progress_context = f"""
IMPORTANT: The user is at {progress_percentage * 100:.1f}% through the content.
Current chapter: {current_chapter or "Beginning"}

When answering, you must:
1. ONLY use information from the first {progress_percentage * 100:.1f}% of the content
2. Do NOT reveal any plot points, character developments, or events after their current position
3. If the answer requires information from later in the content, say "This information hasn't been revealed yet at your current reading position."
4. Focus on what has been established up to their current point in the story

"""
            
            # Prepend progress context to question
            filtered_question = progress_context + "\nUSER QUESTION: " + question
            
            # Use base service with filtered question
            result = await self.base_service.ask_question_about_job(
                user_id, job_id, filtered_question
            )
            
            # Add progress metadata
            if result.get("success"):
                result["progress_filtered"] = True
                result["user_progress"] = {
                    "percentage": progress_percentage,
                    "chapter": current_chapter
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Progress-aware Q&A failed: {e}")
            return {"success": False, "error": str(e), "answer": ""}
    
    def _build_progress_aware_query(
        self, 
        query: str, 
        progress_percentage: float,
        current_chapter: str | None,
        title: str | None
    ) -> str:
        """Build a query that includes progress context."""
        context = f"In '{title or 'this content'}', "
        
        if current_chapter:
            context += f"up to chapter '{current_chapter}' ({progress_percentage * 100:.1f}% complete), "
        else:
            context += f"in the first {progress_percentage * 100:.1f}% of the content, "
        
        return context + query
    
    async def get_content_chunks_with_positions(
        self,
        job_id: str,
        user_id: str
    ) -> list[dict[str, Any]]:
        """
        Get content chunks with position metadata.
        
        This is a placeholder for future implementation where we'd:
        1. Store chunks with position metadata during job processing
        2. Retrieve chunks with their positions from vector store
        3. Filter chunks based on user's current progress
        """
        # TODO: Implement chunk position tracking in job processor
        # For now, return empty list
        logger.warning(
            "Chunk position tracking not yet implemented. "
            "Using instruction-based filtering as fallback."
        )
        return []