import google.generativeai as genai
import json
import os
from typing import List, Optional
from models import TextSegment, Chapter, SpeakerType
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class ChapterParser:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Gemini API client."""
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("Google API key is required. Set GOOGLE_API_KEY environment variable or pass api_key parameter.")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def create_parsing_prompt(self, chapter_text: str, chapter_number: int) -> str:
        """Create a detailed prompt for Gemini to parse the chapter."""
        prompt = f"""
You are an expert literary analyzer. Parse this chapter from a novel into structured segments for text-to-speech processing.

CHAPTER {chapter_number} TEXT:
{chapter_text}

INSTRUCTIONS:
1. Break the text into segments where each segment is either:
   - NARRATOR: Descriptive text, scene setting, action descriptions
   - CHARACTER: Direct speech/dialogue from a specific character

2. For each segment, identify:
   - The exact text content
   - Whether it's narrator or character dialogue
   - If character dialogue, identify the speaker's name
   - Emotional tone (if apparent): angry, sad, cheerful, calm, dramatic, etc.
   - Voice characteristics: male/female, young/old, aristocratic/common, etc.

3. Maintain the exact sequence order of the text.

4. For character names, use the full name as first introduced, then be consistent.

5. Return ONLY a valid JSON array with this exact structure:
[
  {{
    "text": "exact text content",
    "speaker_type": "narrator" or "character",
    "speaker_name": "narrator" or "Character Full Name",
    "sequence_number": 1,
    "voice_hint": "descriptive voice characteristics",
    "emotion": "emotional tone or null"
  }}
]

IMPORTANT: 
- Include ALL text from the chapter
- Preserve exact quotes and punctuation
- Be consistent with character names
- Return ONLY the JSON array, no other text
"""
        return prompt
    
    def parse_chapter_text(self, chapter_text: str, chapter_number: int, title: Optional[str] = None) -> Chapter:
        """Parse raw chapter text into a structured Chapter object."""
        prompt = self.create_parsing_prompt(chapter_text, chapter_number)
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean up the response (sometimes Gemini adds markdown formatting)
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            # Parse JSON response
            segments_data = json.loads(response_text)
            print(f"Debug: Parsed {len(segments_data)} segments from Gemini response")
            
            # Debug: Show structure of first segment
            if segments_data and len(segments_data) > 0:
                print(f"Debug: First segment structure: {list(segments_data[0].keys())}")
            
            # Convert to TextSegment objects
            segments = []
            for seg_data in segments_data:
                # Ensure speaker_type is converted to enum
                speaker_type_str = seg_data.get('speaker_type', 'narrator')
                speaker_type = SpeakerType.NARRATOR if speaker_type_str == 'narrator' else SpeakerType.CHARACTER
                
                # Create segment with proper validation
                try:
                    segment = TextSegment(
                        text=str(seg_data.get('text', '')),
                        speaker_type=speaker_type,
                        speaker_name=str(seg_data.get('speaker_name', 'narrator')),
                        sequence_number=int(seg_data.get('sequence_number', len(segments) + 1)),
                        voice_hint=seg_data.get('voice_hint'),
                        emotion=seg_data.get('emotion')
                    )
                    segments.append(segment)
                except Exception as e:
                    print(f"Warning: Failed to create TextSegment for item {len(segments) + 1}: {e}")
                    # Create a fallback segment
                    segment = TextSegment(
                        text=str(seg_data.get('text', 'Error parsing segment')),
                        speaker_type=SpeakerType.NARRATOR,
                        speaker_name='narrator',
                        sequence_number=len(segments) + 1,
                        voice_hint=None,
                        emotion=None
                    )
                    segments.append(segment)
            
            # Create Chapter object
            chapter = Chapter(
                chapter_number=chapter_number,
                title=title,
                segments=segments
            )
            
            return chapter
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Gemini response as JSON: {e}\nResponse: {response_text}")
        except Exception as e:
            raise ValueError(f"Error parsing chapter with Gemini: {e}")
    
    def parse_chapter_from_file(self, file_path: str, chapter_number: int, title: Optional[str] = None) -> Chapter:
        """Parse a chapter from a text file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            chapter_text = f.read()
        
        return self.parse_chapter_text(chapter_text, chapter_number, title)

# Convenience function for quick usage
def parse_chapter(chapter_text: str, chapter_number: int, title: Optional[str] = None, api_key: Optional[str] = None) -> Chapter:
    """Quick function to parse a chapter without creating a parser instance."""
    parser = ChapterParser(api_key=api_key)
    return parser.parse_chapter_text(chapter_text, chapter_number, title) 