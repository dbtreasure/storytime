from typing import Dict, List
from models import Character, CharacterCatalogue
from tts_providers.base import Voice

class VoiceAssigner:
    def __init__(self, provider_name: str, voices: List[Voice]):
        self.provider_name = provider_name
        self.voices = voices
        
        # Organize voices by gender
        self.male_voices = [v for v in voices if (v.gender or "").lower() == "male"]
        self.female_voices = [v for v in voices if (v.gender or "").lower() == "female"]
        self.neutral_voices = [v for v in voices if v not in self.male_voices + self.female_voices]
        
        # Track assigned voices to avoid duplicates
        self.assigned_voices = set()
    
    def assign_voice_to_character(self, character: Character) -> str:
        """Assign a voice to a character based on their gender."""
        
        # Check if character already has a voice for this provider
        if self.provider_name in character.voice_assignments:
            return character.voice_assignments[self.provider_name]
        
        # Select voice pool based on character gender
        if character.gender == "male":
            pool = self.male_voices
        elif character.gender == "female":
            pool = self.female_voices
        else:
            pool = self.neutral_voices or self.male_voices or self.female_voices
        
        # Find first unassigned voice in pool
        for voice in pool:
            if voice.id not in self.assigned_voices:
                self.assigned_voices.add(voice.id)
                character.voice_assignments[self.provider_name] = voice.id
                return voice.id
        
        # If all voices assigned, cycle through pool
        if pool:
            voice_id = pool[0].id
            character.voice_assignments[self.provider_name] = voice_id
            return voice_id
        
        # Fallback to first available voice
        return self.voices[0].id if self.voices else "default"
    
    def get_narrator_voice(self) -> str:
        """Get a consistent narrator voice."""
        # Use first neutral voice, or fallback to first available
        if self.neutral_voices:
            return self.neutral_voices[0].id
        elif self.voices:
            return self.voices[0].id
        return "default" 