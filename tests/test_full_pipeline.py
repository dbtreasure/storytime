import os
print("OTEL_EXPORTER_OTLP_HEADERS:", repr(os.getenv("OTEL_EXPORTER_OTLP_HEADERS")))
import json
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Add src to path to allow running this script directly before proper packaging
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from storytime.services import TTSGenerator
from storytime.models import Chapter # For type hinting if needed
from storytime.workflows.chapter_parsing import workflow as chapter_workflow

CHAPTER_PATH = Path(__file__).parent / "fixtures" / "chapter_1.txt"

def main():
    logger.info("🚀 Testing Complete Pipeline: Text → Structured Data → Audio")
    print("🚀 Testing Complete Pipeline: Text → Structured Data → Audio")
    print("=" * 60)
    
    # Check API keys
    missing_keys = []
    if not os.getenv('GOOGLE_API_KEY'):
        missing_keys.append('GOOGLE_API_KEY')
    if not os.getenv('OPENAI_API_KEY'):
        missing_keys.append('OPENAI_API_KEY')
    
    if missing_keys:
        logger.error(f"Missing required API keys: {missing_keys}")
        print("❌ Missing required API keys:")
        for key in missing_keys:
            print(f"   - {key}")
        print("\nPlease set your environment variables:")
        print("   export GOOGLE_API_KEY='your-google-key'")
        print("   export OPENAI_API_KEY='your-openai-key'")
        return
    
    try:
        # Step 1: Parse chapter with Junjo workflow
        logger.info("Step 1: Parsing chapter text with Junjo workflow...")
        print("\n📖 Step 1: Parsing chapter text with Junjo workflow...")
        with open(CHAPTER_PATH, "r", encoding="utf-8") as f:
            chapter_text = f.read()
        import asyncio
        async def run_workflow():
            await chapter_workflow.store.set_state({
                "chapter_text": chapter_text,
                "chapter_number": 1,
                "title": "Anna Pavlovna's Salon",
            })
            await chapter_workflow.execute()
            state = await chapter_workflow.store.get_state()
            return state.chapter
        chapter = asyncio.run(run_workflow())
        
        if not chapter:
            logger.error("No chapter parsed.")
            print("❌ No chapter parsed.")
            return
        
        print(f"✅ Parsed Chapter {chapter.chapter_number}: {chapter.title}")
        print(f"   📊 {len(chapter.segments)} segments")
        print(f"   🎭 Characters: {', '.join(chapter.get_unique_characters())}")
        
        # Step 2: Generate audio with OpenAI TTS
        logger.info("Step 2: Generating audio with OpenAI TTS...")
        print(f"\n🎵 Step 2: Generating audio with OpenAI TTS...")
        print("⚠️  This will use OpenAI credits - estimated cost: ~$0.50-1.00")
        
        # Ask for confirmation
        logger.debug("Prompting user for audio generation confirmation...")
        response = input("Continue with audio generation? (y/N): ").strip().lower()
        logger.debug(f"User input: {response}")
        if response != 'y':
            logger.info("Audio generation cancelled by user.")
            print("❌ Audio generation cancelled by user.")
            return
        
        tts_generator = TTSGenerator(output_dir=str(SCRIPT_DIR / "audio_output"))
        
        # Generate audio for first 3 segments as a test
        logger.info("Testing with first 3 segments...")
        print("🧪 Testing with first 3 segments...")
        test_segments = chapter.segments[:3]
        
        audio_files = {}
        for i, segment in enumerate(test_segments, 1):
            logger.info(f"Generating audio {i}/3 for segment {segment.sequence_number}")
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
                logger.error(f"Error generating audio for segment {segment.sequence_number}: {e}")
                print(f"   ❌ Error: {e}")
        
        # Create summary
        logger.info(f"Audio files created: {len(audio_files)}")
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
        logger.error(f"File not found: {e}")
        # Make file not found more specific if possible
        if "chapter_1.txt" in str(e):
            print(f"❌ {CHAPTER_PATH} not found. Make sure the file exists.")
        else:
            print(f"❌ File not found: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main() 