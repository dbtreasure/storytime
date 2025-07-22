"""Ask question about audiobook content MCP tool."""

import logging
from typing import Any

from openai import OpenAI

from storytime.api.settings import get_settings
from storytime.mcp.auth import MCPAuthContext
from storytime.services.responses_api_service import ResponsesAPIVectorStoreService

logger = logging.getLogger(__name__)


async def ask_about_book(
    job_id: str, question: str, context: MCPAuthContext = None
) -> dict[str, Any]:
    """Ask a question about specific audiobook content.

    Args:
        job_id: The audiobook job ID to ask about
        question: The question to ask about the audiobook content
        context: Authentication context with user and database session

    Returns:
        Dict containing the answer with success status, question info, and answer
    """
    try:
        if not context:
            return {"success": False, "error": "Authentication context required", "answer": ""}

        # Create OpenAI client and vector store service
        settings = get_settings()
        if not settings.openai_api_key:
            return {"success": False, "error": "OpenAI API key not configured", "answer": ""}

        openai_client = OpenAI(api_key=settings.openai_api_key)
        vector_service = ResponsesAPIVectorStoreService(openai_client, context.db_session)

        # Ask question using existing service
        result = await vector_service.ask_question_about_job(
            user_id=context.user.id, job_id=job_id, question=question
        )

        logger.info(
            f"MCP ask_about_book: user={context.user.id}, job={job_id}, question='{question[:50]}...'"
        )

        return result

    except Exception as e:
        logger.error(f"Error in ask_about_book MCP tool: {e}")
        return {"success": False, "error": f"Question answering failed: {e!s}", "answer": ""}
