"""Web scraping service using Playwright screenshots and Gemini Flash for text extraction."""

import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional
from io import BytesIO

from playwright.async_api import async_playwright, Page
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class WebScrapingService:
    """Service for extracting content from web URLs using Playwright and Gemini Flash."""

    def __init__(self):
        """Initialize the web scraping service."""
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        if not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required for web scraping")

        # Initialize Gemini client
        self.client = genai.Client(api_key=self.google_api_key)

        # Configuration
        self.timeout = int(os.getenv("SCRAPING_TIMEOUT", 30))
        self.model = os.getenv("SCRAPING_MODEL", "gemini-2.0-flash-001")

        # Minimum content thresholds
        self.min_chars = int(os.getenv("SCRAPING_MIN_CONTENT_LENGTH", 1000))
        self.min_words = 200

    async def extract_content(self, url: str) -> dict[str, Any]:
        """
        Extract text content from a web URL using screenshot capture and Gemini Flash.

        Args:
            url: The URL to scrape

        Returns:
            Dictionary containing extracted content and metadata

        Raises:
            Exception: If extraction fails
        """
        start_time = time.time()

        try:
            logger.info(f"Starting screenshot-based extraction for {url}")

            # Capture screenshot(s) of the webpage
            screenshots = await self._capture_screenshots(url)

            if not screenshots:
                raise Exception("Failed to capture screenshots")

            logger.info(f"Captured {len(screenshots)} screenshot(s), total size: {sum(len(s) for s in screenshots)} bytes")

            # Extract text using Gemini Flash
            content = await self._extract_text_from_screenshots(screenshots, url)

            # Debug logging
            logger.info(f"Extracted content length: {len(content)} chars, {len(content.split())} words")
            logger.info(f"First 500 chars: {content[:500]}...")

            # Validate extraction
            if not self._validate_extraction(content):
                logger.error(f"Validation failed - content: {len(content)} chars, {len(content.split())} words")
                logger.error(f"Min required: {self.min_chars} chars, {self.min_words} words")
                raise Exception("Extracted content failed validation")

            extraction_time = time.time() - start_time

            logger.info(
                f"Extraction completed in {extraction_time:.2f}s: {url}",
                extra={
                    "url": url,
                    "duration": extraction_time,
                    "char_count": len(content),
                    "word_count": len(content.split()),
                }
            )

            # Save extracted content to a debug file for comparison
            import hashlib
            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
            debug_file = f"/tmp/extracted_content_{content_hash}.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(content.strip())
            logger.info(f"Saved extracted content to {debug_file} for debugging")

            return {
                "content": content.strip(),
                "title": None,  # Could be extracted from Gemini response if needed
                "url": str(url),
                "character_count": len(content.strip()),
                "estimated_words": len(content.strip().split()),
                "extraction_time": extraction_time,
                "strategy_used": "screenshot_gemini",
                "debug_file": debug_file  # Add debug file path
            }

        except Exception as e:
            logger.error(f"Failed to extract content from {url}: {e}")
            raise Exception(f"Web scraping failed: {e}") from e

    async def _capture_screenshots(self, url: str) -> list[bytes]:
        """
        Capture screenshot(s) of a webpage using Playwright.

        Args:
            url: The URL to capture

        Returns:
            List of screenshot bytes
        """
        screenshots = []

        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )

            try:
                # Create context with reasonable viewport
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (compatible; StorytimeTTS/1.0)"
                )

                page = await context.new_page()

                # Navigate to the page
                await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)

                # Wait a moment for initial content to render
                await page.wait_for_timeout(2000)

                # Scroll to load lazy-loaded content
                await self._scroll_page(page)

                # Always capture multiple viewport screenshots
                logger.debug("Capturing viewport screenshots")
                screenshots = await self._capture_viewport_screenshots(page)
                logger.info(f"Captured {len(screenshots)} viewport screenshots")

            finally:
                await browser.close()

        return screenshots

    async def _scroll_page(self, page: Page):
        """
        Scroll through the page to trigger lazy-loading of content.

        Args:
            page: Playwright page object
        """
        # Get initial scroll height
        scroll_height = await page.evaluate("document.body.scrollHeight")
        viewport_height = await page.evaluate("window.innerHeight")

        current_position = 0
        scroll_step = viewport_height * 0.8  # Scroll 80% of viewport at a time

        while current_position < scroll_height:
            # Scroll down
            await page.evaluate(f"window.scrollTo(0, {current_position})")
            await page.wait_for_timeout(500)  # Wait for content to load

            current_position += scroll_step

            # Check if page height has increased (new content loaded)
            new_scroll_height = await page.evaluate("document.body.scrollHeight")
            if new_scroll_height > scroll_height:
                scroll_height = new_scroll_height

        # Scroll back to top for screenshot
        await page.evaluate("window.scrollTo(0, 0)")
        await page.wait_for_timeout(500)

    async def _should_use_full_page(self, page: Page) -> bool:
        """
        Determine if we should use a single full-page screenshot or multiple viewports.

        Args:
            page: Playwright page object

        Returns:
            True if full-page screenshot is appropriate
        """
        scroll_height = await page.evaluate("document.body.scrollHeight")

        # NEVER use full-page screenshots - always use multiple viewport screenshots
        return False  # Always use multiple viewport screenshots

    async def _capture_viewport_screenshots(self, page: Page) -> list[bytes]:
        """
        Capture multiple viewport screenshots for very long pages.

        Args:
            page: Playwright page object

        Returns:
            List of screenshot bytes
        """
        screenshots = []
        scroll_height = await page.evaluate("document.body.scrollHeight")
        viewport_height = await page.evaluate("window.innerHeight")

        current_position = 0

        while current_position < scroll_height:
            # Scroll to position
            await page.evaluate(f"window.scrollTo(0, {current_position})")
            await page.wait_for_timeout(300)

            # Capture viewport
            screenshot = await page.screenshot()
            screenshots.append(screenshot)

            # Move to next viewport (minimal overlap - just 5% to ensure no gaps)
            current_position += int(viewport_height * 0.95)

        return screenshots

    async def _extract_text_from_screenshots(self, screenshots: list[bytes], url: str) -> str:
        """
        Extract text from screenshots using Gemini Flash with parallel processing.

        Args:
            screenshots: List of screenshot bytes
            url: The source URL (for context)

        Returns:
            Extracted text content
        """
        # Batch processing parameters
        BATCH_SIZE = 10  # Process 10 screenshots at a time to avoid Gemini limits
        MAX_CONCURRENT = 2  # Process up to 2 batches in parallel to avoid rate limits

        logger.info(f"Processing {len(screenshots)} screenshots in batches of {BATCH_SIZE} with {MAX_CONCURRENT} concurrent workers")

        # Split screenshots into batches
        batches = []
        for i in range(0, len(screenshots), BATCH_SIZE):
            batch = screenshots[i:i + BATCH_SIZE]
            batches.append((i // BATCH_SIZE + 1, batch))

        logger.info(f"Created {len(batches)} batches for parallel processing")

        # Create async function for processing a single batch
        async def process_batch(batch_num: int, batch_screenshots: list[bytes], total_batches: int) -> tuple[int, str]:
            """Process a single batch and return its number and extracted text."""
            logger.info(f"Starting batch {batch_num}/{total_batches} with {len(batch_screenshots)} screenshots")

            # Prepare the prompt for this batch
            if batch_num == 1:
                prompt = """
                Extract ALL text from these screenshots. This is the BEGINNING of a long article.

                CRITICAL: Extract EVERY SINGLE WORD you can see in the screenshots.
                - Start from the very first word in the first screenshot
                - Continue through every screenshot in order
                - Include the COMPLETE text from all screenshots
                - Do not summarize or truncate - I need the FULL TEXT
                - Preserve all paragraphs, quotes, and details
                - Skip only navigation menus and ads

                Return the complete text, nothing else.
                """
            elif batch_num == total_batches:
                prompt = """
                Extract ALL text from these screenshots. This is the END of a long article (continuation from previous batches).

                CRITICAL: Extract EVERY SINGLE WORD you can see in the screenshots.
                - Continue from where the previous batch left off
                - Include text through to the very end of the article
                - Do not summarize or truncate - I need the FULL TEXT
                - Preserve all paragraphs, quotes, and details
                - Skip only navigation menus and ads

                Return the complete text, nothing else.
                """
            else:
                prompt = f"""
                Extract ALL text from these screenshots. This is PART {batch_num} of a long article (continuation from previous batches).

                CRITICAL: Extract EVERY SINGLE WORD you can see in the screenshots.
                - Continue from where the previous batch left off
                - Continue through every screenshot in order
                - Do not summarize or truncate - I need the FULL TEXT
                - Preserve all paragraphs, quotes, and details
                - Skip only navigation menus and ads

                Return the complete text, nothing else.
                """

            # Build content list for Gemini
            contents = [prompt]

            # Add screenshots as image parts
            for screenshot in batch_screenshots:
                contents.append(
                    types.Part.from_bytes(
                        data=screenshot,
                        mime_type='image/png'
                    )
                )

            # Try up to 3 times with exponential backoff
            for attempt in range(3):
                try:
                    if attempt > 0:
                        wait_time = 2 ** attempt  # 2, 4 seconds
                        logger.info(f"Batch {batch_num} retry {attempt} after {wait_time}s delay")
                        await asyncio.sleep(wait_time)

                    # Call Gemini Flash for this batch
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=contents,
                    )

                    # Extract text from response
                    if response.text:
                        batch_text = response.text.strip()
                        logger.info(f"Batch {batch_num} completed: extracted {len(batch_text)} characters")
                        return (batch_num, batch_text)
                    else:
                        logger.warning(f"Batch {batch_num} returned empty response (attempt {attempt + 1}/3)")
                        if attempt == 2:  # Last attempt
                            return (batch_num, "")
                        continue

                except Exception as e:
                    logger.error(f"Batch {batch_num} extraction failed (attempt {attempt + 1}/3): {e}")
                    if attempt == 2:  # Last attempt
                        return (batch_num, "")
                    continue

        # Process batches in parallel with limited concurrency
        import asyncio
        results = []

        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)

        async def process_with_semaphore(batch_info):
            async with semaphore:
                batch_num, batch_screenshots = batch_info
                return await process_batch(batch_num, batch_screenshots, len(batches))

        # Process all batches in parallel
        tasks = [process_with_semaphore(batch_info) for batch_info in batches]
        results = await asyncio.gather(*tasks)

        # Sort results by batch number to maintain order
        results.sort(key=lambda x: x[0])

        # Extract just the text from results
        all_extracted_text = [text for _, text in results if text]

        # Combine all extracted text
        if not all_extracted_text:
            raise Exception("No text extracted from any batch")

        combined_text = "\n\n".join(all_extracted_text)
        logger.info(f"Combined {len(all_extracted_text)} batches into {len(combined_text)} total characters")

        return combined_text

    def _validate_extraction(self, content: str) -> bool:
        """
        Validate that the extracted content meets minimum requirements.

        Args:
            content: Extracted text content

        Returns:
            True if content is valid
        """
        if not content:
            return False

        char_count = len(content)
        word_count = len(content.split())

        if char_count < self.min_chars:
            logger.debug(f"Content too short: {char_count} chars (min: {self.min_chars})")
            return False

        if word_count < self.min_words:
            logger.debug(f"Too few words: {word_count} words (min: {self.min_words})")
            return False

        # Check for truncation indicators
        truncation_indicators = [
            "Subscribe to read more",
            "Sign up to continue",
            "Members only",
            "Premium content",
        ]

        content_lower = content.lower()
        for indicator in truncation_indicators:
            if indicator.lower() in content_lower[-500:]:  # Check last 500 chars
                logger.debug(f"Content appears truncated (found: {indicator})")
                return False

        return True

    def is_scraping_enabled(self) -> bool:
        """Check if web scraping is enabled via environment variable."""
        return os.getenv("SCRAPING_ENABLED", "true").lower() in ("true", "1", "yes")