"""X-ray lookup MCP tool for contextual content queries (Kindle X-ray style)."""

import logging
from typing import Any

from openai import OpenAI
from sqlalchemy import select

from storytime.api.settings import get_settings
from storytime.database import Job
from storytime.mcp.auth import MCPAuthContext
from storytime.services.responses_api_service import ResponsesAPIVectorStoreService

logger = logging.getLogger(__name__)


async def xray_lookup(
    job_id: str,
    query: str,
    context: MCPAuthContext = None
) -> dict[str, Any]:
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

        # Create OpenAI client and vector store service for content access
        settings = get_settings()
        if not settings.openai_api_key:
            return {"success": False, "error": "OpenAI API key not configured", "answer": ""}

        openai_client = OpenAI(api_key=settings.openai_api_key)
        vector_service = ResponsesAPIVectorStoreService(openai_client, context.db_session)

        # Build X-ray lookup question
        xray_question = _build_xray_question(
            query, job.title or "this content", tutoring_data
        )

        # Use the existing vector service to get contextual response
        result = await vector_service.ask_question_about_job(
            user_id=context.user.id,
            job_id=job_id,
            question=xray_question
        )

        if result["success"]:
            logger.info(
                f"MCP xray_lookup: user={context.user.id}, job={job_id}, query='{query[:50]}...'"
            )

            return {
                "success": True,
                "query": query,
                "answer": result["answer"],
                "lookup_type": _classify_lookup_type(query),
                "content_context": {
                    "title": job.title,
                    "has_tutoring_data": tutoring_data is not None
                }
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "X-ray lookup failed"),
                "answer": "I couldn't find information about that in the content."
            }

    except Exception as e:
        logger.error(f"Error in xray_lookup MCP tool: {e}")
        return {"success": False, "error": f"X-ray lookup failed: {e!s}", "answer": ""}


def _build_xray_question(query: str, content_title: str, tutoring_data: dict = None) -> str:
    """Build X-ray lookup question with context (grug-brain approach)."""

    # Add context from tutoring analysis if available
    context_info = ""
    if tutoring_data:
        characters_text = ", ".join([f"{char['name']} ({char['role']})" for char in tutoring_data["characters"]])
        themes_text = ", ".join(tutoring_data["themes"])
        setting_text = f"{tutoring_data['setting']['time']} in {tutoring_data['setting']['place']}"

        context_info = f"""
CONTENT CONTEXT:
- Content Type: {tutoring_data['content_type']}
- Main Characters/Figures: {characters_text}
- Key Themes: {themes_text}
- Setting: {setting_text}
"""

    return f"""This is a contextual lookup query for "{content_title}" (similar to Kindle X-ray functionality).

{context_info}

USER'S X-RAY QUERY: {query}

Please provide a clear, concise answer that explains:
1. The specific information requested (who, what, where, when, why)
2. Relevant context from the content 
3. Any important background or significance

Focus on being helpful and informative, like a reference tool. If it's about a character, explain who they are and their role. If it's about a concept or event, explain what it is and why it matters in the story/content.

Keep the response focused and informative - this is meant to quickly orient the reader/listener."""


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
    elif any(word in query_lower for word in ["what happened", "what's happening", "event", "scene"]):
        return "event"
    else:
        return "general"
