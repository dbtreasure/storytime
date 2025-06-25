"""Text preprocessing service using Google Gemini for TTS content cleanup."""

import logging
from typing import Any

import google.generativeai as genai

from storytime.api.settings import get_settings

logger = logging.getLogger(__name__)


class PreprocessingService:
    """Service for preprocessing text content using Google Gemini before TTS conversion."""

    def __init__(self):
        """Initialize the preprocessing service with Google Gemini."""
        settings = get_settings()

        if not settings.google_api_key:
            logger.warning("GOOGLE_API_KEY not set - preprocessing will be skipped")
            self.client = None
            return

        # Configure Google Gemini API
        genai.configure(api_key=settings.google_api_key)

        # Initialize the model (using Gemini 2.5 Pro for best performance)
        self.model = genai.GenerativeModel("gemini-2.5-pro")
        self.client = True
        logger.info("Gemini preprocessing service initialized")

    async def preprocess_text(
        self, text_content: str, job_config: dict[str, Any] | None = None
    ) -> str:
        """
        Preprocess text content to remove metadata and formatting artifacts.

        Args:
            text_content: The raw text content to preprocess
            job_config: Optional job configuration with preprocessing settings

        Returns:
            Cleaned text content ready for TTS conversion

        Raises:
            Exception: If preprocessing fails (falls back to original text)
        """
        if not self.client:
            logger.warning("Gemini client not available, returning original text")
            return text_content

        # Check if preprocessing is enabled for this job
        preprocessing_config = {}
        if job_config:
            preprocessing_config = job_config.get("preprocessing", {})

        if not preprocessing_config.get("enabled", True):
            logger.info("Preprocessing disabled for this job")
            return text_content

        logger.info(f"Starting text preprocessing, input length: {len(text_content)} characters")
        logger.info(f"First 200 chars of input: {text_content[:200]}...")

        try:
            # Build the preprocessing prompt
            prompt = self._build_preprocessing_prompt(text_content, preprocessing_config)

            logger.info("Calling Gemini API for text preprocessing...")

            # Generate response from Gemini
            response = self.model.generate_content(prompt)

            if not response.text:
                logger.warning("Gemini returned empty response, using original text")
                return text_content

            cleaned_text = response.text.strip()

            logger.info(
                f"Text preprocessing completed successfully: "
                f"{len(text_content)} -> {len(cleaned_text)} characters "
                f"(removed {len(text_content) - len(cleaned_text)} chars, {((len(text_content) - len(cleaned_text)) / len(text_content) * 100):.1f}%)"
            )
            logger.info(f"First 200 chars of output: {cleaned_text[:200]}...")

            return cleaned_text

        except Exception as e:
            logger.error(f"Text preprocessing failed: {e}", exc_info=True)
            logger.info("Falling back to original text content")
            return text_content

    def _build_preprocessing_prompt(self, text_content: str, config: dict[str, Any]) -> str:
        """Build the preprocessing prompt for Gemini."""

        # Extract configuration options
        preserve_structure = config.get("preserve_structure", True)
        aggressive_cleanup = config.get("aggressive_cleanup", False)

        # Build the prompt following best practices
        prompt = """### ROLE AND OBJECTIVE
You are a professional text editor specializing in preparing literary content for audiobook production. Your goal is to clean and optimize text while preserving the author's original intent and narrative flow.

### INSTRUCTIONS / RESPONSE RULES
- ALWAYS preserve the core literary content and author's voice
- REMOVE publication metadata, copyright notices, and publisher information
- REMOVE table of contents, index, and navigation elements
- REMOVE footnote markers and academic citations (but preserve essential footnote content inline if critical to understanding)
- REMOVE repetitive headers/footers and page numbers
- CLEAN UP formatting artifacts like excessive whitespace, random characters, or OCR errors
- PRESERVE chapter titles, section breaks, and narrative structure
- PRESERVE dialogue, character names, and essential story elements
- DO NOT summarize, paraphrase, or change the author's original words
- DO NOT remove legitimate literary content like epigraphs, dedications, or author's notes that are part of the work"""

        if preserve_structure:
            prompt += "\n- MAINTAIN the original chapter structure and literary formatting"

        if aggressive_cleanup:
            prompt += (
                "\n- BE MORE AGGRESSIVE in removing potentially irrelevant metadata and formatting"
            )

        prompt += f"""

### CONTEXT
This text will be converted to audio for audiobook production. Listeners should hear only the literary content, not publishing metadata or formatting artifacts.

### REASONING STEPS
Think step by step:
1. Identify what type of content this is (novel, non-fiction, etc.)
2. Scan for publication metadata and formatting artifacts
3. Preserve the literary structure while removing non-literary elements
4. Ensure the cleaned text flows naturally for audio narration

### OUTPUT FORMATTING CONSTRAINTS
Return only the cleaned text content. Do not add explanations, summaries, or metadata about your changes.

### TEXT TO PROCESS
```
{text_content}
```"""

        return prompt

    def is_available(self) -> bool:
        """Check if the preprocessing service is available."""
        return self.client is not None

    def get_status(self) -> dict[str, Any]:
        """Get the current status of the preprocessing service."""
        return {
            "available": self.is_available(),
            "model": "gemini-2.5-pro" if self.is_available() else None,
            "google_api_configured": get_settings().google_api_key is not None,
        }
