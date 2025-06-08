import json
import os
import sys
from pathlib import Path

# Add src to path to allow running this script directly before proper packaging
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from storytime.workflows.chapter_parsing import workflow as chapter_workflow


def main():
    # Check if API key is set
    if not os.getenv("GOOGLE_API_KEY"):
        print("⚠️  Please set your GOOGLE_API_KEY environment variable first!")
        print("   You can get one from: https://makersuite.google.com/app/apikey")
        print("   Then run: export GOOGLE_API_KEY='your-key-here'")
        return

    try:
        # Parse chapter 1 from the file using Junjo workflow
        print("🚀 Parsing Chapter 1 of War and Peace with Junjo workflow...")
        file_path = SCRIPT_DIR / "chapter_1.txt"
        with open(file_path, encoding="utf-8") as f:
            chapter_text = f.read()
        import asyncio

        async def run_workflow():
            await chapter_workflow.store.set_state(
                {
                    "chapter_text": chapter_text,
                    "chapter_number": 1,
                    "title": "Anna Pavlovna's Salon",
                }
            )
            await chapter_workflow.execute()
            state = await chapter_workflow.store.get_state()
            return state.chapter

        chapter = asyncio.run(run_workflow())

        if not chapter:
            print("❌ No chapter parsed.")
            return

        print(f"✅ Successfully parsed Chapter {chapter.chapter_number}: {chapter.title}")
        print(f"📊 Total segments: {len(chapter.segments)}")
        print(f"👥 Characters found: {', '.join(chapter.get_unique_characters())}")

        # Show first few segments
        print("\n📝 First 5 segments:")
        for i, segment in enumerate(chapter.segments[:5]):
            # Handle both enum and string cases for speaker_type
            speaker_type_str = (
                segment.speaker_type.value
                if hasattr(segment.speaker_type, "value")
                else str(segment.speaker_type)
            )
            speaker_info = (
                f"[{segment.speaker_name}]" if speaker_type_str == "character" else "[NARRATOR]"
            )
            print(f"\n{segment.sequence_number}. {speaker_info}")
            print(f"   Text: {segment.text[:150]}{'...' if len(segment.text) > 150 else ''}")
            if segment.emotion:
                print(f"   Emotion: {segment.emotion}")
            if segment.voice_hint:
                print(f"   Voice: {segment.voice_hint}")

        # Save the parsed chapter to JSON for inspection
        chapter_data = chapter.model_dump()
        output_path = SCRIPT_DIR / "parsed_chapter_1.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(chapter_data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Full parsed chapter saved to: {output_path.name}")

        # Show statistics
        narrator_segments = chapter.get_narrator_segments()
        character_segments = chapter.get_character_segments()

        print("\n📈 Analysis:")
        print(f"   Narrator segments: {len(narrator_segments)}")
        print(f"   Character dialogue segments: {len(character_segments)}")
        print(f"   Dialogue ratio: {len(character_segments) / len(chapter.segments) * 100:.1f}%")

    except FileNotFoundError:
        print(
            f"❌ {SCRIPT_DIR / 'chapter_1.txt'} not found. Make sure the file exists in the current directory."
        )
    except ValueError as e:
        print(f"❌ API Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
