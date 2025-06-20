#!/usr/bin/env python3
"""Simple test script to verify streaming functionality."""

import asyncio

from storytime.infrastructure.spaces import SpacesClient


async def test_streaming_urls():
    """Test that streaming URLs have proper format."""
    print("Testing streaming URL generation...")

    client = SpacesClient()
    test_key = "test/audio.mp3"

    # Generate both types of URLs
    download_url = await client.get_presigned_download_url(test_key)
    streaming_url = await client.get_streaming_url(test_key)

    print(f"\nDownload URL: {download_url[:100]}...")
    print(f"Streaming URL: {streaming_url[:100]}...")

    # Check URL differences
    has_download_params = "response-content" in download_url
    has_streaming_params = "response-content-disposition=inline" in streaming_url
    urls_different = download_url != streaming_url

    print("\nResults:")
    print(f"  Download URL has response params: {has_download_params}")
    print(f"  Streaming URL has response params: {has_streaming_params}")
    print(f"  URLs are different: {urls_different}")

    # Expected results
    if not has_download_params and has_streaming_params and urls_different:
        print("✅ Streaming URL generation working correctly!")
    else:
        print("❌ Streaming URL generation may have issues")

    return has_streaming_params and urls_different


if __name__ == "__main__":
    asyncio.run(test_streaming_urls())
