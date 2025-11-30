import secrets
import zipfile
import io
from datetime import datetime, timedelta
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app import models
from app.auth import get_current_active_user, get_current_user
from app.database import get_db
from app.schemas import FileRead, ShareLinkRead, FolderCreate, FolderRead, ActivityLogRead
from app.services.storage import S3StorageService


def get_storage_service() -> S3StorageService:
    return S3StorageService()


def log_activity(
    db: Session,
    user_id: int,
    action: str,
    file_id: Optional[int] = None,
    details: Optional[str] = None,
):
    """Helper function to log user activities"""
    activity = models.ActivityLog(
        user_id=user_id,
        action=action,
        file_id=file_id,
        details=details,
    )
    db.add(activity)
    db.commit()


router = APIRouter(prefix="/files", tags=["Files"])


@router.get("/", response_model=list[FileRead])
def list_my_files(
    search: Optional[str] = Query(None, description="Search by filename"),
    file_type: Optional[str] = Query(None, description="Filter by file type (image, video, document, etc.)"),
    folder_id: Optional[int] = Query(None, description="Filter by folder"),
    favorite_only: bool = Query(False, description="Show only favorites"),
    trashed: bool = Query(False, description="Show trashed files"),
    sort_by: str = Query("date", description="Sort by: date, name, size"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> list[models.FileAsset]:
    """List files with search, filtering, and sorting"""
    query = db.query(models.FileAsset).filter(models.FileAsset.owner_id == current_user.id)
    
    # Filter by trash status
    if trashed:
        query = query.filter(models.FileAsset.is_trashed == True)
    else:
        query = query.filter(models.FileAsset.is_trashed == False)
    
    # Search by filename
    if search:
        query = query.filter(models.FileAsset.filename.ilike(f"%{search}%"))
    
    # Filter by file type
    if file_type:
        type_mapping = {
            "image": ["image/"],
            "video": ["video/"],
            "audio": ["audio/"],
            "document": ["application/pdf", "application/msword", "application/vnd.openxmlformats"],
            "text": ["text/"],
        }
        if file_type in type_mapping:
            filters = [models.FileAsset.content_type.like(f"{t}%") for t in type_mapping[file_type]]
            query = query.filter(or_(*filters))
    
    # Filter by folder
    if folder_id is not None:
        query = query.filter(models.FileAsset.folder_id == folder_id)
    
    # Filter by favorites
    if favorite_only:
        favorite_file_ids = db.query(models.Favorite.file_id).filter(
            models.Favorite.user_id == current_user.id
        ).subquery()
        query = query.filter(models.FileAsset.id.in_(db.query(favorite_file_ids)))
    
    # Sorting
    if sort_by == "name":
        query = query.order_by(models.FileAsset.filename.asc())
    elif sort_by == "size":
        query = query.order_by(models.FileAsset.size.desc())
    else:  # date (default)
        query = query.order_by(models.FileAsset.uploaded_at.desc())
    
    files = query.all()
    
    # Add favorite status to each file
    favorite_ids = {
        f.file_id for f in db.query(models.Favorite).filter(
            models.Favorite.user_id == current_user.id
        ).all()
    }
    
    result = []
    for file in files:
        file_dict = {
            "id": file.id,
            "filename": file.filename,
            "size": file.size,
            "content_type": file.content_type,
            "uploaded_at": file.uploaded_at,
            "download_count": file.download_count,
            "folder_id": file.folder_id,
            "is_trashed": file.is_trashed,
            "is_favorite": file.id in favorite_ids,
        }
        result.append(file_dict)
    
    return result


@router.post("/upload", response_model=FileRead, status_code=status.HTTP_201_CREATED)
async def upload_file(
    upload: Annotated[UploadFile, File(description="Binary file")],
    folder_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    storage: S3StorageService = Depends(get_storage_service),
) -> dict:
    """Upload a file, optionally to a folder"""
    # Validate folder if provided
    if folder_id:
        folder = db.get(models.Folder, folder_id)
        if not folder or folder.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Folder not found")
    
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
        folder_id=folder_id,
    )
    current_user.total_bytes += size
    current_user.file_count += 1
    db.add(record)
    db.add(current_user)
    db.commit()
    db.refresh(record)
    
    log_activity(db, current_user.id, "upload", record.id, f"Uploaded {upload.filename}")
    
    return {
        "id": record.id,
        "filename": record.filename,
        "size": record.size,
        "content_type": record.content_type,
        "uploaded_at": record.uploaded_at,
        "download_count": record.download_count,
        "folder_id": record.folder_id,
        "is_trashed": record.is_trashed,
        "is_favorite": False,
    }


@router.get("/{file_id}/download")
def generate_download_link(
    file_id: int,
    expires_in: int = 600,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    storage: S3StorageService = Depends(get_storage_service),
) -> dict:
    """Generate a presigned download URL"""
    file_obj = db.get(models.FileAsset, file_id)
    if not file_obj or (file_obj.owner_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="File not found")
    if file_obj.is_trashed:
        raise HTTPException(status_code=404, detail="File is in trash")
    
    file_obj.download_count += 1
    db.add(file_obj)
    db.commit()
    
    log_activity(db, current_user.id, "download", file_id, f"Downloaded {file_obj.filename}")
    
    url = storage.presigned_download(file_obj.s3_key, expires_in=expires_in)
    return {"url": url}


@router.get("/{file_id}/preview")
def preview_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    storage: S3StorageService = Depends(get_storage_service),
):
    """Get file preview URL for viewing in browser"""
    file_obj = db.get(models.FileAsset, file_id)
    if not file_obj or (file_obj.owner_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="File not found")
    if file_obj.is_trashed:
        raise HTTPException(status_code=404, detail="File is in trash")
    
    # Generate a longer-lived URL for preview (1 hour)
    url = storage.presigned_download(file_obj.s3_key, expires_in=3600)
    return {
        "url": url,
        "filename": file_obj.filename,
        "content_type": file_obj.content_type,
        "size": file_obj.size,
    }


