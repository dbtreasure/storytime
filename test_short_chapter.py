from chapter_parser import ChapterParser
from tts_generator import TTSGenerator
import os
import json

def main():
    print("🧪 Testing Complete Pipeline with Short Chapter")
    print("=" * 50)
    
    # Check API keys
    missing_keys = []
    if not os.getenv('GOOGLE_API_KEY'):
        missing_keys.append('GOOGLE_API_KEY')
    if not os.getenv('OPENAI_API_KEY'):
        missing_keys.append('OPENAI_API_KEY')
    
    if missing_keys:
        print("❌ Missing required API keys:")
        for key in missing_keys:
            print(f"   - {key}")
        print("\nPlease set your environment variables:")
        print("   export GOOGLE_API_KEY='your-google-key'")
        print("   export OPENAI_API_KEY='your-openai-key'")
        return
    
    try:
        # Step 1: Parse short test chapter with Gemini
        print("\n📖 Step 1: Parsing test chapter with Gemini API...")
        parser = ChapterParser()
        chapter = parser.parse_chapter_from_file(
            file_path="test_chapter.txt",
            chapter_number=1,
            title="A Business Meeting"
        )
        
        print(f"✅ Parsed Chapter {chapter.chapter_number}: {chapter.title}")
        print(f"   📊 {len(chapter.segments)} segments")
        print(f"   🎭 Characters: {', '.join(chapter.get_unique_characters())}")
        
        # Show what was parsed
        print(f"\n📝 Parsed segments:")
        for segment in chapter.segments:
            speaker_type_str = segment.speaker_type.value if hasattr(segment.speaker_type, 'value') else str(segment.speaker_type)
            speaker_info = f"[{segment.speaker_name}]" if speaker_type_str == "character" else "[NARRATOR]"
            print(f"   {segment.sequence_number}. {speaker_info}: {segment.text[:80]}{'...' if len(segment.text) > 80 else ''}")
            if segment.voice_hint:
                print(f"      Voice: {segment.voice_hint}")
            if segment.emotion:
                print(f"      Emotion: {segment.emotion}")
        
        # Step 2: Generate audio with OpenAI TTS
        print(f"\n🎵 Step 2: Generating complete audio with OpenAI TTS...")
        estimated_chars = sum(len(segment.text) for segment in chapter.segments)
        estimated_cost = (estimated_chars / 1000) * 0.015
        print(f"⚠️  Estimated cost: ~${estimated_cost:.3f} ({estimated_chars} characters)")
        
        # Ask for confirmation
        response = input("Continue with audio generation? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Audio generation cancelled by user.")
            return
        
        # Save parsed JSON results for inspection
        chapter_data = chapter.model_dump()
        with open("parsed_test_chapter.json", "w", encoding="utf-8") as f:
            json.dump(chapter_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Parsed chapter saved to: parsed_test_chapter.json")
        
        # Generate all audio files
        print(f"\n🎙️  Generating audio for all {len(chapter.segments)} segments...")
        tts_generator = TTSGenerator(output_dir="test_audio_output")
        audio_files = tts_generator.generate_audio_for_chapter(chapter)
        
        print(f"\n🎉 Test Complete!")
        print(f"📂 Check the output:")
        print(f"   📊 Parsed data: parsed_test_chapter.json")
        print(f"   🎵 Complete chapter: test_audio_output/chapter_01_complete.mp3")
        print(f"   📁 Individual files: test_audio_output/chapter_01/")
        print(f"   📝 Playlist: test_audio_output/chapter_01/chapter_01_playlist.m3u")
        
        # Show expected voice assignments
        print(f"\n🎭 Expected voice assignments:")
        for segment in chapter.segments:
            voice = tts_generator.select_voice(segment)
            speaker_type_str = segment.speaker_type.value if hasattr(segment.speaker_type, 'value') else str(segment.speaker_type)
            speaker_info = f"{segment.speaker_name}" if speaker_type_str == "character" else "Narrator"
            print(f"   {speaker_info}: {voice}")
        
    except FileNotFoundError:
        print("❌ test_chapter.txt not found. Make sure the file exists in the current directory.")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 