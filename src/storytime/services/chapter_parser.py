from __future__ import annotations

import json
import os
from pathlib import Path

import google.generativeai as genai
from dotenv import load_dotenv

from storytime.models import Chapter, SpeakerType, TextSegment, CharacterCatalogue
from storytime.services.character_analyzer import CharacterAnalyzer

load_dotenv()


class ChapterParser:
    """Parse raw novel text into structured `Chapter` objects using Gemini."""

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def __init__(self, api_key: str | None = None):
        self.api_key: str | None = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google API key is required. Set GOOGLE_API_KEY env variable or pass api_key param."
            )

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")
        self.character_analyzer = CharacterAnalyzer(api_key=self.api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def parse_chapter_from_file(
        self, file_path: str | Path, chapter_number: int, title: str | None = None
    ) -> Chapter:
        """Convenience wrapper to parse chapter text from a file."""

        chapter_text = Path(file_path).read_text(encoding="utf-8")
        return self.parse_chapter_text(chapter_text, chapter_number, title)

    def parse_chapter_with_characters(self, chapter_text: str, chapter_number: int, 
                                    title: str | None = None, 
                                    character_catalogue: CharacterCatalogue | None = None,
                                    output_dir: str = "chapter_data") -> tuple[Chapter, CharacterCatalogue]:
        """Parse chapter and analyze characters, saving all data to structured directory."""
        
        # Create output directory structure - chapter_data as subdirectory
        base_output_path = Path(output_dir)
        chapter_data_path = base_output_path / "chapter_data" / f"chapter_{chapter_number:02d}"
        chapter_data_path.mkdir(parents=True, exist_ok=True)
        
        # Save raw text
        text_file = chapter_data_path / "text.txt"
        text_file.write_text(chapter_text, encoding='utf-8')
        
        # Initialize or use existing character catalogue
        if character_catalogue is None:
            from storytime.models import CharacterCatalogue
            character_catalogue = CharacterCatalogue()
        
        # Analyze characters
        print(f"🎭 Analyzing characters in chapter {chapter_number}...")
        existing_character_names = character_catalogue.get_character_names()
        new_characters = self.character_analyzer.analyze_characters(
            chapter_text, existing_character_names
        )
        
        # Add new characters to catalogue
        for character in new_characters:
            character_catalogue.add_character(character)
            print(f"   ✅ Found new character: {character.name} ({character.gender})")
        
        # Parse chapter segments
        chapter = self.parse_chapter_text(chapter_text, chapter_number, title)
        
        # Save parsed segments
        segments_file = chapter_data_path / "segments.json"
        with segments_file.open("w", encoding="utf-8") as f:
            json.dump(chapter.model_dump(), f, indent=2, ensure_ascii=False)
        
        # Save character catalogue
        characters_file = chapter_data_path / "characters.json"
        with characters_file.open("w", encoding="utf-8") as f:
            json.dump(character_catalogue.model_dump(), f, indent=2, ensure_ascii=False)
        
        print(f"💾 Chapter data saved to: {chapter_data_path}")
        print(f"   📄 Raw text: text.txt")
        print(f"   📊 Segments: segments.json")
        print(f"   🎭 Characters: characters.json")
        
        return chapter, character_catalogue

    def parse_chapter_text(
        self, chapter_text: str, chapter_number: int, title: str | None = None
    ) -> Chapter:
        """Parse raw chapter text into a structured `Chapter` object."""

        if len(chapter_text) > 800:
            print(f"📚 Chapter is long ({len(chapter_text)} chars), processing in chunks…")
            return self._parse_long_chapter_text(chapter_text, chapter_number, title)

        prompt = self._create_parsing_prompt(chapter_text, chapter_number)
        return self._parse_with_gemini(prompt, chapter_number, title)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _create_parsing_prompt(self, chapter_text: str, chapter_number: int) -> str:
        """Return the system prompt instructing Gemini to segment the chapter."""

        return f"""
### ROLE AND OBJECTIVE ###
You are a professional audiobook dialogue separator with expertise in industry-standard voice acting practices. Your goal is to parse novel text into precisely structured segments that follow professional audiobook conventions where dialogue and narrative descriptions are read by different voice actors.

### INSTRUCTIONS / RESPONSE RULES ###

**Core Separation Rules:**
• Direct quoted speech ("dialogue text") must be assigned to the CHARACTER who speaks it
• Dialogue tags (said, replied, whispered, etc.) must be assigned to the NARRATOR
• Action descriptions within dialogue paragraphs must be assigned to the NARRATOR
• Pure narrative text must be assigned to the NARRATOR
• Each segment must contain ONLY text for one speaker type (never mix character + narrator in same segment)

**TTS Instruction Rules:**
• Generate specific, actionable TTS instructions for each segment based on context and emotion
• Instructions should guide voice delivery, pacing, tone, and emotional expression
• Consider the broader narrative context when crafting instructions
• Make instructions concise but specific (1-2 sentences maximum)

**Text Processing Rules:**
• Preserve exact punctuation, capitalization, and spacing
• Maintain strict sequential order of all text
• Include ALL text from the source - nothing should be omitted
• Use consistent character names throughout (first occurrence sets the standard)

**Character Identification Rules:**
• Extract speaker names from dialogue tags: "said Marcus" → speaker is "Marcus"
• For implied dialogue (no explicit tag), use context clues to identify speaker
• When unsure of speaker, default to previous established speaker in conversation

**Output Validation Rules:**
• Return ONLY valid JSON - no explanatory text before or after
• Each segment must have all required fields populated
• Sequence numbers must be consecutive starting from 1

### CONTEXT ###
CHAPTER {chapter_number} TEXT TO PROCESS:
```
{chapter_text}
```

### EXAMPLES ###

**Input Text:**
"Hello there," said Sarah with a smile. "How are you today?"

**Correct Professional Separation:**
[
  {{
    "text": ""Hello there,"",
    "speaker_type": "character",
    "speaker_name": "Sarah",
    "sequence_number": 1,
    "voice_hint": "female, friendly",
    "emotion": "cheerful",
    "instruction": "Deliver this greeting with a warm, friendly tone, conveying Sarah's cheerful demeanor."
  }},
  {{
    "text": "said Sarah with a smile.",
    "speaker_type": "narrator", 
    "speaker_name": "narrator",
    "sequence_number": 2,
    "voice_hint": "neutral, descriptive",
    "emotion": null,
    "instruction": "Deliver this dialogue tag with a calm, neutral tone that smoothly transitions between character voices."
  }},
  {{
    "text": ""How are you today?"",
    "speaker_type": "character",
    "speaker_name": "Sarah", 
    "sequence_number": 3,
    "voice_hint": "female, friendly",
    "emotion": "curious",
    "instruction": "Voice this question with genuine curiosity and continued warmth, maintaining Sarah's friendly tone."
  }}
]

### REASONING STEPS ###
Before generating output, follow this process:
1. **Scan for Dialogue**: Identify all quoted speech sections
2. **Identify Speakers**: Extract character names from dialogue tags and context
3. **Separate Components**: Split mixed paragraphs into dialogue vs. narrative parts
4. **Assign Voice Types**: Map each segment to character or narrator
5. **Add Metadata**: Determine voice hints and emotional context
6. **Validate Sequence**: Ensure all text is included in correct order

### OUTPUT FORMATTING CONSTRAINTS ###
Return ONLY a valid JSON array with this exact structure:
[
  {{
    "text": "exact text content",
    "speaker_type": "narrator" or "character", 
    "speaker_name": "narrator" or "Character Name",
    "sequence_number": integer,
    "voice_hint": "descriptive voice characteristics",
    "emotion": "emotional tone or null",
    "instruction": "specific TTS delivery instruction"
  }}
]

**Critical Requirements:**
• speaker_type must be exactly "narrator" or "character"
• speaker_name must be "narrator" for all narrator segments
• sequence_number must start at 1 and increment by 1
• voice_hint should describe gender, age, personality traits
• emotion can be null or descriptive string
• No markdown formatting, explanations, or additional text
"""

    def _parse_with_gemini(
        self, prompt: str, chapter_number: int, title: str | None
    ) -> Chapter:
        """Send *prompt* to Gemini and build a `Chapter`."""

        try:
            response = self.model.generate_content(prompt)
            print("Gemini raw response:", response.text)
            response_text = self._clean_gemini_response(response.text)
            segments_data = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse Gemini response as JSON: {exc}\nResponse: {response_text}"
            ) from exc

        segments = [self._segment_from_dict(sd, idx) for idx, sd in enumerate(segments_data, 1)]

        return Chapter(
            chapter_number=chapter_number,
            title=title,
            segments=segments,
        )

    def _parse_long_chapter_text(
        self, chapter_text: str, chapter_number: int, title: str | None
    ) -> Chapter:
        """Chunk long chapters and combine the results."""

        chunks = self._split_text_into_chunks(chapter_text)
        print(f"   📝 Split into {len(chunks)} chunks")

        all_segments: list[TextSegment] = []
        seq_offset = 0
        for idx, chunk in enumerate(chunks, 1):
            print(f"   🔄 Processing chunk {idx}/{len(chunks)} ({len(chunk)} chars)…")
            prompt = self._create_parsing_prompt(chunk, chapter_number)
            try:
                response = self.model.generate_content(prompt)
                print(f"Gemini raw response (chunk {idx}):", response.text)
                response_text = self._clean_gemini_response(response.text)
                chunk_data = json.loads(response_text)

                for seg_dict in chunk_data:
                    segment = self._segment_from_dict(seg_dict, seg_dict.get("sequence_number", 0))
                    segment.sequence_number += seq_offset
                    all_segments.append(segment)

                seq_offset = len(all_segments)
                print(f"      ✅ Chunk {idx} processed: {len(chunk_data)} segments")
            except Exception as exc:  # noqa: BLE001
                print(f"      ❌ Error processing chunk {idx}: {exc}")
                continue  # proceed with remaining chunks

        # Re-number sequentially
        for idx, seg in enumerate(all_segments, 1):
            seg.sequence_number = idx

        print(f"   ✅ Combined {len(all_segments)} total segments from all chunks")
        return Chapter(chapter_number=chapter_number, title=title, segments=all_segments)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    @staticmethod
    def _clean_gemini_response(response_text: str) -> str:
        """Remove Markdown fences Gemini occasionally adds."""

        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        return response_text

    @staticmethod
    def _split_text_into_chunks(text: str, max_chunk_size: int = 800) -> list[str]:
        """Split *text* into roughly equal-sized chunks respecting paragraphs."""

        if len(text) <= max_chunk_size:
            return [text]

        paragraphs = text.split("\n\n")
        if len(paragraphs) > 1:
            chunks: list[str] = []
            current = ""
            for paragraph in paragraphs:
                if len(current) + len(paragraph) + 2 > max_chunk_size and current:
                    chunks.append(current.strip())
                    current = paragraph
                else:
                    current = f"{current}\n\n{paragraph}" if current else paragraph
            if current:
                chunks.append(current.strip())
            return chunks

        # Fallback to sentence splitting
        sentences = text.split(". ")
        chunks = []
        current = ""
        for i, sentence in enumerate(sentences):
            if i < len(sentences) - 1:
                sentence += ". "
            if len(current) + len(sentence) > max_chunk_size and current:
                chunks.append(current.strip())
                current = sentence
            else:
                current += sentence
        if current:
            chunks.append(current.strip())
        return chunks

    @staticmethod
    def _segment_from_dict(seg_data: dict, fallback_seq: int) -> TextSegment:
        """Convert raw dict from Gemini into `TextSegment`."""

        speaker_type = (
            SpeakerType.NARRATOR
            if seg_data.get("speaker_type", "narrator") == "narrator"
            else SpeakerType.CHARACTER
        )
        return TextSegment(
            text=str(seg_data.get("text", "")),
            speaker_type=speaker_type,
            speaker_name=str(seg_data.get("speaker_name", "narrator")),
            sequence_number=int(seg_data.get("sequence_number", fallback_seq)),
            voice_hint=seg_data.get("voice_hint"),
            emotion=seg_data.get("emotion"),
            instruction=seg_data.get("instruction"),
        ) 