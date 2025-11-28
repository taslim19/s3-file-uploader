from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_admin
from app.database import get_db
from app.schemas import UserRead
from app.services.stats import admin_summary

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/summary")
def summary(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
) -> dict:
    return admin_summary(db)


@router.get("/users", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
) -> list[models.User]:
    return db.query(models.User).order_by(models.User.created_at.desc()).all()

