from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, BigInteger
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    total_bytes = Column(BigInteger, default=0)
    file_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    files = relationship("FileAsset", back_populates="owner")


class FileAsset(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size = Column(BigInteger, nullable=False)
    s3_key = Column(String, nullable=False, unique=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    download_count = Column(Integer, default=0)

    owner = relationship("User", back_populates="files")
    share_links = relationship("ShareLink", back_populates="file", cascade="all, delete-orphan")


class ShareLink(Base):
    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    file = relationship("FileAsset", back_populates="share_links")

