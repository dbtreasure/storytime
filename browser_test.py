#!/usr/bin/env python3
"""Browser test helper for streaming API."""

import json
import requests
from datetime import datetime
from uuid import uuid4

# Configuration
BASE_URL = "http://localhost:8000"
TEST_USER_EMAIL = "test@streaming.com"
TEST_USER_PASSWORD = "testpassword123"

def create_test_user():
    """Create a test user for authentication."""
    user_data = {
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    }
    
    # Try to register (might already exist)
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=user_data)
        if response.status_code == 200:
            print("✅ Test user created")
        else:
            print(f"ℹ️  User might already exist: {response.status_code}")
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return None
    
    # Login to get token
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=user_data)
        if response.status_code == 200:
            token = response.json()["access_token"]
            print("✅ User authenticated")
            return token
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None

def create_test_job(token):
    """Create a test job."""
    headers = {"Authorization": f"Bearer {token}"}
    job_data = {
        "title": "Browser Test Audio",
        "description": "Test audio for browser streaming",
        "content": "This is a test audio file for browser streaming. It should be converted to MP3 and available for streaming through pre-signed URLs.",
        "file_key": None,
        "voice_config": None
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/jobs", json=job_data, headers=headers)
        if response.status_code == 200:
            job_id = response.json()["id"]
            print(f"✅ Test job created: {job_id}")
            return job_id
        else:
            print(f"❌ Job creation failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Job creation error: {e}")
        return None

def simulate_job_completion(job_id, token):
    """Simulate job completion by directly updating the database."""
    print("ℹ️  Note: In a real scenario, the Celery worker would complete this job")
    print("ℹ️  For testing, you can manually mark the job as completed with mock audio")
    
    # This would normally be done by the worker, but for testing we can simulate it
    print(f"\n📝 To simulate job completion:")
    print(f"   1. The job ID is: {job_id}")
    print(f"   2. Set status to 'COMPLETED'")
    print(f"   3. Set output_file_key to 'jobs/{job_id}/audio.mp3'")
    print(f"   4. Add result_data with metadata")
    
    return job_id

def get_streaming_urls(job_id, token):
    """Get streaming URLs for the job."""
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Try the job audio endpoint first
        response = requests.get(f"{BASE_URL}/api/v1/jobs/{job_id}/audio", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print("✅ Job audio URLs retrieved")
            return data
        elif response.status_code == 400:
            print("ℹ️  Job not completed yet - normal for a new job")
            return None
        else:
            print(f"❌ Failed to get job audio: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error getting URLs: {e}")
        return None

def test_streaming_endpoints(job_id, token):
    """Test the dedicated streaming endpoints."""
    headers = {"Authorization": f"Bearer {token}"}
    
    endpoints = [
        f"/api/v1/audio/{job_id}/stream",
        f"/api/v1/audio/{job_id}/metadata", 
        f"/api/v1/audio/{job_id}/playlist"
    ]
    
    print("\n🧪 Testing streaming endpoints:")
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
            print(f"   {endpoint}: {response.status_code}")
            if response.status_code == 400:
                print(f"      (Job not completed - expected for new job)")
        except Exception as e:
            print(f"   {endpoint}: Error - {e}")

def main():
    """Main test flow."""
    print("🌐 Browser Streaming Test Setup")
    print("=" * 40)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code != 200:
            print("❌ Server not responding. Please start with: docker-compose up")
            return
        print("✅ Server is running")
    except Exception:
        print("❌ Cannot connect to server. Please start with: docker-compose up")
        return
    
    # Create user and get token
    token = create_test_user()
    if not token:
        return
    
    # Create test job
    job_id = create_test_job(token)
    if not job_id:
        return
    
    # Test endpoints (will show job not completed)
    test_streaming_endpoints(job_id, token)
    
    # Get URLs (will fail since job not completed)
    urls = get_streaming_urls(job_id, token)
    
    print("\n" + "=" * 40)
    print("🎯 Next Steps for Browser Testing:")
    print("=" * 40)
    print(f"1. Job ID: {job_id}")
    print(f"2. Access Token: {token[:20]}...")
    print("\n📱 For browser testing:")
    print("   1. Wait for job to complete (check job status)")
    print("   2. Use these curl commands to get URLs:")
    print(f"      curl -H 'Authorization: Bearer {token}' {BASE_URL}/api/v1/jobs/{job_id}/audio")
    print(f"      curl -H 'Authorization: Bearer {token}' {BASE_URL}/api/v1/audio/{job_id}/stream")
    print("   3. Copy the streaming_url and paste into browser audio player")
    print("\n🎵 Browser audio player HTML:")
    print(f'   <audio controls>')
    print(f'     <source src="[STREAMING_URL_HERE]" type="audio/mpeg">')
    print(f'   </audio>')

if __name__ == "__main__":
    main()