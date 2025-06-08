import tempfile
from pathlib import Path

import pytest

from storytime.infrastructure.tts import TTSProvider, Voice
from storytime.models import Chapter, Character, CharacterCatalogue, SpeakerType, TextSegment
from storytime.services.tts_generator import TTSGenerator


class MockTTSProvider(TTSProvider):
    """Mock TTS provider for testing."""

    def __init__(self, name: str, voices: list[Voice]):
        self._name = name
        self._voices = voices

    @property
    def name(self) -> str:
        return self._name

    def list_voices(self) -> list[Voice]:
        return self._voices

    def synth(
        self, *, text: str, voice: str, style: str | None, format: str, out_path: Path
    ) -> Path:
        # Create a dummy file to simulate audio generation
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(f"Mock audio for voice {voice}: {text[:50]}")
        return out_path


@pytest.fixture
def sample_voices():
    """Sample voices for testing."""
    return [
        Voice(id="male_1", name="John", gender="male", description="Male voice 1"),
        Voice(id="male_2", name="Mike", gender="male", description="Male voice 2"),
        Voice(id="female_1", name="Sarah", gender="female", description="Female voice 1"),
        Voice(id="female_2", name="Emma", gender="female", description="Female voice 2"),
        Voice(id="neutral_1", name="Alex", gender="neutral", description="Neutral voice"),
    ]


@pytest.fixture
def sample_characters():
    """Sample character catalogue."""
    catalogue = CharacterCatalogue()
    catalogue.add_character(Character(name="Marcus", gender="male", description="Business partner"))
    catalogue.add_character(Character(name="Sarah", gender="female", description="Entrepreneur"))
    return catalogue


@pytest.fixture
def sample_chapter(sample_characters):
    """Sample chapter with multiple segments per character."""
    segments = [
        TextSegment(
            text="The morning sun filtered through the café windows.",
            speaker_type=SpeakerType.NARRATOR,
            speaker_name="narrator",
            sequence_number=1,
            voice_hint=None,
            emotion=None,
            instruction=None,
        ),
        TextSegment(
            text="You're early,",
            speaker_type=SpeakerType.CHARACTER,
            speaker_name="Marcus",
            sequence_number=2,
            voice_hint="male, warm",
            emotion="friendly",
            instruction="Speak warmly",
        ),
        TextSegment(
            text="said Marcus with a smile.",
            speaker_type=SpeakerType.NARRATOR,
            speaker_name="narrator",
            sequence_number=3,
            voice_hint=None,
            emotion=None,
            instruction=None,
        ),
        TextSegment(
            text="I couldn't sleep,",
            speaker_type=SpeakerType.CHARACTER,
            speaker_name="Sarah",
            sequence_number=4,
            voice_hint="female, anxious",
            emotion="nervous",
            instruction="Speak anxiously",
        ),
        TextSegment(
            text="Sarah replied nervously.",
            speaker_type=SpeakerType.NARRATOR,
            speaker_name="narrator",
            sequence_number=5,
            voice_hint=None,
            emotion=None,
            instruction=None,
        ),
        TextSegment(
            text="I suppose we should get to business.",
            speaker_type=SpeakerType.CHARACTER,
            speaker_name="Marcus",
            sequence_number=6,
            voice_hint="male, serious",
            emotion="businesslike",
            instruction="Speak seriously",
        ),
        TextSegment(
            text="I think we should do it,",
            speaker_type=SpeakerType.CHARACTER,
            speaker_name="Sarah",
            sequence_number=7,
            voice_hint="female, determined",
            emotion="confident",
            instruction="Speak with determination",
        ),
    ]

    return Chapter(chapter_number=1, title="Test Chapter", segments=segments)


def test_voice_consistency_single_provider(sample_voices, sample_characters, sample_chapter):
    """Test that each character gets the same voice across all segments for a single provider."""

    # Create mock provider
    provider = MockTTSProvider("test_provider", sample_voices)

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create TTS generator with character catalogue
        tts_generator = TTSGenerator(
            provider=provider, output_dir=temp_dir, character_catalogue=sample_characters
        )

        # Track voice assignments for each character
        character_voices = {}

        # Process each segment and track voice assignments
        for segment in sample_chapter.segments:
            voice_id = tts_generator.select_voice(segment)

            if segment.speaker_type == SpeakerType.CHARACTER:
                if segment.speaker_name not in character_voices:
                    character_voices[segment.speaker_name] = voice_id
                else:
                    # Assert that the same character gets the same voice
                    assert character_voices[segment.speaker_name] == voice_id, (
                        f"Character {segment.speaker_name} got different voices: "
                        f"{character_voices[segment.speaker_name]} vs {voice_id}"
                    )

        # Verify that different characters get different voices (when possible)
        assigned_voices = list(character_voices.values())
        if len(assigned_voices) > 1:
            assert len(set(assigned_voices)) > 1, (
                "Different characters should get different voices when available"
            )


