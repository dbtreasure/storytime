from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
import logging

from .settings import get_settings
from .auth import get_api_key
from .middleware import LoggingMiddleware
from .chapters import router as chapters_router
from .tts import router as tts_router
from storytime.api import voice_management

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

app.include_router(chapters_router)
app.include_router(tts_router)
app.include_router(voice_management.router)

@app.get("/health", tags=["Utility"])
async def health(api_key: str = Depends(get_api_key)) -> dict[str, str]:
    """Return basic service health status. Requires API key."""
    logger.debug(f"Health check invoked by key: {api_key}")
    return {"status": "ok"} 