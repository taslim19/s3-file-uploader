from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_active_user
from app.database import get_db
from app.schemas import FolderCreate, FolderRead


router = APIRouter(prefix="/folders", tags=["Folders"])


@router.get("/", response_model=list[FolderRead])
def list_folders(
    parent_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> list[models.Folder]:
    """List folders, optionally filtered by parent"""
    query = db.query(models.Folder).filter(models.Folder.owner_id == current_user.id)
    
    if parent_id is None:
        query = query.filter(models.Folder.parent_id.is_(None))
    else:
        # Verify parent belongs to user
        parent = db.get(models.Folder, parent_id)
        if not parent or parent.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Parent folder not found")
        query = query.filter(models.Folder.parent_id == parent_id)
    
    return query.order_by(models.Folder.name.asc()).all()


@router.post("/", response_model=FolderRead, status_code=201)
def create_folder(
    folder: FolderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Folder:
    """Create a new folder"""
    # Validate parent if provided
    if folder.parent_id:
        parent = db.get(models.Folder, folder.parent_id)
        if not parent or parent.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Parent folder not found")
    
    # Check for duplicate name in same parent
    existing = db.query(models.Folder).filter(
        models.Folder.owner_id == current_user.id,
        models.Folder.name == folder.name,
        models.Folder.parent_id == folder.parent_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Folder with this name already exists")
    
    new_folder = models.Folder(
        name=folder.name,
        owner_id=current_user.id,
        parent_id=folder.parent_id,
    )
    db.add(new_folder)
    db.commit()
    db.refresh(new_folder)
    return new_folder


@router.delete("/{folder_id}")
def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> dict:
    """Delete a folder (must be empty)"""
    folder = db.get(models.Folder, folder_id)
    if not folder or folder.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Check if folder has files
    file_count = db.query(models.FileAsset).filter(
        models.FileAsset.folder_id == folder_id,
        models.FileAsset.is_trashed == False
    ).count()
    
    if file_count > 0:
        raise HTTPException(status_code=400, detail="Folder is not empty. Move or delete files first.")
    
    # Check if folder has subfolders
    subfolder_count = db.query(models.Folder).filter(
        models.Folder.parent_id == folder_id
    ).count()
    
    if subfolder_count > 0:
        raise HTTPException(status_code=400, detail="Folder has subfolders. Delete them first.")
    
    db.delete(folder)
    db.commit()
    return {"message": "Folder deleted"}


@router.patch("/{folder_id}", response_model=FolderRead)
def update_folder(
    folder_id: int,
    name: str | None = None,
    parent_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
) -> models.Folder:
    """Update folder name or move it"""
    folder = db.get(models.Folder, folder_id)
    if not folder or folder.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    if name:
        # Check for duplicate name
        existing = db.query(models.Folder).filter(
            models.Folder.owner_id == current_user.id,
            models.Folder.name == name,
            models.Folder.parent_id == folder.parent_id,
            models.Folder.id != folder_id
        ).first()
        
        if existing:
            raise HTTPException(status_code=400, detail="Folder with this name already exists")
        
        folder.name = name
    
    if parent_id is not None:
        if parent_id == folder_id:
            raise HTTPException(status_code=400, detail="Folder cannot be its own parent")
        
        if parent_id:
            parent = db.get(models.Folder, parent_id)
            if not parent or parent.owner_id != current_user.id:
                raise HTTPException(status_code=404, detail="Parent folder not found")
        
        folder.parent_id = parent_id
    
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder

