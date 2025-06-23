#!/usr/bin/env python3
"""Quick integration test for URL input functionality."""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_model_validation():
    """Test Pydantic model validation for URL input."""
    from storytime.models import CreateJobRequest

    # Test URL input
    try:
        request = CreateJobRequest(
            title="Test Article",
            url="https://example.com/article",
            voice_config={
                "provider": "openai",
                "voice_id": "alloy"
            }
        )
        print("✅ URL input validation works")
        print(f"   URL: {request.url}")
        print(f"   Title: {request.title}")
    except Exception as e:
        print(f"❌ URL validation failed: {e}")
        return False

    # Test text content input
    try:
        request = CreateJobRequest(
            title="Test Text",
            content="This is a test text content that is long enough to pass validation requirements.",
            voice_config={
                "provider": "openai",
                "voice_id": "alloy"
            }
        )
        print("✅ Text content validation works")
    except Exception as e:
        print(f"❌ Text validation failed: {e}")
        return False

    # Test validation error (no input)
    try:
        request = CreateJobRequest(
            title="Invalid Request",
            voice_config={
                "provider": "openai",
                "voice_id": "alloy"
            }
        )
        print("❌ Should have failed validation")
        return False
    except Exception:
        print("✅ Validation correctly rejects missing input")

    # Test validation error (multiple inputs)
    try:
        request = CreateJobRequest(
            title="Invalid Request",
            content="Some content",
            url="https://example.com",
            voice_config={
                "provider": "openai",
                "voice_id": "alloy"
            }
        )
        print("❌ Should have failed validation")
        return False
    except Exception:
        print("✅ Validation correctly rejects multiple inputs")

    return True

def test_web_scraping_service():
    """Test web scraping service initialization."""
    try:
        from storytime.services.web_scraping import WebScrapingService

        # Mock the OpenAI API key for testing
        os.environ['OPENAI_API_KEY'] = 'test-key'

        service = WebScrapingService()
        print("✅ WebScrapingService initializes correctly")
        print(f"   Config: {service.graph_config}")

        # Test scraping enabled check
        enabled = service.is_scraping_enabled()
        print(f"✅ Scraping enabled check: {enabled}")

        return True
    except Exception as e:
        print(f"❌ WebScrapingService failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing URL Input Integration")
    print("=" * 50)

    all_passed = True

    print("\n📋 Testing Pydantic Model Validation...")
    all_passed &= test_model_validation()

    print("\n🌐 Testing Web Scraping Service...")
    all_passed &= test_web_scraping_service()

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
