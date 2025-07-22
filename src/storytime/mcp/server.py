"""Main MCP server implementation for StorytimeTTS."""

import asyncio
import logging
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel

from storytime.api.settings import get_settings
from storytime.mcp.auth import MCPAuthContext, authenticate_request, close_auth_context
from storytime.mcp.tools import ask_about_book, search_audiobook, search_library

logger = logging.getLogger(__name__)


# Pydantic models for tool parameters
class SearchAudiobookParams(BaseModel):
    job_id: str
    query: str
    limit: int = 5


class AskAboutBookParams(BaseModel):
    job_id: str
    question: str


class SearchLibraryParams(BaseModel):
    query: str
    limit: int = 10


# Global auth context storage for request handling
_auth_context: MCPAuthContext | None = None


async def get_auth_context() -> MCPAuthContext:
    """Get the current authentication context."""
    if not _auth_context:
        raise ValueError("No authentication context available")
    return _auth_context


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server."""

    # Initialize FastMCP server
    mcp = FastMCP("StorytimeTTS-Knowledge")

    @mcp.tool(description="Search for content within a specific audiobook using vector store")
    async def search_audiobook_tool(params: SearchAudiobookParams) -> dict[str, Any]:
        """Search for content within a specific audiobook using vector store.

        This tool searches within the content of a specific audiobook job
        using vector similarity search to find relevant passages.
        """
        try:
            context = await get_auth_context()
            return await search_audiobook(
                job_id=params.job_id, query=params.query, limit=params.limit, context=context
            )
        except Exception as e:
            logger.error(f"Error in search_audiobook_tool: {e}")
            return {"success": False, "error": f"Tool execution failed: {e!s}", "results": []}

    @mcp.tool(description="Ask a question about specific audiobook content")
    async def ask_about_book_tool(params: AskAboutBookParams) -> dict[str, Any]:
        """Ask a question about specific audiobook content.

        This tool uses the vector store to find relevant content and
        generates an answer to questions about the audiobook.
        """
        try:
            context = await get_auth_context()
            return await ask_about_book(
                job_id=params.job_id, question=params.question, context=context
            )
        except Exception as e:
            logger.error(f"Error in ask_about_book_tool: {e}")
            return {"success": False, "error": f"Tool execution failed: {e!s}", "answer": ""}

    @mcp.tool(description="Search across user's entire audiobook library")
    async def search_library_tool(params: SearchLibraryParams) -> dict[str, Any]:
        """Search across user's entire audiobook library.

        This tool performs vector similarity search across all audiobooks
        in the user's library to find relevant content.
        """
        try:
            context = await get_auth_context()
            return await search_library(query=params.query, limit=params.limit, context=context)
        except Exception as e:
            logger.error(f"Error in search_library_tool: {e}")
            return {"success": False, "error": f"Tool execution failed: {e!s}", "results": []}

    return mcp


async def handle_mcp_request(authorization: str, request_handler):
    """Handle MCP request with authentication."""
    global _auth_context

    try:
        # Authenticate request
        _auth_context = await authenticate_request(authorization)
        logger.info(f"MCP request authenticated for user: {_auth_context.user.email}")

        # Handle the request
        result = await request_handler()

        return result

    except Exception as e:
        logger.error(f"Error handling MCP request: {e}")
        raise
    finally:
        # Clean up auth context
        if _auth_context:
            await close_auth_context(_auth_context)
            _auth_context = None


def start_mcp_server():
    """Start the MCP server with HTTP/SSE transport."""
    import threading

    settings = get_settings()
    logger.info(f"Starting MCP server on {settings.mcp_server_host}:{settings.mcp_server_port}")

    # Create MCP server
    mcp = create_mcp_server()

    try:
        # Check if we're already in an async context
        try:
            asyncio.get_running_loop()
            logger.info("Detected running event loop, starting MCP server in thread")

            # Run in a separate thread to avoid event loop conflict
            def run_server():
                mcp.run(
                    transport="sse", host=settings.mcp_server_host, port=settings.mcp_server_port
                )

            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()
            server_thread.join()

        except RuntimeError:
            # No running event loop, safe to run directly
            logger.info("No running event loop detected, starting MCP server directly")
            mcp.run(transport="sse", host=settings.mcp_server_host, port=settings.mcp_server_port)

    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        raise


if __name__ == "__main__":
    # Run the MCP server
    start_mcp_server()
