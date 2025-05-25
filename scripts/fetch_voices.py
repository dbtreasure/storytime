import argparse, json
from pathlib import Path

from tts_providers.openai_provider import OpenAIProvider
from tts_providers.elevenlabs_provider import ElevenLabsProvider

PROVIDERS = {
    "openai": OpenAIProvider,
    "eleven": ElevenLabsProvider,
}

VOICE_CACHE_DIR = Path("voice_cache")
VOICE_CACHE_DIR.mkdir(exist_ok=True)

def main():
    parser = argparse.ArgumentParser(
        description="Fetch voice list from provider and cache into voice_cache/"
    )
    parser.add_argument("provider", choices=PROVIDERS.keys())
    args = parser.parse_args()

    provider_cls = PROVIDERS[args.provider]
    provider = provider_cls()
    voices = provider.list_voices()

    out_path = VOICE_CACHE_DIR / f"voices_{args.provider}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump([v.__dict__ for v in voices], f, indent=2)
    print(f"✅ Cached {len(voices)} voices to {out_path}")

if __name__ == "__main__":
    main() 