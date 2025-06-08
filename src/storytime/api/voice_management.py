import hashlib
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from storytime.infrastructure.tts import ElevenLabsProvider, OpenAIProvider
from storytime.models import CharacterCatalogue

router = APIRouter(prefix="/api/v1", tags=["Voice Management"])


# --- Models ---
class VoiceOut(BaseModel):
    id: str
    name: str
    gender: str | None
    description: str | None


class VoiceAssignmentRequest(BaseModel):
    provider: str
    voice_id: str


class VoicePreviewRequest(BaseModel):
    provider: str
    voice_id: str
    text: str | None = "This is a sample of the selected voice."


# --- In-memory character catalogue for now ---
# (In production, this would be persistent or loaded per project/session)
character_catalogue = CharacterCatalogue()


# --- Endpoints ---
@router.get("/voices", response_model=dict)
def list_voices():
    """List all available voices for each provider."""
    providers = {
        "openai": OpenAIProvider(),
        "elevenlabs": ElevenLabsProvider(),
    }
    result = {}
    for name, provider in providers.items():
        voices = provider.list_voices()
        result[name] = [VoiceOut(**v.__dict__) for v in voices]
    return result


@router.post("/characters/{character_id}/voice")
def assign_voice(character_id: str, req: VoiceAssignmentRequest):
    """Assign a specific voice to a character for a provider."""
    character = character_catalogue.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    character.voice_assignments[req.provider] = req.voice_id
    return {"character_id": character_id, "provider": req.provider, "voice_id": req.voice_id}


@router.get("/characters/{character_id}/voice")
def get_voice_assignment(character_id: str, provider: str):
    """Get the current voice assignment for a character."""
    character = character_catalogue.get_character(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    voice_id = character.voice_assignments.get(provider)
    if not voice_id:
        raise HTTPException(status_code=404, detail="No voice assigned for this provider")
    return {"character_id": character_id, "provider": provider, "voice_id": voice_id}


@router.post("/voices/preview")
def preview_voice(req: VoicePreviewRequest):
    """Generate a short audio sample for a given voice and text."""
    # Validate provider
    providers = {
        "openai": OpenAIProvider(),
        "elevenlabs": ElevenLabsProvider(),
    }
    provider = providers.get(req.provider.lower())
    if not provider:
        raise HTTPException(status_code=400, detail="Unknown provider")

    # Hash text for unique filename
    text = req.text or "This is a sample of the selected voice."
    text_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    previews_dir = Path("audio_output") / req.provider.lower() / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    out_path = previews_dir / f"{req.voice_id}_{text_hash}.mp3"

    # Only synthesize if file doesn't exist
    if not out_path.exists():
        provider.synth(
            text=text,
            voice=req.voice_id,
            style=None,
            format="mp3",
            out_path=out_path,
        )

    # Return a direct file response (or a URL if static serving is set up)
    return FileResponse(
        out_path,
        media_type="audio/mpeg",
        filename=out_path.name,
    )
