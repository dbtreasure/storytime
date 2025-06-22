from __future__ import annotations

from storytime.infrastructure.tts.base import TTSProvider, Voice


def get_voices(provider: TTSProvider) -> list[Voice]:
    """Return the list of voices from *provider*."""

    return provider.list_voices()
