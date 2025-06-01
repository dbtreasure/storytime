from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field
import logging


class Settings(BaseSettings):
    """Application settings loaded from environment variables or `.env` file."""

    env: str = Field(default="dev", description="Runtime environment, e.g. dev or prod")
    log_level: str = Field(default="INFO", description="Logging level")
    google_api_key: str | None = None
    openai_api_key: str | None = None
    eleven_labs_api_key: str | None = None
    figma_api_key: str | None = None

    # New: DB and Redis URLs
    database_url: str | None = Field(default=None, description="Database URL", alias="DATABASE_URL")
    alembic_database_url: str | None = Field(default=None, description="Alembic sync DB URL (for migrations)", alias="ALEMBIC_DATABASE_URL")
    redis_url: str | None = Field(default=None, description="Redis URL", alias="REDIS_URL")

    # JWT Authentication
    jwt_secret_key: str = Field(default="your-secret-key-here-change-in-production", description="JWT Secret Key")
    
    # DigitalOcean Spaces
    do_spaces_key: str | None = None
    do_spaces_secret: str | None = None
    do_spaces_region: str | None = None
    do_spaces_bucket: str | None = None
    do_spaces_endpoint: str | None = None

    # Observability/Tracing fields
    braintrust_api_key: str | None = None
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: str | None = None

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
    }


@lru_cache()
def get_settings() -> Settings:  # pragma: no cover
    """Return a cached instance of Settings."""
    s = Settings()
    logging.basicConfig(level=s.log_level)
    logging.getLogger(__name__).info(f"Loaded DATABASE_URL: {getattr(s, 'database_url', None)}")
    logging.getLogger(__name__).info(f"Loaded REDIS_URL: {getattr(s, 'redis_url', None)}")
    return s 