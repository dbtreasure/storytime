#!/usr/bin/env python3
"""
Test the complete enhanced TTS pipeline with War and Peace Chapter 1.
This includes Gemini-generated TTS instructions during parsing.
"""

import json
import sys # Added for sys.path modification
from pathlib import Path # Added for path manipulation

# Add src to path to allow running this script directly before proper packaging
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from storytime.services import ChapterParser, TTSGenerator
from storytime.models import Chapter # For type hinting
from storytime.workflows.chapter_parsing import workflow as chapter_workflow

def main():
    print("🏛️  Testing Enhanced TTS Pipeline with War and Peace Chapter 1")
    print("=" * 70)
    
    try:
        # Step 1: Parse War and Peace Chapter 1 with enhanced instruction generation
        print("\n📖 Step 1: Parsing War and Peace Chapter 1 with Gemini API...")
        print("   Including TTS instruction generation during parsing...")
        
        file_path = SCRIPT_DIR / "chapter_1.txt"
        with open(file_path, "r", encoding="utf-8") as f:
            chapter_text = f.read()
        import asyncio
        async def run_workflow():
            await chapter_workflow.store.set_state({
                "chapter_text": chapter_text,
                "chapter_number": 1,
                "title": "Anna Pávlovna's Reception",
            })
            await chapter_workflow.execute()
            state = await chapter_workflow.store.get_state()
            return state.chapter
        chapter = asyncio.run(run_workflow())
        
        if not chapter:
            print("❌ No chapter parsed.")
            return
        
        print(f"✅ Parsed Chapter {chapter.chapter_number}: {chapter.title}")
        print(f"   📊 {len(chapter.segments)} segments")
        print(f"   🎭 Characters: {', '.join(sorted(chapter.get_unique_characters()))}")
        
        # Show parsing results summary
        narrator_count = len(chapter.get_narrator_segments())
        character_count = len(chapter.get_character_segments())
        total_characters = len("".join([seg.text for seg in chapter.segments]))
        
        print(f"\n📝 Parsing Summary:")
        print(f"   Narrator segments: {narrator_count}")
        print(f"   Character segments: {character_count}")
        print(f"   Total characters: {total_characters}")
        total_segments = narrator_count + character_count
        dialogue_ratio = (character_count/total_segments*100) if total_segments > 0 else 0.0
        print(f"   Dialogue ratio: {dialogue_ratio:.1f}%")
        
        # Show sample segments with instructions
        print(f"\n📝 Sample segments with TTS instructions:")
        for i, segment in enumerate(chapter.segments[:5], 1):
            speaker_type = segment.speaker_type if isinstance(segment.speaker_type, str) else segment.speaker_type.value
            print(f"   {i}. [{speaker_type.upper()}]: {segment.text[:80]}{'...' if len(segment.text) > 80 else ''}")
            if segment.instruction:
                print(f"      🎙️  Instruction: {segment.instruction[:100]}{'...' if len(segment.instruction) > 100 else ''}")
            print(f"      Voice: {segment.voice_hint or 'none'}")
            if segment.emotion:
                print(f"      Emotion: {segment.emotion}")
            print()
        
        # Save parsed JSON for inspection
        chapter_data = chapter.model_dump()
        parsed_output_path = SCRIPT_DIR / "parsed_war_and_peace_ch1.json" # Path relative to script
        with open(parsed_output_path, "w", encoding="utf-8") as f:
            json.dump(chapter_data, f, indent=2, ensure_ascii=False)
        print(f"💾 Parsed chapter saved to: {parsed_output_path.name}")
        
        # Step 2: Generate audio with enhanced TTS
        print(f"\n🎵 Step 2: Generating complete audiobook with OpenAI TTS...")
        print(f"   Model: gpt-4o-mini-tts (with instructions support)")
        
        # Calculate estimated cost
        estimated_cost = total_characters / 1000 * 0.015  # $0.015 per 1K characters
        print(f"⚠️  Estimated cost: ~${estimated_cost:.3f} ({total_characters} characters)")
        
        # Ask for confirmation
        response = input("Continue with audio generation? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Audio generation cancelled by user.")
            return
        
        print(f"\n🎙️  Generating audio for all {len(chapter.segments)} segments...")
        print("   Using pre-generated TTS instructions from parsing step...")
        
        # Generate audio
        audio_output_dir = SCRIPT_DIR / "war_and_peace_audio" # Path relative to script
        tts_generator = TTSGenerator(output_dir=str(audio_output_dir)) # Ensure string path
        audio_files = tts_generator.generate_audio_for_chapter(chapter)
        
        print(f"\n🎉 War and Peace Chapter 1 Complete!")
        print(f"📂 Check the output:")
        # Use pathlib for cleaner path joining for output messages
        # OpenAI is the default/hardcoded provider in this script for TTSGenerator
        complete_audio_file = audio_output_dir / "openai" / "chapter_01_complete.mp3"
        individual_files_dir = audio_output_dir / "openai" / "chapter_01"
        playlist_file = audio_output_dir / "openai" / "chapter_01" / "chapter_01_playlist.m3u"

        print(f"   📊 Parsed data: {parsed_output_path.name}") # Use relative name
        print(f"   🎵 Complete chapter: {complete_audio_file}")
        print(f"   📁 Individual files: {individual_files_dir}/") # Add trailing slash for clarity
        print(f"   📝 Playlist: {playlist_file}")
        
        # Final statistics
        print(f"\n📊 Final Statistics:")
        print(f"   Total segments processed: {len(audio_files)}")
        print(f"   Characters: {', '.join(sorted(chapter.get_unique_characters()))}")
        print(f"   Narrator voice: echo")
        print(f"   Character voices: Dynamic assignment based on gender/age hints")
        print(f"   Professional audiobook format with dialogue separation ✅")
        print(f"   Enhanced TTS instructions for optimal delivery ✅")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

if __name__ == "__main__":
    main() 