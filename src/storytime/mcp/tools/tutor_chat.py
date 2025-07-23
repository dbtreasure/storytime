"""Tutoring conversation MCP tool for Socratic dialogue."""

import logging
from typing import Any

from openai import OpenAI
from sqlalchemy import select

from storytime.api.settings import get_settings
from storytime.database import Job
from storytime.mcp.auth import MCPAuthContext
from storytime.services.responses_api_service import ResponsesAPIVectorStoreService

logger = logging.getLogger(__name__)


async def tutor_chat(
    job_id: str,
    user_message: str,
    conversation_history: str = "",
    context: MCPAuthContext = None
) -> dict[str, Any]:
    """Engage in Socratic tutoring dialogue about audiobook content.

    Args:
        job_id: The audiobook job ID to discuss
        user_message: The user's current message/question
        conversation_history: Previous conversation context (optional)
        context: Authentication context with user and database session

    Returns:
        Dict containing tutor response with success status and dialogue
    """
    try:
        if not context:
            return {"success": False, "error": "Authentication context required", "response": ""}

        # Get job and verify ownership
        result = await context.db_session.execute(
            select(Job).where(Job.id == job_id, Job.user_id == context.user.id)
        )
        job = result.scalar_one_or_none()

        if not job:
            return {"success": False, "error": "Job not found or access denied", "response": ""}

        # Get tutoring analysis from job config (grug-brain storage)
        tutoring_data = job.config.get("tutoring_analysis") if job.config else None

        if not tutoring_data:
            return {
                "success": False,
                "error": "Tutoring analysis not available for this content",
                "response": "I don't have tutoring analysis for this content yet. Please try again later."
            }

        # Create OpenAI client and vector store service for content access
        settings = get_settings()
        if not settings.openai_api_key:
            return {"success": False, "error": "OpenAI API key not configured", "response": ""}

        openai_client = OpenAI(api_key=settings.openai_api_key)
        vector_service = ResponsesAPIVectorStoreService(openai_client, context.db_session)

        # Build tutoring question with embedded instructions (grug-brain approach)
        conversation_context = ""
        if conversation_history:
            conversation_context = f"\n\nPrevious conversation context:\n{conversation_history}\n"

        # Create comprehensive tutoring question with all context embedded
        tutoring_question = _build_tutoring_question(
            tutoring_data, job.title or "this content", user_message, conversation_context
        )

        # Use the existing vector service to get contextual response
        result = await vector_service.ask_question_about_job(
            user_id=context.user.id,
            job_id=job_id,
            question=tutoring_question
        )

        if result["success"]:
            logger.info(
                f"MCP tutor_chat: user={context.user.id}, job={job_id}, message='{user_message[:50]}...'"
            )

            return {
                "success": True,
                "response": result["answer"],
                "tutoring_data": {
                    "themes": tutoring_data["themes"],
                    "content_type": tutoring_data["content_type"],
                    "available_questions": tutoring_data["discussion_questions"]
                }
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Tutoring response failed"),
                "response": "I'm having trouble accessing the content right now. Please try again."
            }

    except Exception as e:
        logger.error(f"Error in tutor_chat MCP tool: {e}")
        return {"success": False, "error": f"Tutoring conversation failed: {e!s}", "response": ""}


def _build_tutoring_question(
    tutoring_data: dict, content_title: str, user_message: str, conversation_context: str
) -> str:
    """Build complete tutoring question with embedded instructions (grug-brain approach)."""

    themes_text = ", ".join(tutoring_data["themes"])
    characters_text = ", ".join([f"{char['name']} ({char['role']})" for char in tutoring_data["characters"]])
    setting_text = f"{tutoring_data['setting']['time']} in {tutoring_data['setting']['place']}"

    return f"""I need you to act as an expert Socratic tutor for "{content_title}". 

CONTENT ANALYSIS FOR TUTORING:
- Content Type: {tutoring_data['content_type']}
- Main Themes: {themes_text}
- Key Characters/Figures: {characters_text}
- Setting/Context: {setting_text}

TUTORING APPROACH - Follow these principles:
1. Use the Socratic method - guide the student to discover insights through questioning
2. Ask probing follow-up questions rather than giving direct answers  
3. Help the student connect ideas to their existing knowledge
4. Encourage critical thinking and analysis
5. Be encouraging and supportive while challenging their understanding
6. Draw on the specific content of this audiobook to support your tutoring

AVAILABLE DISCUSSION STARTERS you can reference:
{chr(10).join(f'- {q}' for q in tutoring_data['discussion_questions'])}

{conversation_context}

STUDENT'S MESSAGE: {user_message}

Please respond as a Socratic tutor, using your knowledge of the audiobook content to guide the student's learning. Ask thoughtful questions, provide insights when appropriate, and help them think deeply about the material."""
