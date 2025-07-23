"""MCP (Model Context Protocol) HTTP server for StorytimeTTS.

This module provides MCP HTTP endpoints that expose StorytimeTTS's vector store search
and tutoring capabilities as tools for OpenAI's Realtime API, enabling voice conversations
about audiobook content.
"""

from .http_server import router as mcp_router

__all__ = ["mcp_router"]
