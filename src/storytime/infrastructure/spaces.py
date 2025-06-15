import json
import logging
import os
import tempfile
from typing import Any

import boto3
from botocore.client import Config

DO_SPACES_KEY = os.getenv("DO_SPACES_KEY")
DO_SPACES_SECRET = os.getenv("DO_SPACES_SECRET")
DO_SPACES_REGION = os.getenv("DO_SPACES_REGION", "nyc3")
DO_SPACES_BUCKET = os.getenv("DO_SPACES_BUCKET")
DO_SPACES_ENDPOINT = os.getenv(
    "DO_SPACES_ENDPOINT", f"https://{DO_SPACES_REGION}.digitaloceanspaces.com"
)


class SpacesClient:
    """DigitalOcean Spaces client for file operations."""

    def __init__(self):
        session = boto3.Session()
        self.s3 = session.client(
            "s3",
            region_name=DO_SPACES_REGION,
            endpoint_url=DO_SPACES_ENDPOINT,
            aws_access_key_id=DO_SPACES_KEY,
            aws_secret_access_key=DO_SPACES_SECRET,
            config=Config(signature_version="s3v4"),
        )
        self.bucket = DO_SPACES_BUCKET

    async def download_text_file(self, key: str) -> str:
        """Download a text file and return its content."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp_file:
            self.s3.download_file(self.bucket, key, tmp_file.name)
            with open(tmp_file.name, encoding="utf-8") as f:
                content = f.read()
            os.unlink(tmp_file.name)
            return content

    async def upload_audio_file(self, key: str, audio_data: bytes) -> bool:
        """Upload audio data to spaces."""
        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=audio_data,
                ContentType="audio/mpeg",
                ACL="public-read",
            )
            logging.info(f"[Spaces] Audio upload successful: {key}")
            return True
        except Exception as e:
            logging.error(f"[Spaces] Audio upload failed: {e}")
            return False

    async def upload_json_file(self, key: str, data: dict[str, Any]) -> bool:
        """Upload JSON data to spaces."""
        try:
            json_data = json.dumps(data, indent=2).encode("utf-8")
            self.s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=json_data,
                ContentType="application/json",
                ACL="public-read",
            )
            logging.info(f"[Spaces] JSON upload successful: {key}")
            return True
        except Exception as e:
            logging.error(f"[Spaces] JSON upload failed: {e}")
            return False

    async def get_presigned_download_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for downloading a file."""
        return self.s3.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_in
        )
    
    async def get_streaming_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL optimized for audio streaming.
        
        This method generates URLs with headers appropriate for streaming:
        - Content-Disposition: inline (for in-browser playback)
        - Content-Type: audio/mpeg (for proper audio handling)
        - Cache-Control headers for optimal streaming performance
        """
        return self.s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": "inline",
                "ResponseContentType": "audio/mpeg",
                "ResponseCacheControl": "public, max-age=3600"
            },
            ExpiresIn=expires_in
        )


# Legacy functions for backward compatibility
session = boto3.Session()
s3 = session.client(
    "s3",
    region_name=DO_SPACES_REGION,
    endpoint_url=DO_SPACES_ENDPOINT,
    aws_access_key_id=DO_SPACES_KEY,
    aws_secret_access_key=DO_SPACES_SECRET,
    config=Config(signature_version="s3v4"),
)


def upload_file(file_path: str, key: str, content_type: str | None = None) -> bool:
    logging.info(f"[Spaces] Attempting to upload {file_path} to {DO_SPACES_BUCKET}/{key}")
    try:
        extra_args = {"ACL": "public-read"}
        if content_type:
            extra_args["ContentType"] = content_type
        s3.upload_file(file_path, DO_SPACES_BUCKET, key, ExtraArgs=extra_args)
        logging.info(f"[Spaces] Upload successful: {key}")
        return True
    except Exception as e:
        logging.error(f"[Spaces] Upload failed: {e}")
        return False


def download_file(key: str, file_path: str):
    s3.download_file(DO_SPACES_BUCKET, key, file_path)


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    return s3.generate_presigned_url(
        "get_object", Params={"Bucket": DO_SPACES_BUCKET, "Key": key}, ExpiresIn=expires_in
    )
