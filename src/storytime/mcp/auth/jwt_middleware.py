"""JWT authentication middleware for MCP server with OAuth 2.1 support."""

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
    client_id: str | None = None
    scope: str | None = None


class MCPAuthenticationError(Exception):
    """Authentication error for MCP requests."""

    def __init__(self, message: str = "Authentication failed"):
        self.message = message
        super().__init__(self.message)


async def authenticate_mcp_request(authorization_header: str) -> MCPAuthContext | None:
    """Authenticate MCP request using OAuth JWT token.

    Args:
        authorization_header: Bearer token from Authorization header

    Returns:
        MCPAuthContext with authenticated user if successful, None otherwise
    """
    if not authorization_header:
        logger.debug("Missing authorization header")
        return None

    # Extract token from "Bearer <token>" format
    if not authorization_header.startswith("Bearer "):
        logger.debug("Invalid authorization header format")
        return None

    token = authorization_header[7:]  # Remove "Bearer " prefix

    try:
        # Validate OAuth JWT token
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        user_id: str | None = payload.get("sub")
        client_id: str | None = payload.get("client_id")
        scope: str | None = payload.get("scope")

        if user_id is None:
            logger.debug("Invalid token payload: missing user_id")
            return None

    except InvalidTokenError as e:
        logger.debug(f"Invalid JWT token: {e}")
        return None

    # Get user from database
    db_session = AsyncSessionLocal()
    try:
        # For demo purposes, handle mock user
        if user_id == "demo_user_123":
            # Create mock user for demo
            from datetime import datetime
            mock_user = User(
                id=user_id,
                email="demo@storytime.com",
                hashed_password="mock",
                created_at=datetime.utcnow()
            )
            return MCPAuthContext(
                user=mock_user,
                db_session=db_session,
                client_id=client_id,
                scope=scope
            )

        # Real user lookup
        result = await db_session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user is None:
            await db_session.close()
            logger.debug(f"User not found: {user_id}")
            return None

        return MCPAuthContext(
            user=user,
            db_session=db_session,
            client_id=client_id,
            scope=scope
        )

    except Exception as e:
        await db_session.close()
        logger.error(f"Database error during authentication: {e}")
        return None


async def authenticate_request(authorization_header: str) -> MCPAuthContext:
    """Legacy authentication method - raises exception on failure.

    Args:
        authorization_header: Bearer token from Authorization header

    Returns:
        MCPAuthContext with authenticated user and database session

    Raises:
        MCPAuthenticationError: If authentication fails
    """
    context = await authenticate_mcp_request(authorization_header)
    if context is None:
        raise MCPAuthenticationError("Authentication failed")
    return context


async def close_auth_context(context: MCPAuthContext) -> None:
    """Close the database session in the auth context."""
    try:
        await context.db_session.close()
    except Exception as e:
        logger.warning(f"Error closing database session: {e}")
