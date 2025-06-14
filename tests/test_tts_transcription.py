import os
import re
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pytest
import requests

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


BASE_URL = "http://localhost:8000"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
pytestmark = pytest.mark.skipif(not OPENAI_API_KEY, reason="Requires OpenAI API key")

if OPENAI_API_KEY:
    import openai

    openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
else:
    openai_client = None

# --- Gemini setup (optional) ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    try:
        import google.generativeai as genai

        genai.configure(api_key=GOOGLE_API_KEY)  # type: ignore[attr-defined]

        def gemini_similarity(a: str, b: str) -> float:
            """Return cosine similarity between text embeddings using Gemini."""
            import numpy as np  # type: ignore

            def embed(text: str):
                resp = genai.embed_content(model="models/embedding-001", content=text)  # type: ignore[attr-defined]
                # `resp` may be dict or object with .embedding
                embedding = (
                    resp.get("embedding")
                    if isinstance(resp, dict)
                    else getattr(resp, "embedding", None)
                )
                if embedding is None:
                    raise ValueError("Failed to get embedding from Gemini response")
                return np.array(embedding, dtype=float)

            vec_a, vec_b = embed(a), embed(b)
            norm = lambda v: v / (np.linalg.norm(v) + 1e-8)
            v1, v2 = norm(vec_a), norm(vec_b)
            return float(np.dot(v1, v2))

        _gemini_embed_model = True

    except Exception:  # pragma: no cover
        _gemini_embed_model = None
else:
    _gemini_embed_model = None


def wait_for_job(job_id, timeout=60):
    """Wait for a job to complete using the unified job API."""
    for _ in range(timeout):
        resp = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}")
        if resp.status_code == 200:
            status = resp.json()["status"]
            if status == "COMPLETED":
                return True
            elif status == "FAILED":
                pytest.fail(f"TTS job failed: {resp.json().get('error_message')}")
        time.sleep(1)
    pytest.fail("TTS job did not complete in time")


def test_tts_to_transcription():
    if not openai_client:
        pytest.skip("OpenAI client not available")
    # Read the more substantial test chapter text
    chapter_path = Path(__file__).parent / "fixtures" / "test_chapter.txt"
    with open(chapter_path, encoding="utf-8") as f:
        text = f.read().strip()
    
    # Submit TTS job via unified job API
    job_request = {
        "title": "TTS Transcription Test",
        "description": "Integration test for TTS to transcription pipeline",
        "content": text,
        "source_type": "TEXT",
        "job_type": "SINGLE_VOICE",
        "voice_config": {
            "provider": "openai",
            "voice_id": "alloy"
        }
    }
    resp = requests.post(f"{BASE_URL}/api/v1/jobs", json=job_request)
    assert resp.status_code == 200
    job_id = resp.json()["id"]
    
    # Wait for job to complete
    wait_for_job(job_id)
    
    # Download audio
    resp2 = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}/audio")
    assert resp2.status_code == 200
    # The unified API returns a download URL, not direct content
    download_url = resp2.json()["download_url"]
    
    # Download the actual audio file
    audio_resp = requests.get(download_url)
    assert audio_resp.status_code == 200
    # Save audio to temp file
    audio_path = Path("/tmp/tts_test_audio.mp3")
    with open(audio_path, "wb") as f:
        f.write(audio_resp.content)
    # Transcribe with OpenAI
    with open(audio_path, "rb") as f:
        transcript = openai_client.audio.transcriptions.create(model="whisper-1", file=f)
    # Check transcription
    transcribed_text = transcript.text.strip().lower()

    # Allow for minor differences in whitespace and punctuation
    def normalize(s: str) -> str:
        """Lowercase, remove punctuation/extra whitespace, strip accents."""
        s = unicodedata.normalize("NFD", s)
        s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")  # remove accents
        s = re.sub(r"\W+", " ", s).strip().lower()
        return s

    norm_orig = normalize(text)
    norm_trans = normalize(transcribed_text)

    # Require that at least 90% of the shorter string matches the longer one
    ratio = SequenceMatcher(None, norm_orig, norm_trans).ratio()

    # If Gemini embeddings are available, combine with cosine similarity
    if _gemini_embed_model:
        cos_sim = gemini_similarity(norm_orig, norm_trans)
        assert cos_sim > 0.9, (
            f"Gemini embedding similarity too low (cos={cos_sim:.2f})\n--- ORIGINAL ---\n{norm_orig[:400]}...\n--- TRANSCRIBED ---\n{norm_trans[:400]}..."
        )
    else:
        assert ratio > 0.9, (
            f"Transcription similarity too low (ratio={ratio:.2f})\n--- ORIGINAL ---\n{norm_orig[:400]}...\n--- TRANSCRIBED ---\n{norm_trans[:400]}..."
        )
