from __future__ import annotations

import json
from pathlib import Path

# Now imports from the new location
from storytime.infrastructure.tts.base import TTSProvider, Voice

# Sensible default for user-level config/cache, not inside `src`
CACHE_DIR_NAME = ".storytime_cache"
VOICE_CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "voice_cache"


def get_voices(provider: TTSProvider) -> list[Voice]:
    """Return voice list for *provider*, using cache if available.

    Cache is stored in `~/.storytime_cache/voice_cache/voices_<provider_name>.json`.
    If the cache file does not exist it will call provider.list_voices()
    and write the cache for next time.
    """
    cache_path = VOICE_CACHE_DIR / f"voices_{provider.name}.json"

    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            return [Voice(**item) for item in data]
        except Exception:  # noqa: BLE001, S110
            # Malformed cache, fall through to refresh.
            pass

    # Cache miss or error, fetch fresh from provider
    voices = provider.list_voices()

    # Save to cache
    with cache_path.open("w", encoding="utf-8") as f:
        # Use `model_dump` if Voice objects are Pydantic, else `__dict__`
        # For dataclasses, `asdict` from `dataclasses` module is an option
        json.dump([v.__dict__ for v in voices], f, indent=2)
    return voices 