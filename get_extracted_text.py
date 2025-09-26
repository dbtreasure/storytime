#!/usr/bin/env python3
"""Retrieve the extracted text from DigitalOcean Spaces for comparison."""

import boto3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.docker')

# DigitalOcean Spaces configuration
spaces_key = os.getenv("DO_SPACES_KEY")
spaces_secret = os.getenv("DO_SPACES_SECRET")
spaces_region = os.getenv("DO_SPACES_REGION", "nyc3")
spaces_bucket = os.getenv("DO_SPACES_BUCKET", "storytime")
spaces_endpoint = os.getenv("DO_SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com")

# Job ID from the successful extraction
job_id = "b93ab642-996b-4943-bf8d-5b22558aa942"
text_key = f"jobs/{job_id}/input.txt"

# Initialize S3 client for DigitalOcean Spaces
s3 = boto3.client(
    's3',
    endpoint_url=spaces_endpoint,
    aws_access_key_id=spaces_key,
    aws_secret_access_key=spaces_secret,
    region_name=spaces_region
)

try:
    # Download the text file
    response = s3.get_object(Bucket=spaces_bucket, Key=text_key)
    content = response['Body'].read().decode('utf-8')

    # Save to local file for comparison
    output_file = f"extracted_content_{job_id}.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Extracted text saved to: {output_file}")
    print(f"📊 Total length: {len(content)} characters")
    print(f"📊 Word count: {len(content.split())} words")
    print("\n📝 First 1000 characters:\n")
    print("-" * 80)
    print(content[:1000])
    print("-" * 80)

except Exception as e:
    print(f"❌ Error retrieving text: {e}")