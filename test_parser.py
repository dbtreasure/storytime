from chapter_parser import ChapterParser
import os

def main():
    # Check if API key is set
    if not os.getenv('GOOGLE_API_KEY'):
        print("⚠️  Please set your GOOGLE_API_KEY environment variable first!")
        print("   You can get one from: https://makersuite.google.com/app/apikey")
        print("   Then run: export GOOGLE_API_KEY='your-key-here'")
        return
    
    try:
        # Initialize the parser
        parser = ChapterParser()
        
        # Parse chapter 1 from the file
        print("🚀 Parsing Chapter 1 of War and Peace with Gemini...")
        chapter = parser.parse_chapter_from_file(
            file_path="chapter_1.txt",
            chapter_number=1,
            title="Anna Pavlovna's Salon"
        )
        
        print(f"✅ Successfully parsed Chapter {chapter.chapter_number}: {chapter.title}")
        print(f"📊 Total segments: {len(chapter.segments)}")
        print(f"👥 Characters found: {', '.join(chapter.get_unique_characters())}")
        
        # Show first few segments
        print("\n📝 First 5 segments:")
        for i, segment in enumerate(chapter.segments[:5]):
            # Handle both enum and string cases for speaker_type
            speaker_type_str = segment.speaker_type.value if hasattr(segment.speaker_type, 'value') else str(segment.speaker_type)
            speaker_info = f"[{segment.speaker_name}]" if speaker_type_str == "character" else "[NARRATOR]"
            print(f"\n{segment.sequence_number}. {speaker_info}")
            print(f"   Text: {segment.text[:150]}{'...' if len(segment.text) > 150 else ''}")
            if segment.emotion:
                print(f"   Emotion: {segment.emotion}")
            if segment.voice_hint:
                print(f"   Voice: {segment.voice_hint}")
        
        # Save the parsed chapter to JSON for inspection
        chapter_data = chapter.model_dump()
        import json
        with open("parsed_chapter_1.json", "w", encoding="utf-8") as f:
            json.dump(chapter_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Full parsed chapter saved to: parsed_chapter_1.json")
        
        # Show statistics
        narrator_segments = chapter.get_narrator_segments()
        character_segments = chapter.get_character_segments()
        
        print(f"\n📈 Analysis:")
        print(f"   Narrator segments: {len(narrator_segments)}")
        print(f"   Character dialogue segments: {len(character_segments)}")
        print(f"   Dialogue ratio: {len(character_segments) / len(chapter.segments) * 100:.1f}%")
        
    except FileNotFoundError:
        print("❌ chapter_1.txt not found. Make sure the file exists in the current directory.")
    except ValueError as e:
        print(f"❌ API Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main() 