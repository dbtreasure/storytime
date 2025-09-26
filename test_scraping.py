#!/usr/bin/env python3
"""Test the new web scraping implementation."""

import requests
import json
import time

# API endpoint
BASE_URL = "http://localhost:8000"

# Test article URL (use the one that was previously failing)
TEST_URL = "https://www.newyorker.com/magazine/2025/09/30/the-self-driving-car-wars"

# Login to get JWT token
login_data = {
    "email": "test@example.com",  # Replace with your test account
    "password": "testpass123"  # Replace with your test password
}

print("Logging in...")
login_response = requests.post(
    f"{BASE_URL}/api/v1/auth/login",
    json=login_data
)

if login_response.status_code != 200:
    print(f"Login failed: {login_response.status_code}")
    print(login_response.text)
    exit(1)

auth_data = login_response.json()
token = auth_data["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print(f"Logged in successfully")

# Submit web scraping job
print(f"\nSubmitting web scraping job for: {TEST_URL}")
job_data = {
    "url": TEST_URL,
    "tts_provider": "openai",
    "voice": "alloy"
}

job_response = requests.post(
    f"{BASE_URL}/api/v1/jobs/url",
    json=job_data,
    headers=headers
)

if job_response.status_code != 200:
    print(f"Job submission failed: {job_response.status_code}")
    print(job_response.text)
    exit(1)

job = job_response.json()
job_id = job["job_id"]
print(f"Job submitted successfully: {job_id}")

# Monitor job status
print("\nMonitoring job progress...")
while True:
    status_response = requests.get(
        f"{BASE_URL}/api/v1/jobs/{job_id}",
        headers=headers
    )

    if status_response.status_code != 200:
        print(f"Failed to get job status: {status_response.status_code}")
        break

    job_status = status_response.json()
    current_status = job_status["status"]
    current_step = job_status.get("current_step", "")

    print(f"Status: {current_status} - Step: {current_step}")

    if current_status in ["completed", "failed"]:
        if current_status == "completed":
            print(f"\n✅ Job completed successfully!")
            print(f"Character count: {job_status.get('metadata', {}).get('character_count', 'N/A')}")
            print(f"Estimated words: {job_status.get('metadata', {}).get('estimated_words', 'N/A')}")
            print(f"Total duration: {job_status.get('metadata', {}).get('total_duration', 'N/A')} seconds")

            # Check if we got substantial content (should be ~10,000+ words for a 57 min article)
            word_count = job_status.get('metadata', {}).get('estimated_words', 0)
            if word_count > 5000:
                print(f"\n🎉 SUCCESS: Extracted {word_count} words (expected for long article)")
            else:
                print(f"\n⚠️  WARNING: Only extracted {word_count} words (expected much more)")
        else:
            print(f"\n❌ Job failed!")
            print(f"Error: {job_status.get('error', 'Unknown error')}")
        break

    time.sleep(2)