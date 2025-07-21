"""FastMCP integration with existing FastAPI application."""

import logging
from typing import Any

from fastmcp import Context, FastMCP
from openai import OpenAI
from pydantic import BaseModel

from storytime.api.settings import get_settings
from storytime.mcp.auth.jwt_middleware import authenticate_mcp_request, close_auth_context
from storytime.services.responses_api_service import ResponsesAPIVectorStoreService

logger = logging.getLogger(__name__)


# Pydantic models optimized for OpenAI deep research
class SearchParams(BaseModel):
    query: str
    limit: int = 10


class FetchParams(BaseModel):
    id: str


def create_mcp_app() -> FastMCP:
    """Create FastMCP application with StorytimeTTS tools."""

    # Create FastMCP with explicit configuration
    mcp = FastMCP(
        name="StorytimeTTS-Knowledge",
        instructions="Search and retrieve content from StorytimeTTS audiobook library",
    )

    @mcp.tool(
        description="Searches for content across user's audiobook library using the provided query string and returns matching results. Use this to find relevant audiobooks, chapters, or content passages based on user queries."
    )
    async def search(params: SearchParams, context: Context) -> dict[str, Any]:
        """Search across user's audiobook library.

        This tool searches across the user's complete audiobook library using
        vector similarity search to find relevant content passages.
        """
        try:
            # Get authorization from MCP context
            auth_header = None
            if hasattr(context, "headers") and context.headers:
                auth_header = context.headers.get("authorization")
            elif hasattr(context, "meta") and context.meta:
                auth_header = context.meta.get("authorization")

            if not auth_header:
                return {
                    "results": [
                        {
                            "id": "auth_error",
                            "title": "Authentication Required",
                            "text": "This tool requires authentication. Please authenticate via OAuth to access your audiobook library.",
                            "url": None,
                        }
                    ]
                }

            # Authenticate user
            auth_context = await authenticate_mcp_request(auth_header)
            if not auth_context:
                return {
                    "results": [
                        {
                            "id": "auth_failed",
                            "title": "Authentication Failed",
                            "text": "Authentication failed. Please check your credentials and try again.",
                            "url": None,
                        }
                    ]
                }

            try:
                # Get vector store service
                settings = get_settings()
                if not settings.openai_api_key:
                    return {
                        "results": [
                            {
                                "id": "config_error",
                                "title": "Service Configuration Error",
                                "text": "OpenAI API key not configured. Please contact administrator.",
                                "url": None,
                            }
                        ]
                    }

                openai_client = OpenAI(api_key=settings.openai_api_key)
                service = ResponsesAPIVectorStoreService(openai_client, auth_context.db_session)

                # Search user's library
                result = await service.search_library(
                    user_id=auth_context.user.id, query=params.query, max_results=params.limit
                )

                if not result.get("success"):
                    return {
                        "results": [
                            {
                                "id": "search_error",
                                "title": "Search Error",
                                "text": f"Search failed: {result.get('error', 'Unknown error')}",
                                "url": None,
                            }
                        ]
                    }

                # Transform results to OpenAI format
                search_results = []
                for item in result.get("results", []):
                    search_results.append(
                        {
                            "id": item.get("id", "unknown"),
                            "title": item.get("title", "Untitled"),
                            "text": item.get("text", "")[:500],  # Limit snippet length
                            "url": item.get("url"),  # Can be None
                        }
                    )

                return {"results": search_results}

            finally:
                # Always close database session
                if auth_context:
                    await close_auth_context(auth_context)

        except Exception as e:
            logger.error(f"Error in search tool: {e}")
            return {
                "results": [
                    {
                        "id": "internal_error",
                        "title": "Internal Error",
                        "text": f"An internal error occurred while searching: {e!s}",
                        "url": None,
                    }
                ]
            }

    @mcp.tool(
        description="Retrieves detailed content for a specific audiobook resource identified by the given ID. Use this after search to get complete content for citation purposes."
    )
    async def fetch(params: FetchParams, context: Context) -> dict[str, Any]:
        """Fetch detailed content for a specific audiobook resource.

        This tool retrieves the complete content of a specific audiobook
        passage or chapter identified by its ID.
        """
        try:
            # Get authorization from MCP context
            auth_header = None
            if hasattr(context, "headers") and context.headers:
                auth_header = context.headers.get("authorization")
            elif hasattr(context, "meta") and context.meta:
                auth_header = context.meta.get("authorization")

            if not auth_header:
                return {
                    "id": params.id,
                    "title": "Authentication Required",
                    "text": "This tool requires authentication. Please authenticate via OAuth to access audiobook content.",
                    "url": None,
                }

            # Authenticate user
            auth_context = await authenticate_mcp_request(auth_header)
            if not auth_context:
                return {
                    "id": params.id,
                    "title": "Authentication Failed",
                    "text": "Authentication failed. Please check your credentials and try again.",
                    "url": None,
                }

            try:
                # For now, return a mock response since fetch by ID requires more implementation
                # In a full implementation, this would:
                # 1. Parse the ID to extract job_id and chunk_id
                # 2. Query the vector store for the specific content
                # 3. Return the full content with metadata

                return {
                    "id": params.id,
                    "title": "Content Fetch Not Yet Implemented",
                    "text": f"Fetch functionality for ID '{params.id}' is not yet implemented. Use the search tool to find content.",
                    "url": None,
                    "metadata": {"status": "not_implemented", "user_id": auth_context.user.id},
                }

            finally:
                # Always close database session
                if auth_context:
                    await close_auth_context(auth_context)

        except Exception as e:
            logger.error(f"Error in fetch tool: {e}")
            return {
                "id": params.id,
                "title": "Internal Error",
                "text": f"An internal error occurred while fetching content: {e!s}",
                "url": None,
            }

    return mcp
