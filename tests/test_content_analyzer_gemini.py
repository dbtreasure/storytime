"""Tests for Gemini-based content analyzer - CORE-52."""

import os
from unittest.mock import MagicMock, patch

import pytest

from storytime.models import JobType, SourceType
from storytime.services.content_analyzer import ContentAnalyzer


class TestGeminiContentAnalyzer:
    """Tests for the Gemini-based content analyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create a content analyzer instance."""
        return ContentAnalyzer()

    @pytest.mark.asyncio
    async def test_core52_dialogue_detection(self, analyzer):
        """Test the specific case from CORE-52 where dialogue wasn't detected."""
        content = """Chapter 1: The Meeting

The wind howled through the trees as Emma approached the old cottage.

"Hello?" called Emma. "Is anyone there?"

From inside came a gruff voice: "Who disturbs my peace?" growled the hermit.

"I am Emma," she replied gently. "I need your help."

The hermit opened the door slowly. "What kind of help?" he asked suspiciously.

"My village is in danger," Emma explained. "We need your wisdom."

The hermit studied her face carefully before nodding."""

        result = await analyzer.analyze_content(content, SourceType.TEXT)

        # With Gemini, this should now correctly detect as MULTI_VOICE
        assert result.suggested_job_type == JobType.MULTI_VOICE
        assert result.confidence > 0.7

        # Check features detected
        features = result.detected_features
        assert features.get("has_dialogue") == "True"
        assert float(features.get("dialogue_percentage", 0)) > 0.3
        assert int(features.get("estimated_speakers", 0)) >= 2

        # Should identify Emma and hermit as characters
        if "identified_characters" in features:
            import json

            characters = json.loads(features["identified_characters"])
            assert "Emma" in characters or any("Emma" in c for c in characters)

    @pytest.mark.asyncio
    async def test_technical_content_detection(self, analyzer):
        """Test detection of technical content."""
        content = """# Python Tutorial

Here's how to define a function in Python:

```python
def hello_world():
    print("Hello, World!")
    return True
```

This function prints a message and returns True. You can call it like this:

```python
result = hello_world()
```

Classes are defined using the `class` keyword."""

        result = await analyzer.analyze_content(content, SourceType.TEXT)

        assert result.suggested_job_type == JobType.SINGLE_VOICE
        assert result.confidence > 0.7
        features = result.detected_features
        assert features.get("is_technical_content") == "True"
        assert features.get("has_dialogue") == "False"

    @pytest.mark.asyncio
    async def test_book_with_chapters_detection(self, analyzer):
        """Test detection of book structure with chapters."""
        # Make content longer and more book-like to trigger BOOK_PROCESSING
        chapter_content = (
            """
        The protagonist walked through the ancient forest, contemplating the journey ahead. 
        Years had passed since the last great adventure, and the world had changed significantly.
        The trees whispered secrets of old, telling tales of heroes who had come before.
        
        As the sun set behind the mountains, casting long shadows across the path, 
        our hero knew that tomorrow would bring new challenges and opportunities.
        The village elders had spoken of an ancient prophecy that would soon unfold.
        
        Each step forward was a step into the unknown, but also a step toward destiny.
        The weight of responsibility rested heavily on the protagonist's shoulders,
        yet there was also a sense of excitement about what lay ahead.
        """
            * 3
        )  # Make it substantial

        content = f"""Table of Contents

Chapter 1: The Beginning
Chapter 2: The Journey  
Chapter 3: The Middle Path
Chapter 4: The Trial
Chapter 5: The Return

Chapter 1: The Beginning
{chapter_content}

Chapter 2: The Journey
{chapter_content}

Chapter 3: The Middle Path
{chapter_content}

Chapter 4: The Trial
{chapter_content}

Chapter 5: The Return
{chapter_content}"""

        result = await analyzer.analyze_content(content, SourceType.BOOK)

        # Should detect as book processing due to length and chapter structure
        assert result.suggested_job_type in [JobType.BOOK_PROCESSING, JobType.MULTI_VOICE]
        assert result.confidence > 0.6
        features = result.detected_features
        assert features.get("has_chapter_structure") == "True"
        assert int(features.get("chapter_count", 0)) >= 3

    @pytest.mark.asyncio
    async def test_mixed_dialogue_narration(self, analyzer):
        """Test content with mixed dialogue and narration."""
        content = """The detective entered the room and looked around carefully.

"What happened here?" Detective Smith asked, surveying the scene.

Officer Johnson stepped forward. "We got the call about an hour ago," he explained. "The neighbor heard a loud crash."

Smith nodded thoughtfully. "Any witnesses?"

"Just the neighbor, Mrs. Chen," Johnson replied. "She's waiting outside."

The detective made notes in his pad, then walked over to examine the broken window. The glass was scattered inward, suggesting forced entry from outside.

"Get forensics in here," Smith ordered. "And bring Mrs. Chen in for questioning."

"Right away, sir," Johnson said, already reaching for his radio."""

        result = await analyzer.analyze_content(content, SourceType.TEXT)

        assert result.suggested_job_type == JobType.MULTI_VOICE
        assert result.confidence > 0.7
        features = result.detected_features
        assert features.get("has_dialogue") == "True"
        assert float(features.get("dialogue_percentage", 0)) > 0.3
        assert int(features.get("estimated_speakers", 0)) >= 2

        # Should identify the detective and officer
        if "identified_characters" in features:
            import json

            characters = json.loads(features["identified_characters"])
            assert len(characters) >= 2

    @pytest.mark.asyncio
    async def test_fallback_when_gemini_unavailable(self, analyzer):
        """Test that fallback logic works when Gemini is unavailable."""
        # Temporarily disable Gemini
        original_use_gemini = analyzer.use_gemini
        analyzer.use_gemini = False

        try:
            content = '"Hello," said Bob. "How are you?"'
            result = await analyzer.analyze_content(content, SourceType.TEXT)

            # Should still work with regex fallback
            assert result.suggested_job_type in [JobType.SINGLE_VOICE, JobType.MULTI_VOICE]
            assert result.confidence >= 0.5
            assert len(result.reasons) > 0

        finally:
            analyzer.use_gemini = original_use_gemini

    @pytest.mark.asyncio
    async def test_gemini_error_handling(self, analyzer):
        """Test error handling when Gemini returns invalid JSON."""
        if not analyzer.use_gemini:
            pytest.skip("Gemini not configured")

        # Mock the model to return invalid JSON
        with patch.object(analyzer.model, "generate_content") as mock_generate:
            mock_response = MagicMock()
            mock_response.text = "This is not valid JSON"
            mock_generate.return_value = mock_response

            content = '"Hello," said Alice.'
            result = await analyzer.analyze_content(content, SourceType.TEXT)

            # Should fall back gracefully
            assert result.suggested_job_type in [JobType.SINGLE_VOICE, JobType.MULTI_VOICE]
            assert result.confidence >= 0.5
            assert len(result.reasons) > 0


