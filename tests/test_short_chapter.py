import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add src to path to allow running this script directly before proper packaging
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Import provider classes from their new location
from storytime.infrastructure.tts import ElevenLabsProvider, OpenAIProvider
from storytime.services import TTSGenerator
from storytime.workflows.chapter_parsing import workflow as chapter_workflow


async def main():
    # ---------------- CLI ----------------
    argp = argparse.ArgumentParser(description="Run short-chapter TTS pipeline with selectable provider.")
    argp.add_argument("--tts", choices=["openai", "eleven"], default="openai", help="TTS backend to use")
    argp.add_argument("--model", choices=["gpt-4o-mini-tts", "tts-1", "tts-1-hd"], default="gpt-4o-mini-tts", help="TTS model to use (OpenAI: tts-1, tts-1-hd, gpt-4o-mini-tts)")
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

        # Read chapter text
        chapter_text_path = SCRIPT_DIR / "fixtures" / "test_chapter.txt"
        with open(chapter_text_path, encoding='utf-8') as f:
            chapter_text = f.read()

        # Use Junjo workflow for parsing
        await chapter_workflow.store.set_state({
            "chapter_text": chapter_text,
            "chapter_number": 1,
            "title": "A Business Meeting",
        })
        await chapter_workflow.execute()
        state = await chapter_workflow.store.get_state()
        chapter = state.chapter
        character_catalogue = state.character_catalogue

        if chapter:
            print(f"✅ Parsed Chapter {chapter.chapter_number}: {chapter.title}")
            print(f"   📊 {len(chapter.segments)} segments")
            print(f"   🎭 Characters: {', '.join(chapter.get_unique_characters())}")
        else:
            print("❌ No chapter parsed.")

        # Show character analysis results
        print("\n🎭 Character Analysis Results:")
        if character_catalogue and hasattr(character_catalogue, 'characters') and isinstance(character_catalogue.characters, dict) and character_catalogue.characters:
            for char_name, character in character_catalogue.characters.items():
                print(f"   {char_name}: {character.gender} - {character.description}")
        else:
            print("   No characters found.")

        # Show what was parsed
        print("\n📝 Parsed segments:")
        if chapter and chapter.segments:
            for segment in chapter.segments:
                print(f"   {segment.sequence_number}. {segment.speaker_name}: {segment.text[:80]}{'...' if len(segment.text) > 80 else ''}")
        else:
            print("   No segments found.")

        # Step 2: Generate audio with selected TTS
        if chapter and chapter.segments:
            print(f"\n🎵 Step 2: Generating complete audio with {provider_choice.title()} TTS (model: {args.model})...")
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
                output_dir=str(SCRIPT_DIR.parent / "output" / f"{provider_choice}-{args.model}"),
                character_catalogue=character_catalogue
            )
            audio_files = tts_generator.generate_audio_for_chapter(chapter, model=args.model)

            print("\n🎉 Test Complete!")
            print("📂 Check the output:")
            chapter_data_output = SCRIPT_DIR.parent / "output" / f"{provider_choice}-{args.model}" / "chapter_data" / "chapter_01"
            complete_audio_output = SCRIPT_DIR.parent / "output" / f"{provider_choice}-{args.model}" / "chapter_01_complete.mp3"
            individual_files_output = SCRIPT_DIR.parent / "output" / f"{provider_choice}-{args.model}" / "chapter_01"
            playlist_output = SCRIPT_DIR.parent / "output" / f"{provider_choice}-{args.model}" / "chapter_01" / "chapter_01_playlist.m3u"

            print(f"   📊 Chapter data: {chapter_data_output}")
            print(f"   🎵 Complete chapter: {complete_audio_output}")
            print(f"   📁 Individual files: {individual_files_output}/")
            print(f"   📝 Playlist: {playlist_output}")

            # Show voice assignments
            print(f"\n🎭 Voice assignments for {provider_choice}:")
            print(f"   Narrator: {tts_generator.voice_assigner.get_narrator_voice()}")
            characters_dict = getattr(character_catalogue, 'characters', None)
            if isinstance(characters_dict, dict) and characters_dict:
                for char_name, character in characters_dict.items():
                    voice_id = character.voice_assignments.get(provider_choice, "Not assigned")
                    print(f"   {char_name} ({character.gender}): {voice_id}")
            else:
                print("   No characters found.")
        else:
            print("❌ Skipping TTS generation: No valid chapter parsed.")

    except FileNotFoundError:
        print("❌ test_chapter.txt not found. Make sure the file exists in the current directory.")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
