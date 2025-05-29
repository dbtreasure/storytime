from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables or `.env` file."""

    env: str = Field(default="dev", description="Runtime environment, e.g. dev or prod")
    log_level: str = Field(default="INFO", description="Logging level")
    google_api_key: str | None = None
    openai_api_key: str | None = None
    eleven_labs_api_key: str | None = None
    figma_api_key: str | None = None

    # Observability/Tracing fields
    braintrust_api_key: str | None = None
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: str | None = None

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


@lru_cache()
def get_settings() -> Settings:  # pragma: no cover
    """Return a cached instance of Settings."""

    return Settings() 