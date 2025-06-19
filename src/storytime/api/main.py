import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from storytime.database import create_all

from .auth import router as auth_router
from .jobs import router as jobs_router
from .streaming import router as streaming_router
from .progress import router as progress_router
from .middleware import LoggingMiddleware
from .settings import get_settings

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


app.include_router(auth_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")
app.include_router(streaming_router, prefix="/api")
app.include_router(progress_router, prefix="/api")

# Serve React client static files
static_dir = "/app/static"
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


@app.get("/api/health", tags=["Utility"])
async def health() -> dict[str, str]:
    """Return basic service health status."""
    return {"status": "ok"}


@app.get("/up", tags=["Utility"])
async def up() -> dict[str, str]:
    """Health check endpoint for kamal-proxy."""
    return {"status": "ok"}
