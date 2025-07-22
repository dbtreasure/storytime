"""Search library content MCP tool."""

import logging
from typing import Any

from openai import OpenAI

from storytime.api.settings import get_settings
from storytime.mcp.auth import MCPAuthContext
from storytime.services.responses_api_service import ResponsesAPIVectorStoreService

logger = logging.getLogger(__name__)


async def search_library(
    query: str, limit: int = 10, context: MCPAuthContext = None
) -> dict[str, Any]:
    """Search across user's entire audiobook library.

    Args:
        query: The search query
        limit: Maximum number of results to return (default: 10)
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

        # Search library using existing service
        result = await vector_service.search_library(
            user_id=context.user.id, query=query, max_results=limit
        )

        logger.info(
            f"MCP search_library: user={context.user.id}, query='{query}', results={len(result.get('results', []))}"
        )

        return result

    except Exception as e:
        logger.error(f"Error in search_library MCP tool: {e}")
        return {"success": False, "error": f"Library search failed: {e!s}", "results": []}
