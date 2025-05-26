import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import io
import sys
import os

# Ensure src is in sys.path for import
SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from storytime.api.main import app

# --- Mock API key dependency ---
from fastapi import status
from storytime.api import auth

def always_valid_api_key():
    return "test-api-key"

app.dependency_overrides[auth.get_api_key] = always_valid_api_key

client = TestClient(app)

# --- Fixtures ---
@pytest.fixture
def sample_text():
    return "\"Hello!\" said Marcus. She replied, 'Good morning.' The sun was shining."

@pytest.fixture
def sample_file(tmp_path, sample_text):
    file_path = tmp_path / "chapter.txt"
    file_path.write_text(sample_text)
    return file_path

# --- Tests ---
def test_parse_chapter_text(sample_text):
    resp = client.post("/api/v1/chapters/parse", json={"text": sample_text})
    assert resp.status_code == 200
    data = resp.json()
    assert "chapter_id" in data
    assert "segments" in data
    assert isinstance(data["segments"], list)
    assert data["segments"]


def test_parse_chapter_file(sample_file):
    with open(sample_file, "rb") as f:
        resp = client.post(
            "/api/v1/chapters/parse-file",
            files={"file": ("chapter.txt", f, "text/plain")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "chapter_id" in data
    assert "segments" in data
    assert isinstance(data["segments"], list)
    assert data["segments"]


def test_parse_with_characters(sample_text):
    resp = client.post("/api/v1/chapters/parse-with-characters", json={"text": sample_text})
    assert resp.status_code == 200
    data = resp.json()
    assert "chapter_id" in data
    assert "characters" in data
    assert isinstance(data["characters"], list)


def test_get_chapter_and_characters_flow(sample_text):
    # Parse with characters to get a chapter_id
    resp = client.post("/api/v1/chapters/parse-with-characters", json={"text": sample_text})
    assert resp.status_code == 200
    chapter_id = resp.json()["chapter_id"]

    # Get chapter data
    resp2 = client.get(f"/api/v1/chapters/{chapter_id}")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["chapter_id"] == chapter_id
    assert "segments" in data

    # Get character catalogue
    resp3 = client.get(f"/api/v1/chapters/{chapter_id}/characters")
    assert resp3.status_code == 200
    data = resp3.json()
    assert data["chapter_id"] == chapter_id
    assert "characters" in data


def test_get_chapter_not_found():
    resp = client.get("/api/v1/chapters/doesnotexist")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Chapter not found"


def test_get_characters_no_analysis(sample_text):
    # Parse chapter without character analysis
    resp = client.post("/api/v1/chapters/parse", json={"text": sample_text})
    assert resp.status_code == 200
    chapter_id = resp.json()["chapter_id"]

    # Try to get characters (should 404)
    resp2 = client.get(f"/api/v1/chapters/{chapter_id}/characters")
    assert resp2.status_code == 404
    assert resp2.json()["detail"] == "No character analysis for this chapter"


def test_generate_tts():
    resp = client.post("/api/v1/tts/generate", json={"text": "Hello world!", "provider": "openai"})
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "pending"


def test_get_job_status():
    # Create a job first
    resp = client.post("/api/v1/tts/generate", json={"text": "Hello world!"})
    job_id = resp.json()["job_id"]
    resp2 = client.get(f"/api/v1/tts/jobs/{job_id}")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["job_id"] == job_id
    assert data["status"] == "pending"


def test_download_job_audio():
    # Create a job first
    resp = client.post("/api/v1/tts/generate", json={"text": "Hello world!"})
    job_id = resp.json()["job_id"]
    resp2 = client.get(f"/api/v1/tts/jobs/{job_id}/download")
    assert resp2.status_code == 400
    assert resp2.json()["detail"] == "Audio not ready"


def test_cancel_job():
    # Create a job first
    resp = client.post("/api/v1/tts/generate", json={"text": "Hello world!"})
    job_id = resp.json()["job_id"]
    resp2 = client.delete(f"/api/v1/tts/jobs/{job_id}")
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["job_id"] == job_id
    assert data["status"] == "canceled"


def test_job_not_found():
    resp = client.get("/api/v1/tts/jobs/doesnotexist")
    assert resp.status_code == 404
    resp2 = client.get("/api/v1/tts/jobs/doesnotexist/download")
    assert resp2.status_code == 404
    resp3 = client.delete("/api/v1/tts/jobs/doesnotexist")
    assert resp3.status_code == 404 