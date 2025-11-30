import os
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import models
from app.auth import get_current_active_user, get_optional_user
from app.database import Base, engine
from app.routers import admin, files, folders, users

app = FastAPI(title="Mini Cloud Drive")

app.include_router(users.router)
app.include_router(files.router)
app.include_router(folders.router)
app.include_router(admin.router)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def on_startup() -> None:
    # Create all tables (for new installations)
    Base.metadata.create_all(bind=engine)
    
    # Run migrations for existing databases
    try:
        import sqlite3
        from app.config import get_settings
        settings = get_settings()
        db_url = settings.database_url
        
        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            if db_path and os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Check existing columns
                cursor.execute("PRAGMA table_info(files)")
                existing_columns = [row[1] for row in cursor.fetchall()]
                
                # Add missing columns
                if 'folder_id' not in existing_columns:
                    cursor.execute("ALTER TABLE files ADD COLUMN folder_id INTEGER")
                if 'is_trashed' not in existing_columns:
                    cursor.execute("ALTER TABLE files ADD COLUMN is_trashed BOOLEAN DEFAULT 0")
                if 'trashed_at' not in existing_columns:
                    cursor.execute("ALTER TABLE files ADD COLUMN trashed_at DATETIME")
                
                # Create new tables if they don't exist
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='folders'")
                if not cursor.fetchone():
                    cursor.execute("""
                        CREATE TABLE folders (
                            id INTEGER NOT NULL PRIMARY KEY,
                            name VARCHAR NOT NULL,
                            owner_id INTEGER NOT NULL,
                            parent_id INTEGER,
                            created_at DATETIME,
                            FOREIGN KEY(owner_id) REFERENCES users (id),
                            FOREIGN KEY(parent_id) REFERENCES folders (id)
                        )
                    """)
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='favorites'")
                if not cursor.fetchone():
                    cursor.execute("""
                        CREATE TABLE favorites (
                            id INTEGER NOT NULL PRIMARY KEY,
                            file_id INTEGER NOT NULL,
                            user_id INTEGER NOT NULL,
                            created_at DATETIME,
                            FOREIGN KEY(file_id) REFERENCES files (id),
                            FOREIGN KEY(user_id) REFERENCES users (id)
                        )
                    """)
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activity_logs'")
                if not cursor.fetchone():
                    cursor.execute("""
                        CREATE TABLE activity_logs (
                            id INTEGER NOT NULL PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            action VARCHAR NOT NULL,
                            file_id INTEGER,
                            details VARCHAR,
                            created_at DATETIME,
                            FOREIGN KEY(user_id) REFERENCES users (id),
                            FOREIGN KEY(file_id) REFERENCES files (id)
                        )
                    """)
                
                conn.commit()
                conn.close()
    except Exception as e:
        # If migration fails, log but don't crash
        import logging
        logging.warning(f"Database migration warning: {e}")


@app.get("/", response_class=HTMLResponse)
def landing(
    request: Request,
    current_user: models.User | None = Depends(get_optional_user),
):
    # If user is logged in, show personalized home page (like Google Drive)
    if current_user:
        return templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "user": current_user,
            },
        )
    # Otherwise show public landing page
    return templates.TemplateResponse(
        "landing.html",
        {
            "request": request,
        },
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    current_user: models.User = Depends(get_current_active_user),
):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": current_user},
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/shared/{token}", response_class=HTMLResponse)
def shared_link_page(request: Request, token: str):
    return templates.TemplateResponse("shared.html", {"request": request, "token": token})


@app.get("/admin-panel", response_class=HTMLResponse)
def admin_panel(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@app.get("/favicon.ico")
def favicon():
    # Return a simple 1x1 transparent PNG to avoid 404 errors
    return Response(
        content=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82',
        media_type="image/png"
    )

