"""X-ray lookup MCP tool for contextual content queries (Kindle X-ray style)."""

import logging
from typing import Any

from openai import OpenAI
from sqlalchemy import select

from storytime.api.settings import get_settings
from storytime.database import Job, PlaybackProgress
from storytime.mcp.auth import MCPAuthContext
from storytime.services.progress_aware_search import ProgressAwareSearchService

logger = logging.getLogger(__name__)


async def xray_lookup(job_id: str, query: str, context: MCPAuthContext = None) -> dict[str, Any]:
    """Provide contextual content lookup (Kindle X-ray style).

    Args:
        job_id: The audiobook job ID to search
        query: The contextual query (e.g., "Who is Elizabeth?", "What is happening?")
        context: Authentication context with user and database session

    Returns:
        Dict containing contextual answer with success status and information
    """
    try:
        if not context:
            return {"success": False, "error": "Authentication context required", "answer": ""}

        # Get job and verify ownership
        result = await context.db_session.execute(
            select(Job).where(Job.id == job_id, Job.user_id == context.user.id)
        )
        job = result.scalar_one_or_none()

        if not job:
            return {"success": False, "error": "Job not found or access denied", "answer": ""}

        # Get tutoring analysis for context (if available)
        tutoring_data = job.config.get("tutoring_analysis") if job.config else None

        # Get user's reading progress for spoiler prevention
        progress_result = await context.db_session.execute(
            select(PlaybackProgress).where(
                PlaybackProgress.user_id == context.user.id, PlaybackProgress.job_id == job_id
            )
        )
        progress = progress_result.scalar_one_or_none()

        # Calculate progress context
        current_chapter = progress.current_chapter if progress else None
        progress_percentage = progress.percentage_complete if progress else 0.0

        # Create OpenAI client and progress-aware service for content access
        settings = get_settings()
        if not settings.openai_api_key:
            return {"success": False, "error": "OpenAI API key not configured", "answer": ""}

        openai_client = OpenAI(api_key=settings.openai_api_key)
        progress_service = ProgressAwareSearchService(openai_client, context.db_session)

        # Use progress-aware service to answer question with automatic filtering
        result = await progress_service.ask_question_with_progress_filter(
            user_id=context.user.id, job_id=job_id, question=query
        )

        if result["success"]:
            logger.info(
                f"MCP xray_lookup: user={context.user.id}, job={job_id}, query='{query[:50]}...'"
            )

            # Get progress information from the result
            user_progress = result.get("user_progress", {})

            return {
                "success": True,
                "query": query,
                "answer": result["answer"],
                "lookup_type": _classify_lookup_type(query),
                "content_context": {
                    "title": job.title,
                    "has_tutoring_data": tutoring_data is not None,
                    "current_chapter": user_progress.get("chapter", current_chapter),
                    "progress_percentage": user_progress.get("percentage", progress_percentage),
                    "progress_filtered": result.get("progress_filtered", True),
                },
                "spoiler_warning": _check_for_spoilers(
                    query, user_progress.get("percentage", progress_percentage)
                ),
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "X-ray lookup failed"),
                "answer": "I couldn't find information about that in the content.",
            }

    except Exception as e:
        logger.error(f"Error in xray_lookup MCP tool: {e}")
        return {"success": False, "error": f"X-ray lookup failed: {e!s}", "answer": ""}


def _classify_lookup_type(query: str) -> str:
    """Classify the type of X-ray lookup for analytics."""
    query_lower = query.lower().strip()

    # Simple keyword-based classification
    if any(word in query_lower for word in ["who is", "who's", "character", "person"]):
        return "character"
    elif any(word in query_lower for word in ["what is", "what's", "what does", "define"]):
        return "concept"
    elif any(word in query_lower for word in ["where", "location", "place", "setting"]):
        return "setting"
    elif any(word in query_lower for word in ["when", "time", "date", "period"]):
        return "time"
    elif any(word in query_lower for word in ["why", "how", "explain", "meaning", "significance"]):
        return "explanation"
    elif any(
        word in query_lower for word in ["what happened", "what's happening", "event", "scene"]
    ):
        return "event"
    else:
        return "general"


def _check_for_spoilers(query: str, progress_percentage: float) -> dict[str, Any]:
    """Check if query might contain spoilers based on progress."""
    query_lower = query.lower()

    # Keywords that often indicate future events
    spoiler_keywords = [
        "ending",
        "end",
        "finale",
        "conclusion",
        "resolution",
        "dies",
        "death",
        "killed",
        "married",
        "marries",
        "reveal",
        "revealed",
        "turns out",
        "actually",
        "twist",
        "surprise",
        "secret",
        "hidden",
        "later",
        "eventually",
        "finally",
        "ultimately",
    ]

    # Check if query contains potential spoiler keywords
    contains_spoiler_keywords = any(keyword in query_lower for keyword in spoiler_keywords)

    # More likely to be spoiler if user is early in the book
    early_in_book = progress_percentage < 0.5

    if contains_spoiler_keywords and early_in_book:
        return {
            "potential_spoiler": True,
            "warning": "This query might involve information from later in the content.",
            "suggestion": "Consider rephrasing to ask about what's happened so far.",
        }
    elif contains_spoiler_keywords:
        return {
            "potential_spoiler": True,
            "warning": "This query might involve future events.",
            "suggestion": None,
        }
    else:
        return {"potential_spoiler": False, "warning": None, "suggestion": None}
