"""Authentication module for MCP server."""

from .jwt_middleware import MCPAuthContext, authenticate_request, close_auth_context

__all__ = ["MCPAuthContext", "authenticate_request", "close_auth_context"]
