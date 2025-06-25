"""JWT authentication middleware for MCP server."""

import logging
from dataclasses import dataclass

import jwt
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.api.settings import get_settings
from storytime.database import AsyncSessionLocal, User

logger = logging.getLogger(__name__)


@dataclass
class MCPAuthContext:
    """Authentication context for MCP requests."""

    user: User
    db_session: AsyncSession


class MCPAuthenticationError(Exception):
    """Authentication error for MCP requests."""

    def __init__(self, message: str = "Authentication failed"):
        self.message = message
        super().__init__(self.message)


async def authenticate_request(authorization_header: str) -> MCPAuthContext:
    """Authenticate MCP request using JWT token.

    Args:
        authorization_header: Bearer token from Authorization header

    Returns:
        MCPAuthContext with authenticated user and database session

    Raises:
        MCPAuthenticationError: If authentication fails
    """
    if not authorization_header:
        raise MCPAuthenticationError("Missing authorization header")

    # Extract token from "Bearer <token>" format
    if not authorization_header.startswith("Bearer "):
        raise MCPAuthenticationError("Invalid authorization header format")

    token = authorization_header[7:]  # Remove "Bearer " prefix

    try:
        # Validate JWT token using same logic as FastAPI auth
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        user_id: str | None = payload.get("sub")

        if user_id is None:
            raise MCPAuthenticationError("Invalid token payload")

    except InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        raise MCPAuthenticationError("Invalid or expired token") from e

    # Get user from database
    db_session = AsyncSessionLocal()
    try:
        result = await db_session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            await db_session.close()
            raise MCPAuthenticationError("User not found")

        return MCPAuthContext(user=user, db_session=db_session)

    except Exception as e:
        await db_session.close()
        logger.error(f"Database error during authentication: {e}")
        raise MCPAuthenticationError("Authentication failed") from e


async def close_auth_context(context: MCPAuthContext) -> None:
    """Close the database session in the auth context."""
    try:
        await context.db_session.close()
    except Exception as e:
        logger.warning(f"Error closing database session: {e}")