@router.post("/{file_id}/share", response_model=ShareLinkRead)
def create_share_link(
    file_id: int,
    minutes: int = 30,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.ShareLink:
    """Create a share link for a file"""
    file_obj = db.get(models.FileAsset, file_id)
    if not file_obj or (file_obj.owner_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="File not found")
    if file_obj.is_trashed:
        raise HTTPException(status_code=404, detail="File is in trash")
    
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
    
    log_activity(db, current_user.id, "share", file_id, f"Created share link for {file_obj.filename}")
    
    return share


@router.delete("/{file_id}")
def delete_file(
    file_id: int,
    permanent: bool = Query(False, description="Permanently delete (skip trash)"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    storage: S3StorageService = Depends(get_storage_service),
) -> dict:
    """Delete a file (move to trash or permanent delete)"""
    file_obj = db.get(models.FileAsset, file_id)
    if not file_obj or (file_obj.owner_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="File not found")
    
    if permanent or file_obj.is_trashed:
        # Permanent delete
        try:
            storage.delete(file_obj.s3_key)
        except Exception:
            pass
        
        current_user.total_bytes -= file_obj.size
        current_user.file_count -= 1
        db.delete(file_obj)
        db.add(current_user)
        db.commit()
        
        log_activity(db, current_user.id, "delete_permanent", file_id, f"Permanently deleted {file_obj.filename}")
        return {"message": "File permanently deleted"}
    else:
        # Move to trash
        file_obj.is_trashed = True
        file_obj.trashed_at = datetime.utcnow()
        db.add(file_obj)
        db.commit()
        
        log_activity(db, current_user.id, "delete", file_id, f"Moved {file_obj.filename} to trash")
        return {"message": "File moved to trash"}


@router.post("/{file_id}/restore")
def restore_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> dict:
    """Restore a file from trash"""
    file_obj = db.get(models.FileAsset, file_id)
    if not file_obj or (file_obj.owner_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="File not found")
    if not file_obj.is_trashed:
        raise HTTPException(status_code=400, detail="File is not in trash")
    
    file_obj.is_trashed = False
    file_obj.trashed_at = None
    db.add(file_obj)
    db.commit()
    
    log_activity(db, current_user.id, "restore", file_id, f"Restored {file_obj.filename} from trash")
    return {"message": "File restored"}


@router.post("/{file_id}/favorite")
def toggle_favorite(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> dict:
    """Toggle favorite status of a file"""
    file_obj = db.get(models.FileAsset, file_id)
    if not file_obj or (file_obj.owner_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="File not found")
    
    favorite = db.query(models.Favorite).filter(
        models.Favorite.file_id == file_id,
        models.Favorite.user_id == current_user.id
    ).first()
    
    is_favorite = False
    if favorite:
        db.delete(favorite)
        action = "unfavorited"
    else:
        favorite = models.Favorite(file_id=file_id, user_id=current_user.id)
        db.add(favorite)
        action = "favorited"
        is_favorite = True
    
    db.commit()
    log_activity(db, current_user.id, action, file_id, f"{action.capitalize()} {file_obj.filename}")
    
    return {"message": f"File {action}", "is_favorite": is_favorite}


@router.post("/{file_id}/move")
def move_file(
    file_id: int,
    folder_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> dict:
    """Move a file to a folder (or root if folder_id is None)"""
    file_obj = db.get(models.FileAsset, file_id)
    if not file_obj or (file_obj.owner_id != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="File not found")
    
    if folder_id:
        folder = db.get(models.Folder, folder_id)
        if not folder or folder.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Folder not found")
    
    old_folder_id = file_obj.folder_id
    file_obj.folder_id = folder_id
    db.add(file_obj)
    db.commit()
    
    log_activity(db, current_user.id, "move", file_id, f"Moved {file_obj.filename} to folder {folder_id or 'root'}")
    return {"message": "File moved", "folder_id": folder_id}


@router.post("/bulk/delete")
def bulk_delete(
    file_ids: list[int],
    permanent: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    storage: S3StorageService = Depends(get_storage_service),
) -> dict:
    """Bulk delete files"""
    files = db.query(models.FileAsset).filter(
        models.FileAsset.id.in_(file_ids),
        models.FileAsset.owner_id == current_user.id
    ).all()
    
    deleted_count = 0
    for file_obj in files:
        if permanent or file_obj.is_trashed:
            try:
                storage.delete(file_obj.s3_key)
            except Exception:
                pass
            current_user.total_bytes -= file_obj.size
            current_user.file_count -= 1
            db.delete(file_obj)
            deleted_count += 1
        else:
            file_obj.is_trashed = True
            file_obj.trashed_at = datetime.utcnow()
            db.add(file_obj)
            deleted_count += 1
    
    db.add(current_user)
    db.commit()
    
    log_activity(db, current_user.id, "bulk_delete", None, f"Bulk deleted {deleted_count} files")
    return {"message": f"{deleted_count} files processed", "count": deleted_count}


@router.post("/bulk/download")
def bulk_download(
    file_ids: list[int],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    storage: S3StorageService = Depends(get_storage_service),
):
    """Download multiple files as ZIP"""
    files = db.query(models.FileAsset).filter(
        models.FileAsset.id.in_(file_ids),
        models.FileAsset.owner_id == current_user.id,
        models.FileAsset.is_trashed == False
    ).all()
    
    if not files:
        raise HTTPException(status_code=404, detail="No files found")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for file_obj in files:
            try:
                # Get file from S3
                file_data = storage.download(file_obj.s3_key)
                zip_file.writestr(file_obj.filename, file_data)
            except Exception as e:
                continue
    
    zip_buffer.seek(0)
    
    log_activity(db, current_user.id, "bulk_download", None, f"Downloaded {len(files)} files as ZIP")
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=files.zip"}
    )


@router.post("/bulk/move")
def bulk_move(
    file_ids: list[int],
    folder_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> dict:
    """Move multiple files to a folder"""
    if folder_id:
        folder = db.get(models.Folder, folder_id)
        if not folder or folder.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Folder not found")
    
    files = db.query(models.FileAsset).filter(
        models.FileAsset.id.in_(file_ids),
        models.FileAsset.owner_id == current_user.id
    ).all()
    
    for file_obj in files:
        file_obj.folder_id = folder_id
        db.add(file_obj)
    
    db.commit()
    
    log_activity(db, current_user.id, "bulk_move", None, f"Moved {len(files)} files to folder {folder_id or 'root'}")
    return {"message": f"{len(files)} files moved", "count": len(files)}


@router.get("/shares", response_model=list[ShareLinkRead])
def list_my_share_links(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> list[models.ShareLink]:
    """Get all share links created by the current user"""
    shares = (
        db.query(models.ShareLink)
        .filter(models.ShareLink.created_by_id == current_user.id)
        .order_by(models.ShareLink.expires_at.desc())
        .all()
    )
    return shares


@router.get("/shared/{token}")
def use_share_link(
    token: str,
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
) -> dict:
    """Use a share link to get file download URL"""
    share = db.query(models.ShareLink).filter(models.ShareLink.token == token).first()
    if not share:
        raise HTTPException(status_code=404, detail="Invalid link")
    if share.expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Link expired")
    file_obj = db.get(models.FileAsset, share.file_id)
    if not file_obj or file_obj.is_trashed:
        raise HTTPException(status_code=404, detail="File missing")
    url = storage.presigned_download(file_obj.s3_key)
    return {"filename": file_obj.filename, "url": url}


@router.get("/activity", response_model=list[ActivityLogRead])
def get_activity_log(
    limit: int = Query(50, description="Number of activities to return"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> list[models.ActivityLog]:
    """Get user activity log"""
    activities = (
        db.query(models.ActivityLog)
        .filter(models.ActivityLog.user_id == current_user.id)
        .order_by(models.ActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return activities