def test_voice_consistency_multiple_providers(sample_voices, sample_characters, sample_chapter):
    """Test voice consistency across different TTS providers."""

    # Create two mock providers with different voice IDs but same structure
    provider1_voices = [
        Voice(id="openai_male_1", name="OpenAI Male", gender="male"),
        Voice(id="openai_female_1", name="OpenAI Female", gender="female"),
        Voice(id="openai_neutral_1", name="OpenAI Neutral", gender="neutral"),
    ]

    provider2_voices = [
        Voice(id="eleven_male_1", name="ElevenLabs Male", gender="male"),
        Voice(id="eleven_female_1", name="ElevenLabs Female", gender="female"),
        Voice(id="eleven_neutral_1", name="ElevenLabs Neutral", gender="neutral"),
    ]

    provider1 = MockTTSProvider("openai", provider1_voices)
    provider2 = MockTTSProvider("eleven", provider2_voices)

    with tempfile.TemporaryDirectory() as temp_dir:
        # Test with first provider
        tts_gen1 = TTSGenerator(
            provider=provider1, output_dir=temp_dir, character_catalogue=sample_characters
        )

        # Test with second provider
        tts_gen2 = TTSGenerator(
            provider=provider2, output_dir=temp_dir, character_catalogue=sample_characters
        )

        # Process segments with both providers
        for segment in sample_chapter.segments:
            if segment.speaker_type == SpeakerType.CHARACTER:
                voice1 = tts_gen1.select_voice(segment)
                voice2 = tts_gen2.select_voice(segment)

                # Get character from catalogue
                character = sample_characters.get_character(segment.speaker_name)
                assert character is not None

                # Verify voice assignments are stored per provider
                assert "openai" in character.voice_assignments
                assert "eleven" in character.voice_assignments
                assert character.voice_assignments["openai"] == voice1
                assert character.voice_assignments["eleven"] == voice2


def test_narrator_voice_consistency(sample_voices, sample_characters, sample_chapter):
    """Test that narrator gets consistent voice across segments."""

    provider = MockTTSProvider("test_provider", sample_voices)

    with tempfile.TemporaryDirectory() as temp_dir:
        tts_generator = TTSGenerator(
            provider=provider, output_dir=temp_dir, character_catalogue=sample_characters
        )

        narrator_voices = []

        # Collect narrator voice assignments
        for segment in sample_chapter.segments:
            if segment.speaker_type == SpeakerType.NARRATOR:
                voice_id = tts_generator.select_voice(segment)
                narrator_voices.append(voice_id)

        # Assert all narrator segments use the same voice
        assert len(set(narrator_voices)) == 1, (
            f"Narrator should use consistent voice, got: {set(narrator_voices)}"
        )


def test_gender_based_voice_assignment(sample_voices, sample_characters, sample_chapter):
    """Test that characters get voices matching their gender."""

    provider = MockTTSProvider("test_provider", sample_voices)

    with tempfile.TemporaryDirectory() as temp_dir:
        tts_generator = TTSGenerator(
            provider=provider, output_dir=temp_dir, character_catalogue=sample_characters
        )

        # Process segments and verify gender-appropriate voice assignment
        for segment in sample_chapter.segments:
            if segment.speaker_type == SpeakerType.CHARACTER:
                voice_id = tts_generator.select_voice(segment)
                character = sample_characters.get_character(segment.speaker_name)

                # Find the voice object
                voice_obj = next((v for v in sample_voices if v.id == voice_id), None)
                assert voice_obj is not None, f"Voice {voice_id} not found in available voices"

                # Verify gender matching (when character gender is specified)
                if character.gender in ["male", "female"]:
                    assert voice_obj.gender == character.gender, (
                        f"Character {character.name} ({character.gender}) got voice "
                        f"{voice_obj.name} ({voice_obj.gender})"
                    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
