import openai
import os
import asyncio
from typing import List, Optional, Dict, Literal
from pathlib import Path
import json
from models import TextSegment, Chapter, SpeakerType
from dotenv import load_dotenv
from pydub import AudioSegment

# Load environment variables
load_dotenv()

class TTSGenerator:
    def __init__(self, api_key: Optional[str] = None, output_dir: str = "audio_output"):
        """Initialize the OpenAI TTS client."""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        # Set up OpenAI client
        openai.api_key = self.api_key
        self.client = openai.OpenAI(api_key=self.api_key)
        
        # Create output directory
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Voice mapping for different character types - using proper literal values
        self.voice_mapping: Dict[str, Literal['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']] = {
            "narrator": "echo",  # Neutral, clear voice for narration
            "male": "onyx",      # Deep male voice
            "female": "nova",    # Clear female voice  
            "elderly": "fable",  # Distinguished voice
            "default": "alloy"   # Fallback voice
        }
    
    def select_voice(self, segment: TextSegment) -> Literal['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']:
        """Select appropriate voice based on segment metadata."""
        if segment.speaker_type == SpeakerType.NARRATOR:
            return self.voice_mapping["narrator"]
        
        # For character dialogue, use voice hints if available
        voice_hint = segment.voice_hint or ""
        voice_hint_lower = voice_hint.lower()
        
        if "male" in voice_hint_lower and "female" not in voice_hint_lower:
            return self.voice_mapping["male"]
        elif "female" in voice_hint_lower:
            return self.voice_mapping["female"]
        elif any(age_word in voice_hint_lower for age_word in ["elderly", "old", "aged"]):
            return self.voice_mapping["elderly"]
        else:
            return self.voice_mapping["default"]
    
    def get_chapter_dir(self, chapter_number: int) -> Path:
        """Get the directory path for a specific chapter."""
        chapter_dir = self.output_dir / f"chapter_{chapter_number:02d}"
        chapter_dir.mkdir(exist_ok=True)
        return chapter_dir
    
    def get_audio_filename(self, segment: TextSegment, chapter_number: int) -> str:
        """Generate consistent filename for audio segment."""
        # Sanitize speaker name for filename
        speaker_safe = "".join(c for c in segment.speaker_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        speaker_safe = speaker_safe.replace(' ', '_')
        
        return f"ch{chapter_number:02d}_{segment.sequence_number:03d}_{speaker_safe}.mp3"
    

    
    def generate_audio_for_segment(self, segment: TextSegment, chapter_number: int, chapter: Chapter,
                                 model: str = "gpt-4o-mini-tts", response_format: Literal['mp3', 'opus', 'aac', 'flac', 'wav', 'pcm'] = "mp3") -> str:
        """Generate audio for a single text segment."""
        try:
            # Select appropriate voice
            voice = self.select_voice(segment)
            
            # Use pre-generated instructions from segment or fallback
            instructions = segment.instruction or f"Deliver this {segment.speaker_type.value} text with appropriate tone and emotion."
            
            # Generate filename and put in chapter directory
            filename = self.get_audio_filename(segment, chapter_number)
            chapter_dir = self.get_chapter_dir(chapter_number)
            output_path = chapter_dir / filename
            
            print(f"🎙️  Generating audio for segment {segment.sequence_number}: [{segment.speaker_name}]")
            print(f"   Voice: {voice} | Text: {segment.text[:100]}{'...' if len(segment.text) > 100 else ''}")
            print(f"   Instructions: {instructions[:150]}{'...' if len(instructions) > 150 else ''}")
            
            # Call OpenAI TTS API with instructions
            response = self.client.audio.speech.create(
                model=model,
                voice=voice,
                input=segment.text,
                response_format=response_format,
                instructions=instructions
            )
            
            # Save audio file
            with open(output_path, 'wb') as f:
                f.write(response.content)
            
            print(f"   ✅ Saved: {filename}")
            return str(output_path)
            
        except Exception as e:
            print(f"   ❌ Error generating audio for segment {segment.sequence_number}: {e}")
            raise
    
    def generate_audio_for_chapter(self, chapter: Chapter, 
                                 model: str = "gpt-4o-mini-tts", 
                                 response_format: str = "mp3",
                                 max_concurrent: int = 3) -> Dict[str, str]:
        """Generate audio files for all segments in a chapter."""
        print(f"\n🎵 Generating audio for Chapter {chapter.chapter_number}: {chapter.title}")
        print(f"📊 Total segments: {len(chapter.segments)}")
        print(f"🎭 Characters: {', '.join(chapter.get_unique_characters())}")
        
        audio_files = {}
        
        # Process segments sequentially to avoid rate limits
        for i, segment in enumerate(chapter.segments, 1):
            try:
                audio_path = self.generate_audio_for_segment(
                    segment, chapter.chapter_number, chapter, model, response_format
                )
                audio_files[f"segment_{segment.sequence_number}"] = audio_path
                
                # Progress indicator
                print(f"   Progress: {i}/{len(chapter.segments)} ({i/len(chapter.segments)*100:.1f}%)")
                
            except Exception as e:
                print(f"   ⚠️  Skipping segment {segment.sequence_number} due to error: {e}")
                continue
        
        print(f"\n✅ Chapter {chapter.chapter_number} audio generation complete!")
        print(f"📁 Generated {len(audio_files)} individual files")
        
        # Create playlist
        playlist_path = self.create_playlist(chapter, audio_files)
        
        # Stitch all segments into a single file
        complete_audio_path = self.stitch_chapter_audio(chapter, audio_files)
        
        print(f"📂 Chapter {chapter.chapter_number} files:")
        print(f"   🎵 Complete audio: {Path(complete_audio_path).name}")
        print(f"   📁 Individual files: chapter_{chapter.chapter_number:02d}/")
        print(f"   📝 Playlist: {Path(playlist_path).name}")
        
        return audio_files
    
    def create_playlist(self, chapter: Chapter, audio_files: Dict[str, str]) -> str:
        """Create a playlist file for the chapter's audio segments."""
        playlist_filename = f"chapter_{chapter.chapter_number:02d}_playlist.m3u"
        chapter_dir = self.get_chapter_dir(chapter.chapter_number)
        playlist_path = chapter_dir / playlist_filename
        
        with open(playlist_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            f.write(f"# Chapter {chapter.chapter_number}: {chapter.title}\n")
            
            for segment in chapter.segments:
                segment_key = f"segment_{segment.sequence_number}"
                if segment_key in audio_files:
                    audio_file = Path(audio_files[segment_key]).name
                    duration_estimate = len(segment.text) / 150 * 60  # Rough estimate: 150 words per minute
                    
                    f.write(f"#EXTINF:{duration_estimate:.1f},{segment.speaker_name} - {segment.text[:50]}...\n")
                    f.write(f"{audio_file}\n")
        
        print(f"📝 Created playlist: {playlist_filename}")
        return str(playlist_path)
    
    def stitch_chapter_audio(self, chapter: Chapter, audio_files: Dict[str, str]) -> str:
        """Combine all segment audio files into a single chapter MP3."""
        print(f"\n🔗 Stitching audio segments into single chapter file...")
        
        # Create the final audio
        combined_audio = AudioSegment.empty()
        
        # Add each segment in sequence order
        for segment in chapter.segments:
            segment_key = f"segment_{segment.sequence_number}"
            if segment_key in audio_files:
                audio_path = audio_files[segment_key]
                try:
                    segment_audio = AudioSegment.from_mp3(audio_path)
                    combined_audio += segment_audio
                    print(f"   ✅ Added segment {segment.sequence_number}")
                except Exception as e:
                    print(f"   ⚠️  Skipping segment {segment.sequence_number}: {e}")
        
        # Save the combined audio file
        chapter_filename = f"chapter_{chapter.chapter_number:02d}_complete.mp3"
        chapter_output_path = self.output_dir / chapter_filename
        
        combined_audio.export(str(chapter_output_path), format="mp3")
        
        print(f"🎵 Created complete chapter audio: {chapter_filename}")
        return str(chapter_output_path)
    


# Convenience function for quick usage
def generate_chapter_audio(chapter: Chapter, output_dir: str = "audio_output", 
                         api_key: Optional[str] = None, model: str = "gpt-4o-mini-tts") -> Dict[str, str]:
    """Quick function to generate audio for a chapter without creating a generator instance."""
    generator = TTSGenerator(api_key=api_key, output_dir=output_dir)
    audio_files = generator.generate_audio_for_chapter(chapter, model=model)
    return audio_files 