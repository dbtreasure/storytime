import google.generativeai as genai
import json
import os
from typing import List, Optional
from models import Character, CharacterCatalogue
from dotenv import load_dotenv

load_dotenv()

class CharacterAnalyzer:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Gemini API client for character analysis."""
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("Google API key is required.")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
    def analyze_characters(self, chapter_text: str, existing_characters: Optional[List[str]] = None) -> List[Character]:
        """Analyze text to identify characters and their attributes."""
        
        existing_list = existing_characters or []
        existing_str = ", ".join(existing_list) if existing_list else "None"
        
        prompt = f"""
### ROLE ###
You are a literary character analyst. Analyze the provided text to identify all speaking characters.

### INSTRUCTIONS ###
1. Identify all characters who speak dialogue (have quoted speech attributed to them)
2. For each character, determine:
   - Exact name as it appears in dialogue tags
   - Gender (male/female/other/unknown)
   - Brief description (age, role, personality traits)
3. ONLY return NEW characters not in the existing list
4. Return ONLY valid JSON - no explanatory text

### EXISTING CHARACTERS ###
{existing_str}

### TEXT TO ANALYZE ###
```
{chapter_text}
```

### OUTPUT FORMAT ###
Return a JSON array of character objects:
[
  {{
    "name": "Character Name",
    "gender": "male|female|other|unknown", 
    "description": "Brief character description"
  }}
]

If no new characters found, return: []
"""
        
        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean up response
            if response_text.startswith('```json'):
                response_text = response_text[7:]
            if response_text.endswith('```'):
                response_text = response_text[:-3]
            
            characters_data = json.loads(response_text)
            
            characters = []
            for char_data in characters_data:
                character = Character(
                    name=char_data.get('name', ''),
                    gender=char_data.get('gender'),
                    description=char_data.get('description')
                )
                characters.append(character)
            
            return characters
            
        except Exception as e:
            print(f"Error analyzing characters: {e}")
            return [] 