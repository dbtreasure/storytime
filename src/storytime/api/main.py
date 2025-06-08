import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from storytime.api import voice_management
from storytime.database import create_all

from .auth import router as auth_router
from .chapters import router as chapters_router
from .jobs import router as jobs_router
from .middleware import LoggingMiddleware
from .settings import get_settings
from .tts import router as tts_router

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Storytime API", version="0.1.0")
app.add_middleware(LoggingMiddleware)

# CORS middleware (allow all for now; adjust in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create DB tables on startup (MVP, not for prod)
@app.on_event("startup")
async def on_startup():
    try:
        await create_all()
        logging.getLogger(__name__).info("DB bootstrap complete.")
    except Exception as e:
        logging.getLogger(__name__).error(f"DB bootstrap failed: {e}")

app.include_router(auth_router)
app.include_router(chapters_router)
app.include_router(tts_router)
app.include_router(jobs_router)
app.include_router(voice_management.router)

@app.get("/health", tags=["Utility"])
async def health() -> dict[str, str]:
    """Return basic service health status."""
    return {"status": "ok"}
