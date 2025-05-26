from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from .settings import get_settings

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Storytime API", version="0.1.0")

# CORS middleware (allow all for now; adjust in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Utility"])
async def health() -> dict[str, str]:
    """Return basic service health status."""

    logger.debug("Health check invoked")
    return {"status": "ok"} 