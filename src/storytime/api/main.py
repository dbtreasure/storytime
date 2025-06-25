import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import router as auth_router
from .jobs import router as jobs_router
from .knowledge import router as knowledge_router
from .middleware import LoggingMiddleware
from .progress import router as progress_router
from .settings import get_settings
from .streaming import router as streaming_router

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


# DB migrations should be run via Alembic, not create_all()
# @app.on_event("startup")
# async def on_startup():
#     try:
#         await create_all()
#         logging.getLogger(__name__).info("DB bootstrap complete.")
#     except Exception as e:
#         logging.getLogger(__name__).error(f"DB bootstrap failed: {e}")


app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(streaming_router)
app.include_router(progress_router)
app.include_router(knowledge_router)


@app.get("/api/health", tags=["Utility"])
async def health() -> dict[str, str]:
    """Return basic service health status."""
    return {"status": "ok"}


@app.get("/up", tags=["Utility"])
async def up() -> dict[str, str]:
    """Health check endpoint for kamal-proxy."""
    return {"status": "ok"}


@app.get("/api/v1/environment", tags=["Utility"])
async def get_environment() -> dict[str, str | dict[str, bool]]:
    """Get environment information and feature flags."""
    return {
        "environment": settings.env,
        "features": {
            "signup_enabled": settings.env
            in ["dev", "docker"],  # Enable for dev and docker, disable for production
            "debug_mode": settings.env == "dev",
            "demo_mode": False,  # Could be enabled for specific environments later
        },
    }


# Serve React client static files - MUST BE AFTER ALL API ROUTES
static_dir = "/app/static"
if os.path.exists(static_dir):
    # Mount static assets at /assets
    app.mount("/assets", StaticFiles(directory=f"{static_dir}/assets"), name="assets")

    # Serve other static files
    @app.get("/vite.svg")
    async def vite_svg():
        return FileResponse(f"{static_dir}/vite.svg")

    # Catch-all route for React Router (SPA fallback) - MUST BE LAST
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(request: Request, full_path: str):
        # Only serve SPA for non-API routes
        if not full_path.startswith("api/"):
            return FileResponse(f"{static_dir}/index.html")

        # For API routes, return 404 to let FastAPI handle them properly
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Not found")
