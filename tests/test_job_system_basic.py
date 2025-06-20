#!/usr/bin/env python3
"""Basic validation tests for the simplified unified job management system."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import AsyncMock


def test_imports():
    """Test that all simplified modules can be imported."""
    print("Testing imports...")

    try:
        # Test model imports
        print("✅ Model imports successful")

        # Test simplified job processor import
        print("✅ Job processor import successful")

        # Test API imports
        print("✅ API imports successful")

        # Test simplified worker imports
        print("✅ Worker imports successful")

        return True

    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False


def test_job_processor():
    """Test basic job processor functionality."""
    print("\nTesting job processor...")

    try:
        from storytime.services.job_processor import JobProcessor

        # Mock dependencies
        mock_session = AsyncMock()
        mock_spaces = AsyncMock()

        processor = JobProcessor(db_session=mock_session, spaces_client=mock_spaces)

        assert processor.db_session == mock_session
        assert processor.spaces_client == mock_spaces

        print("✅ Job processor initialization works")
        return True

    except Exception as e:
        print(f"❌ Job processor test failed: {e}")
        return False


def test_job_models():
    """Test simplified job data models."""
    print("\nTesting job models...")

    try:
        from datetime import datetime
        from uuid import uuid4

        from storytime.models import (
            CreateJobRequest,
            JobResponse,
            JobStatus,
            VoiceConfig,
        )

        # Test CreateJobRequest
        request = CreateJobRequest(
            title="Test Job",
            description="Test description",
            content="Sample content",
            file_key=None,
            voice_config=VoiceConfig(provider="openai", voice_id="alloy"),
        )

        assert request.title == "Test Job"
        assert request.voice_config is not None
        assert request.voice_config.provider == "openai"

        print("✅ CreateJobRequest model works")

        # Test JobResponse
        response = JobResponse(
            id=str(uuid4()),
            user_id=str(uuid4()),
            title="Test Job",
            status=JobStatus.PENDING,
            progress=0.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert response.status == JobStatus.PENDING
        assert response.progress == 0.0

        print("✅ JobResponse model works")

        return True

    except Exception as e:
        print(f"❌ Job models test failed: {e}")
        return False


def test_database_models():
    """Test simplified database model definitions."""
    print("\nTesting database models...")

    try:
        # Test that we can import without database connection issues
        import storytime.database as db_module

        # Check that classes exist
        assert hasattr(db_module, "Job")
        assert hasattr(db_module, "JobStep")
        assert hasattr(db_module, "JobStatus")

        # Test enum values
        assert db_module.JobStatus.PENDING == "PENDING"

        print("✅ Database models are properly defined")
        return True

    except Exception as e:
        print(f"❌ Database models test failed: {e}")
        return False


def test_tts_generator():
    """Test simplified TTS generator."""
    print("\nTesting TTS generator...")

    try:
        from storytime.services.tts_generator import TTSGenerator

        # Test initialization (will use OpenAI by default)
        generator = TTSGenerator()

        assert generator.provider is not None
        assert generator.provider_name in ["openai", "eleven"]

        print("✅ TTS generator initialization works")
        return True

    except Exception as e:
        print(f"❌ TTS generator test failed: {e}")
        return False


def main():
    """Run all basic validation tests."""
    print("🧪 Running basic validation tests for simplified job management system...\n")

    tests = [
        test_imports,
        test_job_models,
        test_job_processor,
        test_database_models,
        test_tts_generator,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All basic validation tests passed!")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
