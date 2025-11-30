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
    folders = relationship("Folder", back_populates="owner")
    activities = relationship("ActivityLog", back_populates="user")


class Folder(Base):
    __tablename__ = "folders"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="folders")
    parent = relationship("Folder", remote_side=[id], backref="children")
    files = relationship("FileAsset", back_populates="folder")


class FileAsset(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size = Column(BigInteger, nullable=False)
    s3_key = Column(String, nullable=False, unique=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    folder_id = Column(Integer, ForeignKey("folders.id"), nullable=True)
    is_trashed = Column(Boolean, default=False)
    trashed_at = Column(DateTime, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    download_count = Column(Integer, default=0)

    owner = relationship("User", back_populates="files")
    folder = relationship("Folder", back_populates="files")
    share_links = relationship("ShareLink", back_populates="file", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="file", cascade="all, delete-orphan")


class ShareLink(Base):
    __tablename__ = "share_links"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    file = relationship("FileAsset", back_populates="share_links")


class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    file = relationship("FileAsset", back_populates="favorites")
    user = relationship("User")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)  # upload, download, delete, share, etc.
    file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    details = Column(String, nullable=True)  # JSON string for additional info
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="activities")
    file = relationship("FileAsset")

