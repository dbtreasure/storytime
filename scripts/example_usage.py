import sys  # Added for sys.path modification
from pathlib import Path  # Added for path manipulation

# Add src to path to allow running this script directly before proper packaging
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from storytime.models import Chapter, SpeakerType, TextSegment


# Example of how your parsed War and Peace chapter might look
def create_sample_chapter():
    segments = [
        TextSegment(
            text="\"Well, Prince, so Genoa and Lucca are now just family estates of the Buonapartes. But I warn you, if you don't tell me that this means war, if you still try to defend the infamies and horrors perpetrated by that Antichrist—I really believe he is Antichrist—I will have nothing more to do with you and you are no longer my friend, no longer my 'faithful slave,' as you call yourself! But how do you do? I see I have frightened you—sit down and tell me all the news.\"",
            speaker_type=SpeakerType.CHARACTER,
            speaker_name="Anna Pavlovna Scherer",
            sequence_number=1,
            voice_hint="female, aristocratic",
            emotion="passionate, dramatic",
        ),
        TextSegment(
            text="It was in July, 1805, and the speaker was the well-known Anna Pávlovna Schérer, maid of honor and favorite of the Empress Márya Fëdorovna. With these words she greeted Prince Vasíli Kurágin, a man of high rank and importance, who was the first to arrive at her reception.",
            speaker_type=SpeakerType.NARRATOR,
            speaker_name="narrator",
            sequence_number=2,
            voice_hint="neutral, authoritative",
            emotion=None,
        ),
        TextSegment(
            text='"Heavens! what a virulent attack!" replied the prince, not in the least disconcerted by this reception.',
            speaker_type=SpeakerType.CHARACTER,
            speaker_name="Prince Vasili Kuragin",
            sequence_number=3,
            voice_hint="male, elderly, refined",
            emotion="amused, calm",
        ),
        TextSegment(
            text="He had just entered, wearing an embroidered court uniform, knee breeches, and shoes, and had stars on his breast and a serene expression on his flat face.",
            speaker_type=SpeakerType.NARRATOR,
            speaker_name="narrator",
            sequence_number=4,
            voice_hint="neutral, descriptive",
            emotion=None,
        ),
    ]

    chapter = Chapter(chapter_number=1, title="Anna Pavlovna's Salon", segments=segments)

    return chapter


# Example usage
if __name__ == "__main__":
    chapter_1 = create_sample_chapter()

    print(f"Chapter {chapter_1.chapter_number}: {chapter_1.title}")
    print(f"Total segments: {len(chapter_1.segments)}")
    print(f"Characters in this chapter: {chapter_1.get_unique_characters()}")

    print("\n--- Segments ---")
    for segment in chapter_1.segments:
        speaker_info = (
            f"[{segment.speaker_name}]"
            if segment.speaker_type == SpeakerType.CHARACTER
            else "[NARRATOR]"
        )
        print(f"{segment.sequence_number}. {speaker_info}: {segment.text[:100]}...")
        if segment.emotion:
            print(f"   Emotion: {segment.emotion}")
        if segment.voice_hint:
            print(f"   Voice: {segment.voice_hint}")
        print()

    # Convert to dict for Gemini API processing
    chapter_dict = chapter_1.model_dump()
    print("JSON structure ready for API:", chapter_dict.keys())
