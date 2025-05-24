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
        """Create a detailed prompt for Gemini to parse the chapter with professional dialogue separation."""
        prompt = f"""
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
                        emotion=seg_data.get('emotion'),
                        instruction=seg_data.get('instruction')
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
                        emotion=None,
                        instruction=None
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