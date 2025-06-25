"""MCP (Model Context Protocol) server implementation for StorytimeTTS.

This module provides an MCP server that exposes StorytimeTTS's vector store search
capabilities as tools for OpenAI's Realtime API, enabling voice conversations
about audiobook content.
"""

from .fastapi_integration import create_mcp_app

__all__ = ["create_mcp_app"]
