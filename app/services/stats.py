from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models


def admin_summary(db: Session) -> dict:
    total_users = db.query(func.count(models.User.id)).scalar() or 0
    total_files = db.query(func.count(models.FileAsset.id)).scalar() or 0
    total_bytes = db.query(func.coalesce(func.sum(models.FileAsset.size), 0)).scalar() or 0
    top_users = (
        db.query(models.User.full_name, models.User.email, models.User.total_bytes)
        .order_by(models.User.total_bytes.desc())
        .limit(5)
        .all()
    )
    return {
        "total_users": total_users,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "top_users": [
            {"name": row[0], "email": row[1], "bytes": row[2]}
            for row in top_users
        ],
    }

