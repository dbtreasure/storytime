"""OAuth 2.1 implementation for MCP server authentication."""

import secrets
import string
import uuid
from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.api.auth import get_db
from storytime.api.settings import get_settings
from storytime.database import User


class OAuthClientRegistration(BaseModel):
    """Dynamic client registration request."""
    client_name: str
    client_uri: HttpUrl | None = None
    redirect_uris: list[HttpUrl]
    grant_types: list[str] = ["authorization_code"]
    response_types: list[str] = ["code"]
    token_endpoint_auth_method: str = "client_secret_basic"


class OAuthClient(BaseModel):
    """Registered OAuth client."""
    client_id: str
    client_secret: str
    client_name: str
    client_uri: HttpUrl | None = None
    redirect_uris: list[HttpUrl]
    grant_types: list[str]
    response_types: list[str]
    token_endpoint_auth_method: str


class AuthorizationRequest(BaseModel):
    """OAuth authorization request."""
    response_type: str = "code"
    client_id: str
    redirect_uri: HttpUrl
    scope: str | None = "read"
    state: str | None = None
    code_challenge: str  # PKCE required
    code_challenge_method: str = "S256"


class TokenRequest(BaseModel):
    """OAuth token exchange request."""
    grant_type: str = "authorization_code"
    code: str
    redirect_uri: HttpUrl
    client_id: str
    client_secret: str | None = None
    code_verifier: str  # PKCE required


class TokenResponse(BaseModel):
    """OAuth token response."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: str | None = "read"


class AuthorizationCode(BaseModel):
    """Temporary authorization code storage."""
    code: str
    client_id: str
    user_id: str
    redirect_uri: str
    expires_at: datetime
    code_challenge: str
    code_challenge_method: str
    scope: str | None = None


# In-memory storage for demo (replace with Redis/database in production)
_registered_clients: dict[str, OAuthClient] = {}
_authorization_codes: dict[str, AuthorizationCode] = {}

settings = get_settings()
router = APIRouter(prefix="/api/v1/mcp-oauth", tags=["MCP OAuth"])


def generate_client_id() -> str:
    """Generate a unique client ID."""
    return f"mcp_client_{uuid.uuid4().hex[:16]}"


def generate_client_secret() -> str:
    """Generate a secure client secret."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(32))


def generate_authorization_code() -> str:
    """Generate a secure authorization code."""
    return secrets.token_urlsafe(32)


def verify_pkce_challenge(code_verifier: str, code_challenge: str, method: str = "S256") -> bool:
    """Verify PKCE code challenge."""
    import base64
    import hashlib

    if method == "S256":
        digest = hashlib.sha256(code_verifier.encode()).digest()
        expected = base64.urlsafe_b64encode(digest).decode().rstrip('=')
        return expected == code_challenge
    elif method == "plain":
        return code_verifier == code_challenge
    return False


