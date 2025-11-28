from datetime import datetime
from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    sub: str | None = None


class UserBase(BaseModel):
    email: EmailStr
    full_name: str


class UserCreate(UserBase):
    password: str


class UserRead(UserBase):
    id: int
    is_admin: bool
    total_bytes: int
    file_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class FileBase(BaseModel):
    filename: str
    size: int
    content_type: str


class FileRead(FileBase):
    id: int
    uploaded_at: datetime
    download_count: int

    class Config:
        from_attributes = True


class ShareLinkRead(BaseModel):
    token: str
    expires_at: datetime
    file_id: int

    class Config:
        from_attributes = True

