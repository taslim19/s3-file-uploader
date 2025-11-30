import uuid
from typing import BinaryIO

import boto3
from botocore.client import Config

from app.config import get_settings

settings = get_settings()


def _create_client():
    session = boto3.session.Session(
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )
    return session.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        config=Config(signature_version="s3v4"),
    )


class S3StorageService:
    def __init__(self):
        self.client = _create_client()
        self.bucket = settings.s3_bucket_name

    def upload(self, *, file_obj: BinaryIO, content_type: str) -> str:
        key = f"uploads/{uuid.uuid4().hex}"
        self.client.upload_fileobj(
            Fileobj=file_obj,
            Bucket=self.bucket,
            Key=key,
            ExtraArgs={"ContentType": content_type},
        )
        return key

    def presigned_download(self, key: str, expires_in: int = 600) -> str:
        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)
    
    def download(self, key: str) -> bytes:
        """Download file content as bytes"""
        import io
        buffer = io.BytesIO()
        try:
            self.client.download_fileobj(Bucket=self.bucket, Key=key, Fileobj=buffer)
            buffer.seek(0)
            return buffer.read()
        except Exception as e:
            raise Exception(f"Failed to download file: {str(e)}")

