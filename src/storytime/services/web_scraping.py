"""Web scraping service using ScrapeGraphAI."""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from scrapegraphai.graphs import SmartScraperGraph

logger = logging.getLogger(__name__)


class WebScrapingService:
    """Service for extracting content from web URLs using ScrapeGraphAI."""

    def __init__(self):
        """Initialize the web scraping service."""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for web scraping")

        # Configuration for ScrapeGraphAI
        self.graph_config = {
            "llm": {
                "model": "gpt-4o-mini",  # Cost-effective model for content extraction
                "api_key": self.openai_api_key,
            },
            "verbose": False,
            "headless": True,
            "timeout": int(os.getenv("SCRAPING_TIMEOUT", 30)),
        }

    async def extract_content(self, url: str) -> dict[str, Any]:
        """
        Extract text content from a web URL.

        Args:
            url: The URL to scrape

        Returns:
            Dictionary containing extracted content and metadata

        Raises:
            Exception: If scraping fails or content is insufficient
        """
        try:
            logger.info(f"Starting content extraction from URL: {url}")

            # Create SmartScraperGraph instance
            smart_scraper = SmartScraperGraph(
                prompt="""Extract the main text content from this webpage that would be suitable for text-to-speech conversion.
                Focus on:
                - Main article text, blog post content, or primary text
                - Exclude navigation menus, advertisements, footers, and sidebar content
                - Preserve paragraph structure and readability
                - Include the page title if available
                - Return clean, readable text optimized for audio conversion""",
                source=url,
                config=self.graph_config,
            )

            # Execute scraping in a thread to avoid asyncio.run() conflicts
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, smart_scraper.run)

            if not result:
                raise Exception("Failed to extract content from URL")

            # Extract text content from result
            if isinstance(result, dict):
                # Try to get clean text content
                content = result.get("content") or result.get("text") or str(result)
                title = result.get("title") or result.get("page_title")
            else:
                content = str(result)
                title = None

            # Validate content length
            if len(content.strip()) < 100:
                raise Exception(
                    f"Extracted content is too short ({len(content)} characters). Minimum 100 characters required."
                )

            logger.info(f"Successfully extracted {len(content)} characters from {url}")

            return {
                "content": content.strip(),
                "title": title,
                "url": str(url),
                "character_count": len(content.strip()),
                "estimated_words": len(content.strip().split()),
            }

        except Exception as e:
            logger.error(f"Failed to extract content from {url}: {e!s}")
            raise Exception(f"Web scraping failed: {e!s}") from e

    def is_scraping_enabled(self) -> bool:
        """Check if web scraping is enabled via environment variable."""
        return os.getenv("SCRAPING_ENABLED", "true").lower() in ("true", "1", "yes")
