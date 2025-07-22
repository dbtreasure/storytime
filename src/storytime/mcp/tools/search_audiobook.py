"""Search audiobook content MCP tool."""

import logging
from typing import Any

from openai import OpenAI

from storytime.api.settings import get_settings
from storytime.mcp.auth import MCPAuthContext
from storytime.services.responses_api_service import ResponsesAPIVectorStoreService

logger = logging.getLogger(__name__)


async def search_audiobook(
    job_id: str, query: str, limit: int = 5, context: MCPAuthContext = None
) -> dict[str, Any]:
    """Search for content within a specific audiobook using vector store.

    Args:
        job_id: The audiobook job ID to search within
        query: The search query
        limit: Maximum number of results to return (default: 5)
        context: Authentication context with user and database session

    Returns:
        Dict containing search results with success status, query info, and results
    """
    try:
        if not context:
            return {"success": False, "error": "Authentication context required", "results": []}

        # Create OpenAI client and vector store service
        settings = get_settings()
        if not settings.openai_api_key:
            return {"success": False, "error": "OpenAI API key not configured", "results": []}

        openai_client = OpenAI(api_key=settings.openai_api_key)
        vector_service = ResponsesAPIVectorStoreService(openai_client, context.db_session)

        # Perform search using existing service
        result = await vector_service.search_job_content(
            user_id=context.user.id, job_id=job_id, query=query, max_results=limit
        )

        logger.info(
            f"MCP search_audiobook: user={context.user.id}, job={job_id}, query='{query}', results={len(result.get('results', []))}"
        )

        return result

    except Exception as e:
        logger.error(f"Error in search_audiobook MCP tool: {e}")
        return {"success": False, "error": f"Search failed: {e!s}", "results": []}
