import os
import boto3
from botocore.client import Config
from typing import Optional
import logging

DO_SPACES_KEY = os.getenv("DO_SPACES_KEY")
DO_SPACES_SECRET = os.getenv("DO_SPACES_SECRET")
DO_SPACES_REGION = os.getenv("DO_SPACES_REGION", "nyc3")
DO_SPACES_BUCKET = os.getenv("DO_SPACES_BUCKET")
DO_SPACES_ENDPOINT = os.getenv("DO_SPACES_ENDPOINT", f"https://{DO_SPACES_REGION}.digitaloceanspaces.com")

session = boto3.Session()
s3 = session.client(
    's3',
    region_name=DO_SPACES_REGION,
    endpoint_url=DO_SPACES_ENDPOINT,
    aws_access_key_id=DO_SPACES_KEY,
    aws_secret_access_key=DO_SPACES_SECRET,
    config=Config(signature_version='s3v4')
)

def upload_file(file_path: str, key: str, content_type: Optional[str] = None) -> bool:
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
        'get_object',
        Params={'Bucket': DO_SPACES_BUCKET, 'Key': key},
        ExpiresIn=expires_in
    ) 