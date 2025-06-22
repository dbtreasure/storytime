import logging
import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables or `.env` file."""

    env: Literal["dev", "docker", "production"] = Field(
        default="dev",
        description="Runtime environment: dev (local), docker (docker-compose), or production",
    )
    log_level: str = Field(default="INFO", description="Logging level")
    google_api_key: str | None = None
    openai_api_key: str | None = None
    eleven_labs_api_key: str | None = None
    figma_api_key: str | None = None

    # New: DB and Redis URLs
    database_url: str | None = Field(default=None, description="Database URL", alias="DATABASE_URL")
    alembic_database_url: str | None = Field(
        default=None,
        description="Alembic sync DB URL (for migrations)",
        alias="ALEMBIC_DATABASE_URL",
    )
    redis_url: str | None = Field(default=None, description="Redis URL", alias="REDIS_URL")

    # JWT Authentication
    jwt_secret_key: str = Field(..., description="JWT Secret Key")

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
        "extra": "ignore",  # Ignore extra environment variables (like Kamal secrets)
    }

    @field_validator("database_url", mode="after")
    @classmethod
    def validate_database_url(cls, v: str | None, values) -> str:
        """Validate and set database URL based on environment."""
        if not v:
            # Provide default URLs based on environment
            env = values.data.get("env", "dev")
            if env == "docker":
                return "postgresql+asyncpg://postgres:postgres@db:5432/storytime"
            elif env == "dev":
                return "postgresql+asyncpg://postgres:postgres@localhost:5432/storytime"
            else:
                raise ValueError(f"DATABASE_URL must be provided for {env} environment")
        return v

    @field_validator("redis_url", mode="after")
    @classmethod
    def validate_redis_url(cls, v: str | None, values) -> str:
        """Validate and set Redis URL based on environment."""
        if not v:
            # Provide default URLs based on environment
            env = values.data.get("env", "dev")
            if env == "docker":
                return "redis://redis:6379/0"
            elif env == "dev":
                return "redis://localhost:6379/0"
            else:
                raise ValueError(f"REDIS_URL must be provided for {env} environment")
        return v


@lru_cache
def get_settings() -> Settings:  # pragma: no cover
    """Return a cached instance of Settings."""
    s = Settings()
    logging.basicConfig(level=s.log_level)
    logger = logging.getLogger(__name__)

    # Log environment information
    logger.info("=" * 60)
    logger.info(f"Starting StorytimeTTS in {s.env.upper()} environment")
    logger.info("=" * 60)
    logger.info(f"Environment: {s.env}")
    logger.info(f"Database URL: {s.database_url}")
    logger.info(f"Redis URL: {s.redis_url}")
    logger.info(f"DO Spaces Bucket: {s.do_spaces_bucket}")
    logger.info(f"TTS Provider: {os.environ.get('TTS_PROVIDER', 'openai')}")
    logger.info("=" * 60)

    # Validate critical settings for production
    if s.env == "production":
        if not s.openai_api_key:
            logger.warning("OPENAI_API_KEY not set in production!")
        if not s.google_api_key:
            logger.warning("GOOGLE_API_KEY not set in production - text preprocessing will be disabled!")
        if not s.do_spaces_key or not s.do_spaces_secret:
            logger.warning("DigitalOcean Spaces credentials not set in production!")

    return s
