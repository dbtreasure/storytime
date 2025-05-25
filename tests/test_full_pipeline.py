import os
import json
import sys
from pathlib import Path

# Add src to path to allow running this script directly before proper packaging
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from storytime.services import ChapterParser, TTSGenerator
from storytime.models import Chapter # For type hinting if needed

def main():
    print("🚀 Testing Complete Pipeline: Text → Structured Data → Audio")
    print("=" * 60)
    
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
        # Step 1: Parse chapter with Gemini
        print("\n📖 Step 1: Parsing chapter text with Gemini API...")
        parser = ChapterParser()
        chapter = parser.parse_chapter_from_file(
            file_path= SCRIPT_DIR / "chapter_1.txt",
            chapter_number=1,
            title="Anna Pavlovna's Salon"
        )
        
        print(f"✅ Parsed Chapter {chapter.chapter_number}: {chapter.title}")
        print(f"   📊 {len(chapter.segments)} segments")
        print(f"   🎭 Characters: {', '.join(chapter.get_unique_characters())}")
        
        # Step 2: Generate audio with OpenAI TTS
        print(f"\n🎵 Step 2: Generating audio with OpenAI TTS...")
        print("⚠️  This will use OpenAI credits - estimated cost: ~$0.50-1.00")
        
        # Ask for confirmation
        response = input("Continue with audio generation? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Audio generation cancelled by user.")
            return
        
        tts_generator = TTSGenerator(output_dir= SCRIPT_DIR / "audio_output")
        
        # Generate audio for first 3 segments as a test
        print("🧪 Testing with first 3 segments...")
        test_segments = chapter.segments[:3]
        
        audio_files = {}
        for i, segment in enumerate(test_segments, 1):
            print(f"\n🎙️  Generating audio {i}/3...")
            try:
                audio_path = tts_generator.generate_audio_for_segment(
                    segment,
                    chapter.chapter_number,
                    chapter=chapter
                )
                audio_files[f"segment_{segment.sequence_number}"] = audio_path
                print(f"   ✅ Created: {os.path.basename(audio_path)}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        # Create summary
        print(f"\n📋 Test Summary:")
        print(f"   📁 Audio files created: {len(audio_files)}")
        print(f"   📂 Output directory: audio_output/")
        
        if audio_files:
            print(f"\n🎧 Generated audio files:")
            for filename in audio_files.values():
                print(f"   • {os.path.basename(filename)}")
            
            print(f"\n💡 To generate the full chapter audio:")
            print(f"   generator.generate_audio_for_chapter(chapter)")
            
        # Save test results
        test_results = {
            "chapter_info": {
                "number": chapter.chapter_number,
                "title": chapter.title,
                "total_segments": len(chapter.segments),
                "characters": list(chapter.get_unique_characters())
            },
            "audio_test": {
                "segments_tested": len(test_segments),
                "audio_files_created": len(audio_files),
                "audio_files": audio_files
            }
        }
        
        test_results_path = SCRIPT_DIR / "test_results.json"
        with open(test_results_path, "w", encoding="utf-8") as f:
            json.dump(test_results, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Test results saved to: {test_results_path.name}")
        
    except FileNotFoundError as e:
        # Make file not found more specific if possible
        if "chapter_1.txt" in str(e):
            print(f"❌ {SCRIPT_DIR / 'chapter_1.txt'} not found. Make sure the file exists.")
        else:
            print(f"❌ File not found: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main() 