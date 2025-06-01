import enum
import logging
import uuid
from datetime import datetime

from passlib.context import CryptContext
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from storytime.api.settings import get_settings

Base = declarative_base()

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class BookStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def verify_password(self, password: str) -> bool:
        """Verify a password against the hash."""
        return pwd_context.verify(password, self.hashed_password)
    
    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hash a password for storing."""
        return pwd_context.hash(password)

class Book(Base):
    __tablename__ = "book"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(Enum(BookStatus), nullable=False, default=BookStatus.UPLOADED)
    progress_pct = Column(Integer, nullable=False, default=0)
    error_msg = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    text_key = Column(String, nullable=True)
    audio_key = Column(String, nullable=True)

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=True, future=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.getLogger(__name__).info("Database tables created (User, Book)") 