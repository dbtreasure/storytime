"""Content analysis service for automatic job type detection and text processing."""

import asyncio
import json
import logging
import os
import re

import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from pydantic import BaseModel, Field

from storytime.models import ContentAnalysisResult, JobType, SourceType

logger = logging.getLogger(__name__)


class GeminiContentAnalysis(BaseModel):
    """Schema for Gemini's structured content analysis output."""

    # Core dialogue metrics
    has_dialogue: bool = Field(
        ..., description="Whether the text contains dialogue between characters"
    )
    dialogue_percentage: float = Field(
        ..., ge=0.0, le=1.0, description="Percentage of content that is dialogue (0.0 to 1.0)"
    )
    estimated_speakers: int = Field(
        ..., ge=0, description="Number of distinct speakers/characters detected"
    )
    identified_characters: list[str] = Field(
        default_factory=list, description="List of character names found in dialogue"
    )

    # Content structure
    has_chapter_structure: bool = Field(
        ..., description="Whether the text has clear chapter divisions"
    )
    chapter_count: int = Field(..., ge=0, description="Number of chapters detected")
    is_technical_content: bool = Field(
        ..., description="Whether this is technical documentation or code"
    )
    is_fiction: bool = Field(..., description="Whether this appears to be fictional narrative")

    # Job type recommendation
    recommended_job_type: str = Field(
        ...,
        description="Recommended processing type: SINGLE_VOICE, MULTI_VOICE, CHAPTER_PARSING, or BOOK_PROCESSING",
    )
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the recommendation (0.0 to 1.0)"
    )
    reasoning: list[str] = Field(
        default_factory=list, description="List of reasons for the recommendation"
    )

    # Additional insights
    narrative_complexity: str = Field(..., description="LOW, MEDIUM, or HIGH narrative complexity")
    primary_genre: str = Field(
        ..., description="Primary genre detected (fiction, non-fiction, technical, academic, etc.)"
    )


