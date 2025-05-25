from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, cast

from dotenv import load_dotenv
from pydub import AudioSegment, effects
from pydub.silence import detect_leading_silence

# Provider imports are now from the new infrastructure paths
from storytime.infrastructure.tts import (  # __init__ re-exports these
    ElevenLabsProvider,
    OpenAIProvider,
    TTSProvider,
    Voice,
)
from storytime.infrastructure.voice_utils import get_voices
from storytime.models import Chapter, CharacterCatalogue, SpeakerType, TextSegment
from storytime.services.voice_assigner import VoiceAssigner

load_dotenv()


class TTSGenerator:
    """Generate audio files for chapters using pluggable TTS providers."""

    def __init__(
        self,
        provider: TTSProvider | None = None,
        output_dir: str = "audio_output",
        character_catalogue: CharacterCatalogue | None = None,
    ) -> None:
        # Select provider based on env or param
        if provider is None:
            provider_name = os.getenv("TTS_PROVIDER", "openai").lower()
            provider = ElevenLabsProvider() if provider_name == "eleven" else OpenAIProvider()

        self.provider: TTSProvider = provider
        self.provider_name: str = getattr(provider, "name", "openai")

        # Destination path: e.g. audio_output/openai/
        self.output_dir = Path(output_dir) / self.provider_name
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Cache voices
        self._voices: list[Voice] = get_voices(self.provider)
        self.voice_assigner = VoiceAssigner(self.provider_name, self._voices)

        self.character_catalogue = character_catalogue or CharacterCatalogue()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def generate_audio_for_segment(
        self,
        segment: TextSegment,
        chapter_number: int,
        chapter: Chapter | None = None,
        *,
        model: str = "gpt-4o-mini-tts",
        response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "mp3",
    ) -> str:
        """Generate audio for a *single* `segment` and return the output path."""

        # Choose voice
        voice = self.select_voice(segment)

        instructions = segment.instruction or (
            f"Deliver this {segment.speaker_type.value} text with appropriate tone and emotion."
        )

        filename = self.get_audio_filename(segment, chapter_number)
        chapter_dir = self.get_chapter_dir(chapter_number)
        output_path = chapter_dir / filename

        print(
            f"🎙️  Generating audio for segment {segment.sequence_number}: "
            f"[{segment.speaker_name}]"
        )
        print(
            f"   Voice: {voice} | Text: {segment.text[:100]}"
            f"{'...' if len(segment.text) > 100 else ''}"
        )
        print(
            f"   Instructions: {instructions[:150]}"
            f"{'...' if len(instructions) > 150 else ''}"
        )

        self.provider.synth(
            text=segment.text,
            voice=voice,
            style=instructions,
            format=response_format,
            out_path=output_path,
        )

        print(f"   ✅ Saved: {filename}")
        return str(output_path)

    def generate_audio_for_chapter(
        self,
        chapter: Chapter,
        *,
        model: str = "gpt-4o-mini-tts",
        response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = "mp3",
    ) -> dict[str, str]:
        """Generate audio for every segment in *chapter*. Returns dict of segment key → file path."""

        print(f"\n🎵 Generating audio for Chapter {chapter.chapter_number}: {chapter.title}")
        print(f"📊 Total segments: {len(chapter.segments)}")
        print(f"🎭 Characters: {', '.join(chapter.get_unique_characters())}")

        audio_files: dict[str, str] = {}
        for idx, segment in enumerate(chapter.segments, 1):
            try:
                path = self.generate_audio_for_segment(
                    segment, chapter.chapter_number, chapter, model=model, response_format=response_format
                )
                audio_files[f"segment_{segment.sequence_number}"] = path
                print(
                    f"   Progress: {idx}/{len(chapter.segments)} "
                    f"({idx/len(chapter.segments)*100:.1f}%)"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"   ⚠️  Skipping segment {segment.sequence_number}: {exc}")
                continue

        print(f"\n✅ Chapter {chapter.chapter_number} audio generation complete! ({len(audio_files)} files)")

        playlist_path = self.create_playlist(chapter, audio_files)
        _ = self.stitch_chapter_audio(chapter, audio_files)
        print(f"📝 Playlist: {Path(playlist_path).name}")
        return audio_files

    # ------------------------------------------------------------------
    # Voice assignment helpers
    # ------------------------------------------------------------------
    def select_voice(self, segment: TextSegment) -> str:  # noqa: D401
        """Return a voice ID for *segment* based on character/narrator logic."""

        if segment.speaker_type == SpeakerType.NARRATOR:
            return self.voice_assigner.get_narrator_voice()

        character = self.character_catalogue.get_character(segment.speaker_name)
        if character:
            return self.voice_assigner.assign_voice_to_character(character)

        # Unknown character – create temporary entry to track assignments
        from storytime.models import Character

        temp = Character(
            name=segment.speaker_name,
            gender=self._infer_gender_from_hint(segment.voice_hint),
            description="Character from chapter dialogue",
        )
        self.character_catalogue.add_character(temp)
        return self.voice_assigner.assign_voice_to_character(temp)

    def _infer_gender_from_hint(self, hint: str | None) -> str:
        if not hint:
            return "unknown"
        hint = hint.lower()
        if "female" in hint:
            return "female"
        if "male" in hint:
            return "male"
        return "unknown"

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    def get_chapter_dir(self, chapter_number: int) -> Path:
        path = self.output_dir / f"chapter_{chapter_number:02d}"
        path.mkdir(exist_ok=True)
        return path

    def get_audio_filename(self, segment: TextSegment, chapter_number: int) -> str:
        safe_name = "".join(c for c in segment.speaker_name if c.isalnum() or c in (" ", "-", "_"))
        safe_name = safe_name.replace(" ", "_")
        return f"ch{chapter_number:02d}_{segment.sequence_number:03d}_{safe_name}.mp3"

    # ------------------------------------------------------------------
    # Playlist & stitching helpers (unchanged)
    # ------------------------------------------------------------------
    def create_playlist(self, chapter: Chapter, audio_files: dict[str, str]) -> str:
        playlist_filename = f"chapter_{chapter.chapter_number:02d}_playlist.m3u"
        chapter_dir = self.get_chapter_dir(chapter.chapter_number)
        playlist_path = chapter_dir / playlist_filename

        with playlist_path.open("w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"# Chapter {chapter.chapter_number}: {chapter.title}\n")
            for segment in chapter.segments:
                key = f"segment_{segment.sequence_number}"
                if key in audio_files:
                    audio_file = Path(audio_files[key]).name
                    duration = len(segment.text) / 150 * 60  # ~150 wpm
                    f.write(f"#EXTINF:{duration:.1f},{segment.speaker_name} - {segment.text[:50]}...\n")
                    f.write(f"{audio_file}\n")
        print(f"📝 Created playlist: {playlist_filename}")
        return str(playlist_path)

    def stitch_chapter_audio(self, chapter: Chapter, audio_files: dict[str, str]) -> str:
        print("\n🔗 Stitching audio segments into single chapter file…")

        lead_in_ms = 200
        tail_ms = 400
        crossfade_ms = 30

        combined = AudioSegment.empty()
        last_speaker: str | None = None

        for segment in chapter.segments:
            key = f"segment_{segment.sequence_number}"
            if key not in audio_files:
                continue
            audio_path = audio_files[key]
            try:
                seg_audio = AudioSegment.from_mp3(audio_path)
                seg_audio = cast(AudioSegment, self.strip_silence(seg_audio, thresh=-40, chunk_size=10))
                seg_audio = effects.normalize(seg_audio)
                seg_audio = (
                    AudioSegment.silent(duration=lead_in_ms)
                    + seg_audio
                    + AudioSegment.silent(duration=tail_ms)
                )
                if len(combined) == 0:
                    combined = seg_audio
                else:
                    if segment.speaker_name == last_speaker:
                        xf = min(crossfade_ms, len(seg_audio) // 2, len(combined) // 2)
                        combined = combined.append(seg_audio, crossfade=xf)
                    else:
                        combined += seg_audio
                last_speaker = segment.speaker_name
                print(f"   ✅ Added & processed segment {segment.sequence_number}")
            except Exception as exc:  # noqa: BLE001
                print(f"   ⚠️  Skipping segment {segment.sequence_number}: {exc}")
                continue

        output = self.output_dir / f"chapter_{chapter.chapter_number:02d}_complete.mp3"
        combined.export(str(output), format="mp3")
        print(f"🎵 Created complete chapter audio: {output.name}")
        return str(output)

    @staticmethod
    def strip_silence(
        audio: AudioSegment, *, thresh: int = -40, chunk_size: int = 10
    ) -> AudioSegment:
        start = detect_leading_silence(audio, silence_threshold=thresh, chunk_size=chunk_size)
        end = detect_leading_silence(audio.reverse(), silence_threshold=thresh, chunk_size=chunk_size)
        return cast(AudioSegment, audio[start : len(audio) - end])


# Convenience wrapper

def generate_chapter_audio(
    chapter: Chapter,
    *,
    output_dir: str = "audio_output",
    provider: TTSProvider | None = None,
) -> dict[str, str]:
    generator = TTSGenerator(provider=provider, output_dir=output_dir)
    return generator.generate_audio_for_chapter(chapter) 