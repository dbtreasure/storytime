import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta

import jwt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytime.api.settings import get_settings
from storytime.database import AsyncSessionLocal, User

# Security scheme
security = HTTPBearer()


# Pydantic models for API
class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str


# JWT utilities
settings = get_settings()


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm="HS256")
    return encoded_jwt


async def verify_token(token: str) -> User | None:
    """Verify JWT token and return user if valid."""
    import logging

    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Decoding token with secret key length: {len(settings.jwt_secret_key)}")
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        logger.info(f"Token decoded successfully, user_id: {user_id}")
        if user_id is None:
            logger.error("No 'sub' field in token payload")
            return None
    except InvalidTokenError as e:
        logger.error(f"JWT decode error: {e}")
        return None

    # Get user from database
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            logger.info(f"User found: {user.email}")
        else:
            logger.error(f"No user found with id: {user_id}")

    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(lambda: AsyncSessionLocal()),
) -> User:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except InvalidTokenError as e:
        raise credentials_exception from e

    # Get user from database
    async with db as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Router
router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    # Check if signups are enabled based on environment
    if settings.env not in ["dev", "docker"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Signups are temporarily disabled",
        )

    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create new user
    hashed_password = User.hash_password(user_data.password)
    new_user = User(id=str(uuid.uuid4()), email=user_data.email, hashed_password=hashed_password)

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return UserResponse(id=new_user.id, email=new_user.email, created_at=new_user.created_at)


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token."""

    # Get user from database
    result = await db.execute(select(User).where(User.email == user_data.email))
    user = result.scalar_one_or_none()

    if not user or not user.verify_password(user_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(data={"sub": user.id})

    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return UserResponse(
        id=current_user.id, email=current_user.email, created_at=current_user.created_at
    )


async def get_current_user_websocket(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Authenticate user from WebSocket connection.
    Returns None if authentication fails (allows handling in endpoint).
    """
    # Try to get token from query parameters or headers
    token = None
    
    # Check query parameters first (common for WebSocket connections)
    if "token" in websocket.query_params:
        token = websocket.query_params["token"]
    # Check Authorization header
    elif "authorization" in websocket.headers:
        auth = websocket.headers["authorization"]
        if auth.startswith("Bearer "):
            token = auth[7:]
    
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, get_settings().jwt_secret_key, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
    except InvalidTokenError:
        return None
    
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    return user