class ContentAnalyzer:
    """Service for analyzing content and determining appropriate processing strategies."""

    def __init__(self):
        # Initialize Gemini API
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY not set - falling back to regex-based analysis")
            self.use_gemini = False
        else:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel(
                    model_name=os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest"),
                    generation_config=GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.0,  # Consistent results
                    ),
                )
                self.use_gemini = True
                logger.info("Initialized Gemini for content analysis")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")
                self.use_gemini = False

        # Fallback patterns for when Gemini is unavailable
        self.dialogue_patterns = [
            r'"[^"]*"',  # Double quoted speech
            r"'[^']*'",  # Single quoted speech
            r'"[^"]*"',  # Smart quotes
            r"—[^—]*—",  # Em dash dialogue
        ]

        # Patterns for chapter detection
        self.chapter_patterns = [
            r"^chapter\s+\d+",
            r"^ch\.\s*\d+",
            r"^\d+\.",
            r"^[IVX]+\.",  # Roman numerals
        ]

        # Minimum lengths for different processing types
        self.single_voice_max_length = 5000  # Characters
        self.chapter_min_length = 1000  # Characters

    async def analyze_content(
        self, content: str, source_type: SourceType = SourceType.TEXT
    ) -> ContentAnalysisResult:
        """Analyze content and suggest appropriate job type."""
        logger.info(f"Analyzing content of length {len(content)} with source_type {source_type}")

        if self.use_gemini:
            try:
                # Use Gemini for intelligent content analysis
                analysis = await self._analyze_with_gemini(content, source_type)

                # Convert Gemini analysis to ContentAnalysisResult
                features = {
                    "length": str(len(content)),
                    "word_count": str(len(content.split())),
                    "has_dialogue": str(analysis.has_dialogue),
                    "dialogue_percentage": str(analysis.dialogue_percentage),
                    "estimated_speakers": str(analysis.estimated_speakers),
                    "identified_characters": json.dumps(analysis.identified_characters),
                    "has_chapter_structure": str(analysis.has_chapter_structure),
                    "chapter_count": str(analysis.chapter_count),
                    "is_technical_content": str(analysis.is_technical_content),
                    "is_fiction": str(analysis.is_fiction),
                    "narrative_complexity": analysis.narrative_complexity,
                    "primary_genre": analysis.primary_genre,
                }

                # Map Gemini's recommendation to JobType enum
                job_type = JobType(analysis.recommended_job_type)
                estimated_time = await self._estimate_processing_time(content, job_type)

                return ContentAnalysisResult(
                    suggested_job_type=job_type,
                    confidence=analysis.confidence_score,
                    reasons=analysis.reasoning,
                    detected_features=features,
                    estimated_processing_time=estimated_time,
                )

            except Exception as e:
                logger.error(f"Gemini analysis failed, falling back to regex: {e}")

        # Fallback to regex-based analysis
        features = await self._extract_features(content)
        suggested_type, confidence, reasons = await self._determine_job_type(features, source_type)
        estimated_time = await self._estimate_processing_time(content, suggested_type)

        return ContentAnalysisResult(
            suggested_job_type=suggested_type,
            confidence=confidence,
            reasons=reasons,
            detected_features=features,
            estimated_processing_time=estimated_time,
        )

    async def _analyze_with_gemini(
        self, content: str, source_type: SourceType
    ) -> GeminiContentAnalysis:
        """Use Gemini to analyze content with structured output."""
        # Sample content for efficiency (first 3000 chars)
        content_sample = content[:3000] if len(content) > 3000 else content

        prompt = f"""Analyze this text content and provide a detailed analysis to determine the best processing approach for audiobook generation.

IMPORTANT: You must respond with valid JSON matching this exact schema:
{{
    "has_dialogue": boolean,
    "dialogue_percentage": number (0.0 to 1.0),
    "estimated_speakers": integer,
    "identified_characters": array of strings,
    "has_chapter_structure": boolean,
    "chapter_count": integer,
    "is_technical_content": boolean,
    "is_fiction": boolean,
    "recommended_job_type": string (one of: SINGLE_VOICE, MULTI_VOICE, CHAPTER_PARSING, BOOK_PROCESSING),
    "confidence_score": number (0.0 to 1.0),
    "reasoning": array of strings,
    "narrative_complexity": string (one of: LOW, MEDIUM, HIGH),
    "primary_genre": string
}}

Analysis criteria:
1. Dialogue Detection: Look for quoted speech, dialogue tags (said, asked, replied), and conversational patterns
2. Character Identification: Find character names mentioned in dialogue attribution
3. Content Structure: Detect chapter markers, sections, or natural divisions
4. Genre Detection: Identify if it's fiction, non-fiction, technical documentation, academic text, etc.

Job type recommendations:
- SINGLE_VOICE: For content with no dialogue, technical docs, or single narrator
  (news articles, documentation, essays)
- MULTI_VOICE: For content with multiple characters speaking
  (fiction with dialogue, plays, interviews)
- CHAPTER_PARSING: For analyzing chapter structure only (when just parsing is needed)
- BOOK_PROCESSING: For full books/novels with multiple chapters that need to be split first
  (content >10,000 words with chapter structure)

Source type context: {source_type.value}
Total content length: {len(content)} characters

Content to analyze:
{content_sample}"""

        try:
            # Run Gemini API call in executor to avoid blocking
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: self.model.generate_content(prompt))

            # Parse JSON response
            response_text = response.text.strip()

            # Clean up common JSON issues from LLMs
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Parse and validate with Pydantic
            analysis_data = json.loads(response_text)
            return GeminiContentAnalysis(**analysis_data)

        except Exception as e:
            logger.error(f"Error in Gemini analysis: {e}")
            # Return a sensible default based on basic heuristics
            has_quotes = bool(re.search(r'[""].*?[""]', content_sample))

            return GeminiContentAnalysis(
                has_dialogue=has_quotes,
                dialogue_percentage=0.1 if has_quotes else 0.0,
                estimated_speakers=2 if has_quotes else 1,
                identified_characters=[],
                has_chapter_structure=bool(
                    re.search(r"chapter\s+\d+", content_sample, re.IGNORECASE)
                ),
                chapter_count=0,
                is_technical_content=bool(
                    re.search(r"```|def\s+|class\s+|function\s+", content_sample)
                ),
                is_fiction=has_quotes
                and not bool(re.search(r"```|def\s+|class\s+", content_sample)),
                recommended_job_type=(
                    JobType.MULTI_VOICE.value if has_quotes else JobType.SINGLE_VOICE.value
                ),
                confidence_score=0.5,
                reasoning=["Fallback analysis due to Gemini error"],
                narrative_complexity="MEDIUM",
                primary_genre="unknown",
            )

    async def split_book_into_chapters(self, content: str) -> list[str]:
        """Split book content into individual chapters."""
        logger.info(f"Splitting book content of length {len(content)} into chapters")

        chapters = []

        # Try to find chapter boundaries
        chapter_boundaries = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            line_clean = line.strip().lower()

            # Check if line matches chapter pattern
            for pattern in self.chapter_patterns:
                if re.match(pattern, line_clean):
                    chapter_boundaries.append(i)
                    break

        if not chapter_boundaries:
            # No clear chapter structure found, split by length
            logger.info("No chapter structure detected, splitting by length")
            return await self._split_by_length(content)

        # Split content at chapter boundaries
        for i, start_line in enumerate(chapter_boundaries):
            end_line = chapter_boundaries[i + 1] if i + 1 < len(chapter_boundaries) else len(lines)

            chapter_lines = lines[start_line:end_line]
            chapter_content = "\n".join(chapter_lines).strip()

            if len(chapter_content) > self.chapter_min_length:
                chapters.append(chapter_content)
            elif chapters:  # Append to previous chapter if too short
                chapters[-1] += "\n\n" + chapter_content

        logger.info(f"Split content into {len(chapters)} chapters")
        return chapters

    async def _extract_features(self, content: str) -> dict[str, str]:
        """Extract features from content for analysis."""
        features = {}

        # Basic metrics
        features["length"] = str(len(content))
        features["word_count"] = str(len(content.split()))
        features["line_count"] = str(len(content.split("\n")))
        features["paragraph_count"] = str(len([p for p in content.split("\n\n") if p.strip()]))

        # Dialogue detection
        dialogue_matches = 0
        for pattern in self.dialogue_patterns:
            dialogue_matches += len(re.findall(pattern, content))

        features["dialogue_count"] = str(dialogue_matches)
        features["dialogue_ratio"] = str(round(dialogue_matches / max(1, len(content.split())), 3))

        # Character name patterns (simple heuristic)
        # Look for capitalized words that might be character names
        capitalized_words = re.findall(r"\b[A-Z][a-z]+\b", content)
        unique_caps = set(capitalized_words)
        features["potential_character_count"] = str(len(unique_caps))

        # Chapter detection
        chapter_indicators = 0
        for pattern in self.chapter_patterns:
            chapter_indicators += len(re.findall(pattern, content, re.IGNORECASE | re.MULTILINE))

        features["chapter_indicators"] = str(chapter_indicators)

        # Document structure indicators
        features["has_table_of_contents"] = str(
            bool(re.search(r"table\s+of\s+contents|contents", content, re.IGNORECASE))
        )
        features["has_title_page"] = str(
            bool(re.search(r"^\s*[A-Z\s]{10,}\s*$", content, re.MULTILINE))
        )

        # Technical content detection
        features["has_code_blocks"] = str(
            bool(re.search(r"```|<code>|def\s+\w+|class\s+\w+", content))
        )
        features["has_markdown"] = str(
            bool(re.search(r"#{1,6}\s|^\*\s|\[.*\]\(.*\)", content, re.MULTILINE))
        )

        return features

    async def _determine_job_type(
        self, features: dict[str, str], source_type: SourceType
    ) -> tuple[JobType, float, list[str]]:
        """Determine appropriate job type based on features."""
        reasons = []
        confidence = 0.5  # Base confidence

        length = int(features.get("length", "0"))
        dialogue_count = int(features.get("dialogue_count", "0"))
        dialogue_ratio = float(features.get("dialogue_ratio", "0"))
        chapter_indicators = int(features.get("chapter_indicators", "0"))
        potential_characters = int(features.get("potential_character_count", "0"))

        # Simple content -> SINGLE_VOICE
        if length <= self.single_voice_max_length:
            reasons.append(f"Short content ({length} chars) suitable for single voice")
            confidence += 0.3
            return JobType.SINGLE_VOICE, min(confidence, 0.95), reasons

        # Book with chapters -> BOOK_PROCESSING
        if chapter_indicators > 1 and source_type == SourceType.BOOK:
            reasons.append(f"Detected {chapter_indicators} chapter indicators")
            confidence += 0.4
            return JobType.BOOK_PROCESSING, min(confidence, 0.95), reasons

        # High dialogue content -> MULTI_VOICE
        if dialogue_count > 10 and dialogue_ratio > 0.1:
            reasons.append(
                f"High dialogue content ({dialogue_count} instances, {dialogue_ratio:.1%} ratio)"
            )
            confidence += 0.3

        if potential_characters > 5:
            reasons.append(f"Multiple potential characters detected ({potential_characters})")
            confidence += 0.2

        # Technical content usually stays single voice
        if features.get("has_code_blocks") == "True" or features.get("has_markdown") == "True":
            reasons.append("Technical content detected, using single voice")
            return JobType.SINGLE_VOICE, min(confidence + 0.2, 0.9), reasons

        # Default decision based on dialogue content
        if dialogue_count > 5 or dialogue_ratio > 0.05:
            reasons.append("Sufficient dialogue detected for multi-voice processing")
            return JobType.MULTI_VOICE, min(confidence, 0.85), reasons
        else:
            reasons.append("Limited dialogue, using single voice")
            return JobType.SINGLE_VOICE, min(confidence, 0.8), reasons

    async def _estimate_processing_time(self, content: str, job_type: JobType) -> int:
        """Estimate processing time in seconds based on content and job type."""
        word_count = len(content.split())

        # Base time estimates (seconds per word)
        time_per_word = {
            JobType.SINGLE_VOICE: 0.1,  # ~6 words per second
            JobType.MULTI_VOICE: 0.3,  # ~3 words per second (more complex)
            JobType.CHAPTER_PARSING: 0.05,  # ~20 words per second (parsing only)
            JobType.BOOK_PROCESSING: 0.4,  # ~2.5 words per second (most complex)
        }

        base_time = word_count * time_per_word.get(job_type, 0.2)

        # Add overhead for setup and finalization
        overhead = {
            JobType.SINGLE_VOICE: 30,  # 30 seconds
            JobType.MULTI_VOICE: 120,  # 2 minutes
            JobType.CHAPTER_PARSING: 60,  # 1 minute
            JobType.BOOK_PROCESSING: 300,  # 5 minutes
        }

        total_time = int(base_time + overhead.get(job_type, 60))

        # Minimum processing time
        return max(total_time, 10)

    async def _split_by_length(self, content: str, max_chunk_size: int = 50000) -> list[str]:
        """Split content by length when no clear structure is found."""
        chunks = []

        # Try to split at paragraph boundaries first
        paragraphs = content.split("\n\n")
        current_chunk = ""

        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) <= max_chunk_size:
                current_chunk += paragraph + "\n\n"
            else:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + "\n\n"

        # Add final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # If still too large, split at sentence boundaries
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= max_chunk_size:
                final_chunks.append(chunk)
            else:
                # Split large chunks at sentence boundaries
                sentences = re.split(r"[.!?]+\s+", chunk)
                current_subchunk = ""

                for sentence in sentences:
                    if len(current_subchunk) + len(sentence) <= max_chunk_size:
                        current_subchunk += sentence + ". "
                    else:
                        if current_subchunk.strip():
                            final_chunks.append(current_subchunk.strip())
                        current_subchunk = sentence + ". "

                if current_subchunk.strip():
                    final_chunks.append(current_subchunk.strip())

        return final_chunks