@pytest.mark.skipif(not os.getenv("GOOGLE_API_KEY"), reason="GOOGLE_API_KEY not set")
class TestGeminiIntegration:
    """Integration tests that actually call Gemini API."""

    @pytest.mark.asyncio
    async def test_real_gemini_analysis(self):
        """Test actual Gemini API call with real content."""
        analyzer = ContentAnalyzer()

        if not analyzer.use_gemini:
            pytest.skip("Gemini not initialized")

        content = """
        "Good morning, Sarah," Dr. Williams said as she entered the office.
        
        Sarah looked up from her computer. "Oh, hello Doctor. I was just reviewing the test results."
        
        "And what did you find?" the doctor asked, pulling up a chair.
        
        "The results are quite interesting," Sarah replied, turning the monitor. "Look at these numbers."
        """

        result = await analyzer.analyze_content(content, SourceType.TEXT)

        # Should detect as multi-voice with high confidence
        assert result.suggested_job_type == JobType.MULTI_VOICE
        assert result.confidence > 0.8

        features = result.detected_features
        assert features.get("has_dialogue") == "True"
        assert float(features.get("dialogue_percentage", 0)) > 0.5
        assert int(features.get("estimated_speakers", 0)) >= 2

        # Should identify Sarah and Dr. Williams
        if "identified_characters" in features:
            import json

            characters = json.loads(features["identified_characters"])
            assert any("Sarah" in c for c in characters)
            assert any("Williams" in c or "Doctor" in c for c in characters)
