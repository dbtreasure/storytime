import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from storytime.api.main import app

client = TestClient(app)


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