from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Mini Cloud Drive"
    database_url: str = "sqlite:///./cloud_drive.db"
    secret_key: str
    access_token_expire_minutes: int = 60
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "ap-south-1"
    s3_bucket_name: str
    s3_endpoint_url: str | None = None  # allows localstack/minio

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()

