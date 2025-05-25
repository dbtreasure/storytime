import os
import asyncio
from typing import List, Optional, Dict, Literal, cast
from pathlib import Path
import json
from models import TextSegment, Chapter, SpeakerType, CharacterCatalogue
from dotenv import load_dotenv
from pydub import AudioSegment, effects
from pydub.silence import detect_leading_silence

# Load environment variables
load_dotenv()

# Provider imports
from tts_providers.base import TTSProvider, Voice
from tts_providers.openai_provider import OpenAIProvider
from tts_providers.elevenlabs_provider import ElevenLabsProvider
from voice_utils import get_voices
from voice_assigner import VoiceAssigner

class TTSGenerator:
    def __init__(self, provider: Optional[TTSProvider] = None, output_dir: str = "audio_output", 
                 character_catalogue: Optional[CharacterCatalogue] = None):
        """Initialize with a pluggable TTS provider and character catalogue."""

        # Pick provider
        if provider is None:
            provider_name = os.getenv("TTS_PROVIDER", "openai").lower()
            if provider_name == "eleven":
                provider = ElevenLabsProvider()
            else:
                provider = OpenAIProvider()

        self.provider: TTSProvider = provider
        self.provider_name: str = getattr(provider, "name", "openai")

        # Create output directory
        self.output_dir = Path(output_dir) / self.provider_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load voice catalogue (cached)
        self._voices: list[Voice] = get_voices(self.provider)
        
        # Initialize voice assigner
        self.voice_assigner = VoiceAssigner(self.provider_name, self._voices)
        
        # Store character catalogue
        self.character_catalogue = character_catalogue or CharacterCatalogue()
    
    def select_voice(self, segment: TextSegment) -> str:
        """Select appropriate voice based on character or narrator."""
        
        # Narrator gets consistent narrator voice
        if segment.speaker_type == SpeakerType.NARRATOR:
            return self.voice_assigner.get_narrator_voice()
        
        # Character gets assigned voice based on character catalogue
        character = self.character_catalogue.get_character(segment.speaker_name)
        if character:
            return self.voice_assigner.assign_voice_to_character(character)
        
        # Fallback for unknown characters - create temporary character
        from models import Character
        temp_character = Character(
            name=segment.speaker_name,
            gender=self._infer_gender_from_hint(segment.voice_hint),
            description=f"Character from chapter dialogue"
        )
        self.character_catalogue.add_character(temp_character)
        return self.voice_assigner.assign_voice_to_character(temp_character)
    
    def _infer_gender_from_hint(self, voice_hint: Optional[str]) -> str:
        """Infer gender from voice hint."""
        if not voice_hint:
            return "unknown"
        hint_lower = voice_hint.lower()
        if "female" in hint_lower:
            return "female"
        elif "male" in hint_lower:
            return "male"
        return "unknown"
    
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
            
            # Delegate synthesis to the provider
            self.provider.synth(
                text=segment.text,
                voice=voice,
                style=instructions,
                format=response_format,
                out_path=output_path,
            )
            
            print(f"   ✅ Saved: {filename}")
            return str(output_path)
            
        except Exception as e:
            print(f"   ❌ Error generating audio for segment {segment.sequence_number}: {e}")
            raise
    
    def generate_audio_for_chapter(self, chapter: Chapter, 
                                 model: str = "gpt-4o-mini-tts", 
                                 response_format: Literal['mp3', 'opus', 'aac', 'flac', 'wav', 'pcm'] = "mp3",
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
        
        # --------------------------------------------------
        # Timing parameters (tweak as desired)
        # --------------------------------------------------
        lead_in_ms   = 200   # uniform lead-in padding per segment
        tail_ms      = 400   # uniform tail padding per segment
        crossfade_ms = 30    # overlap (in ms) when SAME speaker continues

        # Create the final audio container
        combined_audio = AudioSegment.empty()

        # Add each segment in sequence order with cleanup
        last_speaker_name: str | None = None

        for segment in chapter.segments:
            segment_key = f"segment_{segment.sequence_number}"
            if segment_key not in audio_files:
                continue

            audio_path = audio_files[segment_key]

            try:
                # Load
                seg_audio = AudioSegment.from_mp3(audio_path)

                # 1) Trim stray silence
                seg_audio = cast(AudioSegment, self.strip_silence(seg_audio, thresh=-40, chunk_size=10))

                # 2) Normalise loudness (LUFS-style)
                seg_audio = effects.normalize(seg_audio)

                # 3) Pad to uniform lead-in / tail
                seg_audio = (AudioSegment.silent(duration=lead_in_ms) +
                             seg_audio +
                             AudioSegment.silent(duration=tail_ms))

                # 4) Append: cross-fade only if SAME speaker continues
                if len(combined_audio) == 0:
                    combined_audio = seg_audio
                else:
                    if segment.speaker_name == last_speaker_name:
                        xf_ms = min(crossfade_ms,
                                     len(seg_audio) // 2,
                                     len(combined_audio) // 2)
                        combined_audio = combined_audio.append(seg_audio, crossfade=xf_ms)
                    else:
                        combined_audio += seg_audio  # no overlap, keep silence gap

                last_speaker_name = segment.speaker_name

                print(f"   ✅ Added & processed segment {segment.sequence_number}")

            except Exception as e:
                print(f"   ⚠️  Skipping segment {segment.sequence_number}: {e}")
        
        # Save the combined audio file
        chapter_filename = f"chapter_{chapter.chapter_number:02d}_complete.mp3"
        chapter_output_path = self.output_dir / chapter_filename
        
        combined_audio.export(str(chapter_output_path), format="mp3")
        
        print(f"🎵 Created complete chapter audio: {chapter_filename}")
        return str(chapter_output_path)
    
    def strip_silence(self, audio: AudioSegment, thresh: int = -40, chunk_size: int = 10) -> AudioSegment:
        """Remove leading and trailing silence from an ``AudioSegment``.

        Args:
            audio: The audio to trim.
            thresh: Volume threshold (in dBFS) below which the signal is
                     considered silence.
            chunk_size: Analysis window in milliseconds.

        Returns:
            The trimmed ``AudioSegment``.
        """
        start_trim = detect_leading_silence(audio, silence_threshold=thresh, chunk_size=chunk_size)
        end_trim = detect_leading_silence(audio.reverse(), silence_threshold=thresh, chunk_size=chunk_size)
        duration = len(audio)
        return cast(AudioSegment, audio[start_trim:duration - end_trim])


# Convenience function for quick usage
def generate_chapter_audio(chapter: Chapter, output_dir: str = "audio_output", provider: Optional[TTSProvider] = None) -> Dict[str, str]:
    """Quick convenience function using default or supplied provider."""
    generator = TTSGenerator(provider=provider, output_dir=output_dir)
    return generator.generate_audio_for_chapter(chapter) 