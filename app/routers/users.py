from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import models
from app.auth import (
    authenticate_user,
    create_access_token,
    get_current_active_user,
    get_password_hash,
    get_user_by_email,
)
from app.database import get_db
from app.schemas import Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserCreate, db: Session = Depends(get_db)) -> models.User:
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    first_user = db.query(models.User).count() == 0
    user = models.User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=get_password_hash(payload.password),
        is_admin=first_user,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token(subject=user.email)
    
    # Create response with token
    response = JSONResponse(content={"access_token": token, "token_type": "bearer"})
    
    # Set cookie for web interface
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=86400,  # 24 hours
        httponly=False,  # Allow JS access for localStorage fallback
        samesite="lax",
        secure=False,  # Set to True in production with HTTPS
    )
    
    return response


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: models.User = Depends(get_current_active_user)) -> models.User:
    return current_user

