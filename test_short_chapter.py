import argparse
import os
import json

from chapter_parser import ChapterParser
from tts_generator import TTSGenerator

# Provider classes
from tts_providers.openai_provider import OpenAIProvider
from tts_providers.elevenlabs_provider import ElevenLabsProvider

def main():
    # ---------------- CLI ----------------
    argp = argparse.ArgumentParser(description="Run short-chapter TTS pipeline with selectable provider.")
    argp.add_argument("--tts", choices=["openai", "eleven"], default="openai", help="TTS backend to use")
    args = argp.parse_args()

    provider_choice: str = args.tts.lower()

    print("🧪 Testing Complete Pipeline with Short Chapter")
    print("=" * 50)
    
    # ---------------- API key checks ----------------
    missing_keys = []
    if not os.getenv('GOOGLE_API_KEY'):
        missing_keys.append('GOOGLE_API_KEY')
    if provider_choice == "openai" and not os.getenv('OPENAI_API_KEY'):
        missing_keys.append('OPENAI_API_KEY')
    if provider_choice == "eleven" and not os.getenv("ELEVEN_LABS_API_KEY"):
        missing_keys.append('ELEVEN_LABS_API_KEY')
    
    if missing_keys:
        print("❌ Missing required API keys:")
        for key in missing_keys:
            print(f"   - {key}")
        print("\nPlease set your environment variables:")
        print("   export GOOGLE_API_KEY='your-google-key'")
        if provider_choice == "openai":
            print("   export OPENAI_API_KEY='your-openai-key'")
        else:
            print("   export ELEVEN_LABS_API_KEY='your-elevenlabs-key'")
        return
    
    try:
        # Step 1: Parse short test chapter with character analysis
        print("\n📖 Step 1: Parsing test chapter with character analysis...")
        parser = ChapterParser()
        
        # Read chapter text
        with open("test_chapter.txt", 'r', encoding='utf-8') as f:
            chapter_text = f.read()
        
        # Parse with character analysis
        chapter, character_catalogue = parser.parse_chapter_with_characters(
            chapter_text=chapter_text,
            chapter_number=1,
            title="A Business Meeting",
            output_dir="chapter_data"
        )
        
        print(f"✅ Parsed Chapter {chapter.chapter_number}: {chapter.title}")
        print(f"   📊 {len(chapter.segments)} segments")
        print(f"   🎭 Characters: {', '.join(chapter.get_unique_characters())}")
        
        # Show character analysis results
        print(f"\n🎭 Character Analysis Results:")
        for char_name, character in character_catalogue.characters.items():
            print(f"   {char_name}: {character.gender} - {character.description}")
        
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
        
        # Step 2: Generate audio with selected TTS
        print(f"\n🎵 Step 2: Generating complete audio with {provider_choice.title()} TTS...")
        estimated_chars = sum(len(segment.text) for segment in chapter.segments)
        cost_per_1k = 0.015 if provider_choice == "openai" else 0.30  # USD per 1k characters
        estimated_cost = (estimated_chars / 1000) * cost_per_1k
        print(
            f"⚠️  Estimated cost: ~${estimated_cost:.3f} "
            f"({estimated_chars} characters @ ${cost_per_1k:.3f}/1k)"
        )
        
        # Ask for confirmation
        response = input("Continue with audio generation? (y/N): ").strip().lower()
        if response != 'y':
            print("❌ Audio generation cancelled by user.")
            return
        
        # Build provider instance
        provider_obj = OpenAIProvider() if provider_choice == "openai" else ElevenLabsProvider()

        # Generate all audio files with character catalogue
        print(f"\n🎙️  Generating audio for all {len(chapter.segments)} segments using {provider_choice}...")
        tts_generator = TTSGenerator(
            provider=provider_obj, 
            output_dir="test_audio_output",
            character_catalogue=character_catalogue
        )
        audio_files = tts_generator.generate_audio_for_chapter(chapter)
        
        print(f"\n🎉 Test Complete!")
        print(f"📂 Check the output:")
        print(f"   📊 Chapter data: chapter_data/chapter_01/")
        print(f"   🎵 Complete chapter: test_audio_output/{provider_choice}/chapter_01_complete.mp3")
        print(f"   📁 Individual files: test_audio_output/{provider_choice}/chapter_01/")
        print(f"   📝 Playlist: test_audio_output/{provider_choice}/chapter_01/chapter_01_playlist.m3u")
        
        # Show voice assignments
        print(f"\n🎭 Voice assignments for {provider_choice}:")
        print(f"   Narrator: {tts_generator.voice_assigner.get_narrator_voice()}")
        for char_name, character in character_catalogue.characters.items():
            voice_id = character.voice_assignments.get(provider_choice, "Not assigned")
            print(f"   {char_name} ({character.gender}): {voice_id}")
        
    except FileNotFoundError:
        print("❌ test_chapter.txt not found. Make sure the file exists in the current directory.")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 