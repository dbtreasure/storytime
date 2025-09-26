"""Content analysis service using Google Gemini for job type detection."""

import logging
from typing import Any

from google import genai
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


class TutoringAnalysisResult(BaseModel):
    """Basic tutoring analysis for uploaded content."""

    themes: list[str]
    characters: list[dict[str, str]]  # [{"name": "...", "role": "..."}]
    setting: dict[str, str]  # {"time": "...", "place": "..."}
    discussion_questions: list[str]
    content_type: str  # "fiction", "non-fiction", "academic", etc.


class OpeningLectureResult(BaseModel):
    """Opening lecture content for tutor sessions."""

    introduction: str  # Opening hook and context setting
    key_concepts_overview: str  # Brief overview of main concepts
    learning_objectives: str  # What students will explore
    engagement_questions: list[str]  # Questions to get students thinking
    lecture_duration_minutes: int  # Estimated duration
    extension_topics: list[str]  # Topics for deeper exploration if requested


class ContentAnalyzer:
    """Service for analyzing content to determine optimal job type."""

    def __init__(self):
        """Initialize the content analysis service with Google Gemini."""
        settings = get_settings()

        if not settings.google_api_key:
            logger.warning("GOOGLE_API_KEY not set - content analysis will be disabled")
            self.client = None
            return

        # Initialize Google Gemini client
        self.client = genai.Client(api_key=settings.google_api_key)
        self.model_name = "gemini-2.0-flash-exp"  # Using Flash for faster response
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
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )

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

    async def analyze_for_tutoring(
        self, content: str, title: str | None = None
    ) -> TutoringAnalysisResult:
        """
        Analyze content for tutoring capabilities.

        Simple grug-brain version that extracts basic info for tutoring conversations.

        Args:
            content: The text content to analyze
            title: Optional title to help with analysis

        Returns:
            TutoringAnalysisResult with themes, characters, setting, and discussion questions
        """
        if not self.client:
            logger.warning("Gemini client not available, returning basic tutoring analysis")
            return TutoringAnalysisResult(
                themes=["learning", "education"],
                characters=[],
                setting={"time": "unknown", "place": "unknown"},
                discussion_questions=["What are the main ideas in this content?"],
                content_type="unknown",
            )

        if not content or len(content.strip()) < 100:
            logger.info("Content too short for tutoring analysis")
            return TutoringAnalysisResult(
                themes=["short content"],
                characters=[],
                setting={"time": "present", "place": "unspecified"},
                discussion_questions=["What can you learn from this content?"],
                content_type="short-form",
            )

        logger.info(f"Analyzing content for tutoring: {len(content)} characters")

        try:
            prompt = self._build_tutoring_prompt(content, title)
            response = self.model.generate_content(prompt)

            if not response.text:
                logger.warning("Gemini returned empty response for tutoring analysis")
                return self._fallback_tutoring_analysis()

            result = self._parse_tutoring_result(response.text)
            logger.info(
                f"Tutoring analysis completed: {len(result.themes)} themes, {len(result.characters)} characters"
            )
            return result

        except Exception as e:
            logger.error(f"Tutoring analysis failed: {e}", exc_info=True)
            return self._fallback_tutoring_analysis()

    def _build_tutoring_prompt(self, content: str, title: str | None) -> str:
        """Build tutoring analysis prompt for Gemini."""

        title_context = f"\n**Title:** {title}" if title else ""

        # Use first 4000 characters for tutoring analysis
        analysis_content = content[:4000]
        if len(content) > 4000:
            analysis_content += "\n\n[Content truncated for analysis...]"

        prompt = f"""### ROLE
You are an expert tutor and content analyst. Your job is to analyze content and extract key information needed for tutoring conversations.

### TASK
Analyze the provided content and extract tutoring-relevant information. Focus on creating a foundation for Socratic dialogue and engaged learning.

### RESPONSE FORMAT
Respond with a JSON object containing exactly these fields:
```json
{{
    "themes": ["list of 3-5 main themes or concepts"],
    "characters": [{{"name": "Character Name", "role": "brief description"}}],
    "setting": {{"time": "time period", "place": "location/setting"}},
    "discussion_questions": ["list of 3-5 thought-provoking questions for Socratic dialogue"],
    "content_type": "fiction|non-fiction|academic|poetry|biography|history|science|philosophy|etc"
}}
```

### GUIDELINES
- **Themes**: Extract core concepts, ideas, or topics (not just plot points)
- **Characters**: For fiction, list main characters. For non-fiction, list key figures/people mentioned
- **Setting**: Time period and place. For non-fiction, consider historical/intellectual context
- **Discussion Questions**: Create open-ended questions that promote deep thinking and analysis
- **Content Type**: Categorize to help tailor tutoring approach

### CONTENT TO ANALYZE{title_context}

**Content Length:** {len(content):,} characters

**Content:**
```
{analysis_content}
```

Provide the JSON analysis:"""

        return prompt

    def _parse_tutoring_result(self, response_text: str) -> TutoringAnalysisResult:
        """Parse tutoring analysis response from Gemini."""
        import json

        try:
            # Extract JSON from response
            response_text = response_text.strip()

            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
            else:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end != 0:
                    json_text = response_text[start:end]
                else:
                    raise ValueError("No JSON structure found")

            result_data = json.loads(json_text)
            return TutoringAnalysisResult(**result_data)

        except Exception as e:
            logger.warning(f"Failed to parse tutoring analysis JSON: {e}")
            return self._fallback_tutoring_analysis()

    def _fallback_tutoring_analysis(self) -> TutoringAnalysisResult:
        """Fallback tutoring analysis if parsing fails."""
        return TutoringAnalysisResult(
            themes=["main concepts", "key ideas", "important topics"],
            characters=[{"name": "Content", "role": "main subject"}],
            setting={"time": "contemporary", "place": "general"},
            discussion_questions=[
                "What are the main ideas presented in this content?",
                "How does this relate to your existing knowledge?",
                "What questions does this content raise for you?",
            ],
            content_type="general",
        )

    async def analyze_for_opening_lecture(
        self,
        content: str,
        title: str | None = None,
        tutoring_analysis: TutoringAnalysisResult | None = None,
    ) -> OpeningLectureResult:
        """
        Generate opening lecture content for tutor sessions.

        Creates a 2-3 minute opening lecture that introduces the content and sets up
        Socratic dialogue. Uses tutoring analysis if available for richer context.

        Args:
            content: The text content to analyze
            title: Optional title to help with analysis
            tutoring_analysis: Previous tutoring analysis results for context

        Returns:
            OpeningLectureResult with structured lecture content
        """
        if not self.client:
            logger.warning("Gemini client not available, returning basic opening lecture")
            return self._fallback_opening_lecture(title)

        if not content or len(content.strip()) < 100:
            logger.info("Content too short for opening lecture generation")
            return self._fallback_opening_lecture(title)

        logger.info(f"Generating opening lecture for content: {len(content)} characters")

        try:
            prompt = self._build_opening_lecture_prompt(content, title, tutoring_analysis)
            response = self.model.generate_content(prompt)

            if not response.text:
                logger.warning("Gemini returned empty response for opening lecture")
                return self._fallback_opening_lecture(title)

            result = self._parse_opening_lecture_result(response.text)
            logger.info(
                f"Opening lecture generated: {result.lecture_duration_minutes} minutes, {len(result.engagement_questions)} questions"
            )
            return result

        except Exception as e:
            logger.error(f"Opening lecture generation failed: {e}", exc_info=True)
            return self._fallback_opening_lecture(title)

    def _build_opening_lecture_prompt(
        self, content: str, title: str | None, tutoring_analysis: TutoringAnalysisResult | None
    ) -> str:
        """Build opening lecture generation prompt following structured guidelines."""

        # Prepare context sections
        title_context = f"\n**Title:** {title}" if title else ""

        tutoring_context = ""
        if tutoring_analysis:
            tutoring_context = f"""
**Available Context from Prior Analysis:**
- Themes: {", ".join(tutoring_analysis.themes)}
- Content Type: {tutoring_analysis.content_type}
- Key Characters: {len(tutoring_analysis.characters)} identified
- Setting: {tutoring_analysis.setting.get("time", "unknown")} / {tutoring_analysis.setting.get("place", "unknown")}
"""

        # Use first 3000 characters for lecture generation
        analysis_content = content[:3000]
        if len(content) > 3000:
            analysis_content += "\n\n[Content truncated for analysis...]"

        prompt = f"""### ROLE AND OBJECTIVE
You are an expert educational content designer and tutor. Your goal is to create an engaging 2-3 minute opening lecture that introduces content to students and prepares them for Socratic dialogue.

### INSTRUCTIONS / RESPONSE RULES
- Create a warm, welcoming introduction that hooks student interest
- Provide a clear overview of key concepts without spoiling details
- Set learning expectations and objectives
- Generate 3-4 engagement questions to prime student thinking
- Keep the tone conversational and accessible
- Aim for 2-3 minutes of speaking time (approximately 300-450 words)
- DO NOT include detailed analysis or answers - focus on setting up curiosity
- DO NOT spoil plot points or key revelations if this is narrative content

### CONTEXT{title_context}
**Content Length:** {len(content):,} characters{tutoring_context}

**Content to Introduce:**
```
{analysis_content}
```

### EXAMPLES
Example JSON response structure:
```json
{{
    "introduction": "Welcome! Today we're diving into fascinating content that explores...",
    "key_concepts_overview": "We'll be examining three main areas: first, the concept of...",
    "learning_objectives": "By the end of our discussion, you'll be able to...",
    "engagement_questions": ["What do you already know about...?", "How might this relate to...?"],
    "lecture_duration_minutes": 3,
    "extension_topics": ["Advanced concept A", "Historical context B"]
}}
```

### REASONING STEPS
Think step by step:
1. Identify the most compelling hook from the content
2. Determine 2-3 core concepts that are accessible entry points
3. Consider what learning outcomes are realistic for a tutoring session
4. Craft questions that activate prior knowledge and curiosity
5. Identify natural extension points for deeper exploration

### OUTPUT FORMATTING CONSTRAINTS
Respond with a JSON object containing exactly these fields:
```json
{{
    "introduction": "string - warm, engaging opening that hooks interest (100-150 words)",
    "key_concepts_overview": "string - brief overview of main concepts to explore (100-150 words)", 
    "learning_objectives": "string - what students will gain from the session (50-100 words)",
    "engagement_questions": ["array of 3-4 open-ended questions to prime thinking"],
    "lecture_duration_minutes": "integer - estimated speaking time (2-4 minutes)",
    "extension_topics": ["array of 2-4 topics for deeper exploration if requested"]
}}
```

### CONTENT ANALYSIS
Generate the opening lecture JSON:"""

        return prompt

    def _parse_opening_lecture_result(self, response_text: str) -> OpeningLectureResult:
        """Parse opening lecture response from Gemini."""
        import json

        try:
            # Extract JSON from response
            response_text = response_text.strip()

            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                json_text = response_text[start:end].strip()
            else:
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start != -1 and end != 0:
                    json_text = response_text[start:end]
                else:
                    raise ValueError("No JSON structure found")

            result_data = json.loads(json_text)
            return OpeningLectureResult(**result_data)

        except Exception as e:
            logger.warning(f"Failed to parse opening lecture JSON: {e}")
            return self._fallback_opening_lecture()

    def _fallback_opening_lecture(self, title: str | None = None) -> OpeningLectureResult:
        """Fallback opening lecture if generation fails."""
        content_ref = f" '{title}'" if title else ""

        return OpeningLectureResult(
            introduction=f"Welcome to our tutoring session! Today we'll be exploring the content{content_ref} together. This material offers rich opportunities for discussion and deeper understanding. Let's embark on this learning journey with curiosity and open minds.",
            key_concepts_overview="We'll examine the main themes and ideas presented in this content, considering different perspectives and interpretations. Our discussion will focus on understanding the key concepts and how they connect to broader knowledge.",
            learning_objectives="Through our Socratic dialogue, you'll develop critical thinking skills, deepen your understanding of the material, and discover new connections and insights.",
            engagement_questions=[
                "What are your initial thoughts about this content?",
                "What questions does this material raise for you?",
                "How might this relate to what you already know?",
            ],
            lecture_duration_minutes=2,
            extension_topics=[
                "Critical analysis",
                "Historical context",
                "Contemporary relevance",
                "Personal connections",
            ],
        )
