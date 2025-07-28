"""Opening lecture MCP tool for fetching pre-generated lecture content."""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.database import Job

logger = logging.getLogger(__name__)


async def opening_lecture(db_session: AsyncSession, user_id: str, job_id: str) -> dict[str, Any]:
    """
    Fetch pre-generated opening lecture content for a specific job.

    This tool retrieves the opening lecture content that was generated during
    job processing and stored in the job config. Used by the voice assistant
    to deliver the introductory lecture before starting Socratic dialogue.

    Args:
        db_session: Database session for querying
        user_id: ID of the authenticated user
        job_id: ID of the job to get opening lecture for

    Returns:
        Dictionary containing opening lecture content or error message
    """
    try:
        logger.info(f"Fetching opening lecture for job {job_id} by user {user_id}")

        # Query for the job with user verification
        stmt = select(Job).where(Job.id == job_id, Job.user_id == user_id)
        result = await db_session.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            logger.warning(f"Job {job_id} not found or not accessible by user {user_id}")
            return {
                "success": False,
                "error": "Job not found or access denied",
                "message": "I couldn't find that audiobook in your library. Please check the job ID and try again.",
            }

        # Check if job has opening lecture content
        if not job.config or not job.config.get("opening_lecture"):
            logger.info(f"No opening lecture content found for job {job_id}")
            return {
                "success": False,
                "error": "No opening lecture available",
                "message": f"I don't have an opening lecture prepared for '{job.title}'. This might be because the content is still processing or the lecture generation failed.",
            }

        opening_lecture_data = job.config["opening_lecture"]

        logger.info(
            f"Retrieved opening lecture for '{job.title}' - {opening_lecture_data.get('lecture_duration_minutes', 'unknown')} minutes"
        )

        return {
            "success": True,
            "job_id": job.id,
            "job_title": job.title,
            "opening_lecture": {
                "introduction": opening_lecture_data.get("introduction", ""),
                "key_concepts_overview": opening_lecture_data.get("key_concepts_overview", ""),
                "learning_objectives": opening_lecture_data.get("learning_objectives", ""),
                "engagement_questions": opening_lecture_data.get("engagement_questions", []),
                "lecture_duration_minutes": opening_lecture_data.get("lecture_duration_minutes", 3),
                "extension_topics": opening_lecture_data.get("extension_topics", []),
                "generated_at": opening_lecture_data.get("generated_at"),
            },
            "message": f"Opening lecture content ready for '{job.title}'. Duration: {opening_lecture_data.get('lecture_duration_minutes', 3)} minutes.",
        }

    except Exception as e:
        logger.error(f"Error fetching opening lecture for job {job_id}: {e}", exc_info=True)
        return {
            "success": False,
            "error": "Internal error",
            "message": "I encountered an error while retrieving the opening lecture content. Please try again later.",
        }
