import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, DateTime, Integer, Enum
import enum
from storytime.api.settings import get_settings
import logging

Base = declarative_base()

class BookStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"

class Book(Base):
    __tablename__ = "book"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=False)
    status = Column(Enum(BookStatus), nullable=False, default=BookStatus.UPLOADED)
    progress_pct = Column(Integer, nullable=False, default=0)
    error_msg = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

settings = get_settings()
engine = create_async_engine(settings.database_url, echo=True, future=True)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.getLogger(__name__).info("Database tables created (Book)") 