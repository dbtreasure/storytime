from __future__ import annotations

# TTS Voice model from infrastructure layer
from storytime.infrastructure.tts.base import Voice

# Domain model for Character
from storytime.models import Character


class VoiceAssigner:
    """Assigns TTS voices to characters, attempting to maintain consistency."""

    def __init__(self, provider_name: str, voices: list[Voice]):
        self.provider_name = provider_name
        self.all_voices: list[Voice] = voices  # Keep a copy of all available

        # Pre-sort voices by gender for faster lookup
        self.male_voices: list[Voice] = [v for v in voices if (v.gender or "").lower() == "male"]
        self.female_voices: list[Voice] = [v for v in voices if (v.gender or "").lower() == "female"]
        self.neutral_voices: list[Voice] = [
            v for v in voices if v not in self.male_voices + self.female_voices
        ]

        # Track which voice IDs have been used to promote variety
        self.assigned_voice_ids: set[str] = set()

    def assign_voice_to_character(self, character: Character) -> str:
        """Assign a voice ID to *character*, caching it on the character object."""

        # 1. Check if this character already has a voice for this provider
        if self.provider_name in character.voice_assignments:
            return character.voice_assignments[self.provider_name]

        # 2. Determine the best pool of voices based on gender
        voice_pool: list[Voice]
        if character.gender == "male":
            voice_pool = self.male_voices
        elif character.gender == "female":
            voice_pool = self.female_voices
        else:
            # For unknown/neutral, prefer neutral voices, then any others
            voice_pool = self.neutral_voices or self.all_voices

        # 3. Try to find an unassigned voice from the preferred pool
        for voice in voice_pool:
            if voice.id not in self.assigned_voice_ids:
                self.assigned_voice_ids.add(voice.id)
                character.voice_assignments[self.provider_name] = voice.id
                return voice.id

        # 4. If all in preferred pool are used, cycle through that pool (LRU)
        #    (Simple version: just pick the first one from the pool)
        if voice_pool:
            chosen_voice_id = voice_pool[0].id
            character.voice_assignments[self.provider_name] = chosen_voice_id
            return chosen_voice_id

        # 5. Absolute fallback: pick the first available voice from all voices
        if self.all_voices:
            fallback_id = self.all_voices[0].id
            character.voice_assignments[self.provider_name] = fallback_id
            return fallback_id

        # Should not happen if providers return voices, but as a last resort:
        return "default"  # Or raise an error

    def get_narrator_voice(self) -> str:
        """Return a consistent voice ID for the narrator."""

        # Prefer first neutral voice, then first female, then first male, then any.
        # This logic could be more sophisticated (e.g. config-driven default)
        if self.neutral_voices:
            return self.neutral_voices[0].id
        if self.female_voices:  # Often a good default for narration
            return self.female_voices[0].id
        if self.male_voices:
            return self.male_voices[0].id
        if self.all_voices:
            return self.all_voices[0].id
        return "default"  # Last resort
