#!/usr/bin/env python3
"""Quick integration test for URL input functionality."""

import os
import sys

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def test_model_validation():
    """Basic validation checks for CreateJobRequest."""
    from storytime.models import CreateJobRequest

    # Valid URL input
    req = CreateJobRequest(
        title="Test Article",
        url="https://example.com/article",
        voice_config={"provider": "openai", "voice_id": "alloy"},
    )
    assert req.url == "https://example.com/article"

    # Valid text input
    req = CreateJobRequest(
        title="Test Text",
        content="This is a test text content that is long enough to pass validation requirements.",
        voice_config={"provider": "openai", "voice_id": "alloy"},
    )
    assert req.content.startswith("This is a test")

    # Missing input should raise error
    with pytest.raises(ValueError):
        CreateJobRequest(title="Invalid", voice_config={"provider": "openai", "voice_id": "alloy"})

    # Multiple inputs should raise error
    with pytest.raises(ValueError):
        CreateJobRequest(
            title="Invalid",
            content="Text",
            url="https://example.com",
            voice_config={"provider": "openai", "voice_id": "alloy"},
        )


def test_web_scraping_service():
    """Ensure WebScrapingService can be created."""
    pytest.importorskip("dotenv")
    from storytime.services.web_scraping import WebScrapingService

    os.environ["OPENAI_API_KEY"] = "test-key"
    service = WebScrapingService()
    assert service.graph_config is not None
    assert isinstance(service.is_scraping_enabled(), bool)