@router.post("/register", response_model=OAuthClient)
async def register_client(registration: OAuthClientRegistration) -> OAuthClient:
    """Dynamic client registration endpoint."""

    # Validate redirect URIs (must be HTTPS or localhost)
    for uri in registration.redirect_uris:
        if not (uri.scheme == "https" or uri.host in ["localhost", "127.0.0.1"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Redirect URIs must use HTTPS or localhost"
            )

    # Generate client credentials
    client_id = generate_client_id()
    client_secret = generate_client_secret()

    # Create and store client
    client = OAuthClient(
        client_id=client_id,
        client_secret=client_secret,
        client_name=registration.client_name,
        client_uri=registration.client_uri,
        redirect_uris=registration.redirect_uris,
        grant_types=registration.grant_types,
        response_types=registration.response_types,
        token_endpoint_auth_method=registration.token_endpoint_auth_method
    )

    _registered_clients[client_id] = client

    return client


@router.get("/authorize")
async def authorize(
    response_type: str,
    client_id: str,
    redirect_uri: str,
    scope: str | None = "read",
    state: str | None = None,
    code_challenge: str | None = None,
    code_challenge_method: str = "S256",
    request: Request = None
):
    """OAuth authorization endpoint."""

    # Validate client
    if client_id not in _registered_clients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client_id"
        )

    client = _registered_clients[client_id]

    # Validate redirect URI
    if redirect_uri not in [str(uri) for uri in client.redirect_uris]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid redirect_uri"
        )

    # Validate PKCE (required)
    if not code_challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="code_challenge is required (PKCE)"
        )

    # For demo purposes, we'll auto-approve for registered clients
    # In production, this would redirect to a user consent page

    # For now, create a mock user session (in production, get from session)
    mock_user_id = "demo_user_123"  # This would come from authenticated session

    # Generate authorization code
    auth_code = generate_authorization_code()
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Store authorization code
    _authorization_codes[auth_code] = AuthorizationCode(
        code=auth_code,
        client_id=client_id,
        user_id=mock_user_id,
        redirect_uri=redirect_uri,
        expires_at=expires_at,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        scope=scope
    )

    # Redirect back to client with code
    redirect_url = f"{redirect_uri}?code={auth_code}"
    if state:
        redirect_url += f"&state={state}"

    return RedirectResponse(url=redirect_url)


@router.post("/token", response_model=TokenResponse)
async def token_exchange(
    grant_type: str,
    code: str,
    redirect_uri: str,
    client_id: str,
    code_verifier: str,
    client_secret: str | None = None,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """OAuth token exchange endpoint."""

    # Validate grant type
    if grant_type != "authorization_code":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported grant_type"
        )

    # Validate client
    if client_id not in _registered_clients:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials"
        )

    client = _registered_clients[client_id]

    # Validate client secret (if required)
    if client.token_endpoint_auth_method == "client_secret_basic" and client_secret != client.client_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials"
        )

    # Validate authorization code
    if code not in _authorization_codes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authorization code"
        )

    auth_code_data = _authorization_codes[code]

    # Check expiration
    if datetime.utcnow() > auth_code_data.expires_at:
        del _authorization_codes[code]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authorization code expired"
        )

    # Validate client_id and redirect_uri match
    if auth_code_data.client_id != client_id or auth_code_data.redirect_uri != redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authorization code"
        )

    # Verify PKCE
    if not verify_pkce_challenge(code_verifier, auth_code_data.code_challenge, auth_code_data.code_challenge_method):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code_verifier"
        )

    # Code is valid, delete it (one-time use)
    del _authorization_codes[code]

    # Get user from database (in demo, use mock user)
    # In production, use auth_code_data.user_id to get real user
    user_id = auth_code_data.user_id

    # Create JWT access token
    token_data = {
        "sub": user_id,
        "client_id": client_id,
        "scope": auth_code_data.scope,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=1)
    }

    access_token = jwt.encode(token_data, settings.jwt_secret_key, algorithm="HS256")

    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=3600,
        scope=auth_code_data.scope
    )


@router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    """OAuth server metadata endpoint."""
    base_url = f"{settings.base_url or 'http://localhost:8000'}/api/v1/mcp-oauth"

    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/authorize",
        "token_endpoint": f"{base_url}/token",
        "registration_endpoint": f"{base_url}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "none"],
        "code_challenge_methods_supported": ["S256", "plain"],
        "scopes_supported": ["read", "write"],
        "response_modes_supported": ["query"],
        "subject_types_supported": ["public"]
    }


async def extract_user_from_mcp_token(authorization: str, db: AsyncSession) -> User | None:
    """Extract user from MCP OAuth token."""
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]  # Remove "Bearer " prefix

    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            return None

        # For demo, return mock user. In production, query database:
        # result = await db.execute(select(User).where(User.id == user_id))
        # return result.scalar_one_or_none()

        # Mock user for demo
        if user_id == "demo_user_123":
            return User(
                id=user_id,
                email="demo@storytime.com",
                hashed_password="mock",
                created_at=datetime.utcnow()
            )

        return None

    except jwt.InvalidTokenError:
        return None
