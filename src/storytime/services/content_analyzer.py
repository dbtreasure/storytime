"""Content analysis service using Google Gemini for job type detection."""

import logging
from typing import Any

import google.generativeai as genai
from pydantic import BaseModel

from storytime.api.settings import get_settings
from storytime.models import JobType

logger = logging.getLogger(__name__)


class ContentAnalysisResult(BaseModel):
    """Structured output from Gemini content analysis."""

    job_type: str
    confidence: float
    reasoning: str
    estimated_chapters: int | None = None
    content_characteristics: list[str]


class ContentAnalyzer:
    """Service for analyzing content to determine optimal job type."""

    def __init__(self):
        """Initialize the content analysis service with Google Gemini."""
        settings = get_settings()

        if not settings.google_api_key:
            logger.warning("GOOGLE_API_KEY not set - content analysis will be disabled")
            self.client = None
            return

        # Configure Google Gemini API
        genai.configure(api_key=settings.google_api_key)

        # Initialize the model with structured output capability
        self.model = genai.GenerativeModel("gemini-2.5-pro")
        self.client = True
        logger.info("Gemini content analysis service initialized")

    async def analyze_content(self, content: str, title: str | None = None) -> JobType:
        """
        Analyze content to determine the appropriate job type.

        Args:
            content: The text content to analyze
            title: Optional title to help with analysis

        Returns:
            JobType enum value (TEXT_TO_AUDIO or BOOK_PROCESSING)
        """
        if not self.client:
            logger.warning("Gemini client not available, defaulting to TEXT_TO_AUDIO")
            return JobType.TEXT_TO_AUDIO

        if not content or len(content.strip()) < 100:
            logger.info("Content too short for analysis, defaulting to TEXT_TO_AUDIO")
            return JobType.TEXT_TO_AUDIO

        logger.info(f"Analyzing content for job type detection: {len(content)} characters")
        if title:
            logger.info(f"Content title: {title}")

        try:
            # Build the analysis prompt
            prompt = self._build_analysis_prompt(content, title)

            logger.info("Calling Gemini API for content analysis...")

            # Generate response from Gemini
            response = self.model.generate_content(prompt)

            if not response.text:
                logger.warning("Gemini returned empty response, defaulting to TEXT_TO_AUDIO")
                return JobType.TEXT_TO_AUDIO

            # Parse the structured response
            result = self._parse_analysis_result(response.text)

            logger.info(
                f"Content analysis completed: {result.job_type} "
                f"(confidence: {result.confidence:.2f}) - {result.reasoning}"
            )

            # Convert string result to JobType enum
            if result.job_type.lower() == "book_processing":
                return JobType.BOOK_PROCESSING
            else:
                return JobType.TEXT_TO_AUDIO

        except Exception as e:
            logger.error(f"Content analysis failed: {e}", exc_info=True)
            logger.info("Falling back to TEXT_TO_AUDIO job type")
            return JobType.TEXT_TO_AUDIO

    def _build_analysis_prompt(self, content: str, title: str | None) -> str:
        """Build the content analysis prompt for Gemini."""

        title_context = f"\n**Title:** {title}" if title else ""

        # Truncate content for analysis (first 3000 characters should be enough)
        analysis_content = content[:3000]
        if len(content) > 3000:
            analysis_content += "\n\n[Content truncated for analysis...]"

        prompt = f"""### ROLE AND OBJECTIVE
You are a content analysis expert specializing in determining optimal processing approaches for text-to-speech conversion. Your goal is to analyze content and determine whether it should be processed as a simple text-to-audio job or as a full book with chapter splitting.

### INSTRUCTIONS
Analyze the provided content and determine the appropriate job type based on these criteria:

**TEXT_TO_AUDIO (Simple Processing):**
- Short articles, blog posts, essays (typically under 10,000 words)
- Single-topic content without clear chapter structure
- News articles, reviews, documentation
- Content that reads better as a single continuous audio file
- Academic papers, research documents

**BOOK_PROCESSING (Chapter Splitting):**
- Full-length books with clear chapter divisions
- Long-form content with distinct sections/chapters (typically over 15,000 words)
- Content with "Chapter 1", "Chapter 2" or similar markers
- Multi-part stories or serialized content
- Textbooks with numbered sections
- Content that benefits from being split into manageable audio segments

### RESPONSE FORMAT
You must respond with a JSON object containing exactly these fields:
```json
{{
    "job_type": "text_to_audio" or "book_processing",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of your decision",
    "estimated_chapters": null or number (only if book_processing),
    "content_characteristics": ["list", "of", "key", "characteristics", "observed"]
}}
```

### CONTENT TO ANALYZE{title_context}

**Content Length:** {len(content):,} characters (~{len(content.split()):,} words)

**Content:**
```
{analysis_content}
```

Analyze this content and respond with the JSON structure above."""

        return prompt

    def _parse_analysis_result(self, response_text: str) -> ContentAnalysisResult:
        """Parse the structured response from Gemini."""
        import json

        try:
            # Try to extract JSON from the response
            response_text = response_text.strip()

            # Look for JSON block markers
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
            else:
                # Try to find JSON-like content
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end != 0:
                    json_text = response_text[start:end]
                else:
                    raise ValueError("No JSON structure found in response")

            # Parse the JSON
            result_data = json.loads(json_text)

            # Validate and create the result
            return ContentAnalysisResult(**result_data)

        except Exception as e:
            logger.warning(f"Failed to parse Gemini response as JSON: {e}")
            logger.debug(f"Raw response: {response_text[:500]}...")

            # Fallback analysis based on text content
            return self._fallback_analysis(response_text)

    def _fallback_analysis(self, response_text: str) -> ContentAnalysisResult:
        """Fallback analysis if JSON parsing fails."""

        # Simple keyword-based fallback
        lower_response = response_text.lower()

        if any(keyword in lower_response for keyword in ["book", "chapter", "long", "split"]):
            job_type = "book_processing"
            confidence = 0.6
            reasoning = "Fallback analysis detected book-like characteristics"
        else:
            job_type = "text_to_audio"
            confidence = 0.7
            reasoning = "Fallback analysis suggests simple text processing"

        return ContentAnalysisResult(
            job_type=job_type,
            confidence=confidence,
            reasoning=reasoning,
            content_characteristics=["fallback_analysis"],
        )

    def is_available(self) -> bool:
        """Check if the content analysis service is available."""
        return self.client is not None

    def get_status(self) -> dict[str, Any]:
        """Get the current status of the content analysis service."""
        return {
            "available": self.is_available(),
            "model": "gemini-2.5-pro" if self.is_available() else None,
            "google_api_configured": get_settings().google_api_key is not None,
        }
