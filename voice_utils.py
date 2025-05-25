from __future__ import annotations

import json
from pathlib import Path
from typing import List

from tts_providers.base import Voice, TTSProvider

VOICE_CACHE_DIR = Path("voice_cache")
VOICE_CACHE_DIR.mkdir(exist_ok=True)

def get_voices(provider: TTSProvider) -> List[Voice]:
    """Return voice list for *provider*, using cache if available.

    If the cache file does not exist it will call provider.list_voices() and
    write the cache.
    """
    cache_path = VOICE_CACHE_DIR / f"voices_{provider.name}.json"

    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text())
            return [Voice(**item) for item in data]
        except Exception:
            # fall through to refresh cache below
            pass

    voices = provider.list_voices()
    # save
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump([v.__dict__ for v in voices], f, indent=2)
    return voices 