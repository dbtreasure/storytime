from __future__ import annotations

import json
import os

import google.generativeai as genai
from dotenv import load_dotenv

from storytime.models import Character

load_dotenv()


class CharacterAnalyzer:
    """Analyze raw text to extract new speaking characters and metadata."""

    def __init__(self, api_key: str | None = None):
        self.api_key: str | None = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key is required.")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze_characters(
        self,
        chapter_text: str,
        existing_characters: list[str] | None = None,
    ) -> list[Character]:
        """Return a list of *new* Character objects found in *chapter_text*.

        Any names already present in *existing_characters* are filtered out.
        """

        existing_list = existing_characters or []
        existing_str = ", ".join(existing_list) if existing_list else "None"

        prompt = self._build_prompt(chapter_text, existing_str)

        try:
            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            # Gemini sometimes wraps JSON in markdown fences.
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]

            characters_data = json.loads(response_text)
            return [
                Character(
                    name=cd.get("name", ""),
                    gender=cd.get("gender"),
                    description=cd.get("description"),
                )
                for cd in characters_data
            ]
        except Exception as exc:
            # In library code we avoid prints; instead raise or log.
            raise RuntimeError(f"Error analysing characters: {exc}") from exc

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_prompt(self, chapter_text: str, existing_str: str) -> str:
        """Return the LLM prompt string."""

        return f"""
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
