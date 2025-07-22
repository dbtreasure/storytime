"""
MCP integration for Pipecat using official pipecat.services.mcp_service.

Based on examples/foundational/39a-mcp-run-sse.py and pipecat MCP service architecture.
"""

import logging
from typing import Any

try:
    from mcp.client.session_group import SseServerParameters
    from pipecat.services.mcp_service import MCPClient
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    MCPClient = None
    SseServerParameters = None

logger = logging.getLogger(__name__)


async def create_mcp_client(mcp_base_url: str, mcp_access_token: str) -> MCPClient:
    """Create and initialize MCP client using official Pipecat MCP service."""

    if not MCP_AVAILABLE:
        raise ImportError("MCP dependencies not available. Install with: pip install pipecat-ai[mcp]")

    # Create SSE server parameters for MCP connection
    sse_params = SseServerParameters(
        url=f"{mcp_base_url}/mcp-server/sse",
        headers={"Authorization": f"Bearer {mcp_access_token}"}
    )

    # Create MCP client using official Pipecat service
    mcp_client = MCPClient(sse_params)

    logger.info("Created MCP client using official Pipecat MCP service")
    return mcp_client


async def register_mcp_tools_with_llm(mcp_client: MCPClient, llm) -> dict[str, Any]:
    """Register MCP tools with LLM using official Pipecat patterns."""

    try:
        # Use the official Pipecat method to register tools
        tools_schema = await mcp_client.register_tools(llm)

        logger.info(f"Successfully registered MCP tools with LLM: {tools_schema}")
        return {"tools_schema": tools_schema, "success": True}

    except Exception as e:
        logger.error(f"Failed to register MCP tools with LLM: {e}")
        return {"error": str(e), "success": False}


async def create_mcp_integration(
    mcp_base_url: str,
    mcp_access_token: str
) -> tuple[None | Any, dict[str, Any]]:
    """Create and initialize MCP integration using official Pipecat patterns."""

    if not MCP_AVAILABLE:
        logger.warning("MCP not available, skipping MCP integration")
        return None, {}

    try:
        # Create MCP client using official Pipecat service
        mcp_client = await create_mcp_client(mcp_base_url, mcp_access_token)

        logger.info("MCP integration successful - client created")

        # Return client and empty functions dict (tools will be registered later with LLM)
        return mcp_client, {}

    except Exception as e:
        logger.error(f"Failed to initialize MCP integration: {e}")
        return None, {}
