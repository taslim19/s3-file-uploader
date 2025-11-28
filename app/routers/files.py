import secrets
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_active_user, get_current_user
from app.database import get_db
from app.schemas import FileRead, ShareLinkRead
from app.services.storage import S3StorageService


def get_storage_service() -> S3StorageService:
    return S3StorageService()


router = APIRouter(prefix="/files", tags=["Files"])


@router.get("/", response_model=list[FileRead])
def list_my_files(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> list[models.FileAsset]:
    files = (
        db.query(models.FileAsset)
        .filter(models.FileAsset.owner_id == current_user.id)
        .order_by(models.FileAsset.uploaded_at.desc())
        .all()
    )
    return files


@router.post("/upload", response_model=FileRead, status_code=status.HTTP_201_CREATED)
async def upload_file(
    upload: Annotated[UploadFile, File(description="Binary file")],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    storage: S3StorageService = Depends(get_storage_service),
) -> models.FileAsset:
    upload.file.seek(0, 2)
    size = upload.file.tell()
    upload.file.seek(0)
    s3_key = storage.upload(file_obj=upload.file, content_type=upload.content_type or "application/octet-stream")
    record = models.FileAsset(
        filename=upload.filename,
        content_type=upload.content_type or "application/octet-stream",
        size=size,
        owner_id=current_user.id,
        s3_key=s3_key,
    )
    current_user.total_bytes += size
    current_user.file_count += 1
    db.add(record)
    db.add(current_user)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{file_id}/download")
def generate_download_link(
    file_id: int,
    expires_in: int = 600,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    storage: S3StorageService = Depends(get_storage_service),
) -> dict:
    file_obj = db.get(models.FileAsset, file_id)
    if not file_obj or (file_obj.owner_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="File not found")
    file_obj.download_count += 1
    db.add(file_obj)
    db.commit()
    url = storage.presigned_download(file_obj.s3_key, expires_in=expires_in)
    return {"url": url}


@router.post("/{file_id}/share", response_model=ShareLinkRead)
def create_share_link(
    file_id: int,
    minutes: int = 30,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.ShareLink:
    file_obj = db.get(models.FileAsset, file_id)
    if not file_obj or (file_obj.owner_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="File not found")
    token = secrets.token_urlsafe(16)
    share = models.ShareLink(
        token=token,
        file_id=file_obj.id,
        expires_at=datetime.utcnow() + timedelta(minutes=minutes),
        created_by_id=current_user.id,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share


@router.delete("/{file_id}")
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    storage: S3StorageService = Depends(get_storage_service),
) -> dict:
    file_obj = db.get(models.FileAsset, file_id)
    if not file_obj or (file_obj.owner_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete from S3
    try:
        storage.delete(file_obj.s3_key)
    except Exception:
        pass  # Continue even if S3 delete fails
    
    # Update user stats
    current_user.total_bytes -= file_obj.size
    current_user.file_count -= 1
    
    # Delete file record
    db.delete(file_obj)
    db.add(current_user)
    db.commit()
    
    return {"message": "File deleted successfully"}


@router.get("/shared/{token}")
def use_share_link(
    token: str,
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
) -> dict:
    share = db.query(models.ShareLink).filter(models.ShareLink.token == token).first()
    if not share:
        raise HTTPException(status_code=404, detail="Invalid link")
    if share.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Link expired")
    file_obj = db.get(models.FileAsset, share.file_id)
    if not file_obj:
        raise HTTPException(status_code=404, detail="File missing")
    url = storage.presigned_download(file_obj.s3_key)
    return {"filename": file_obj.filename, "url": url}

