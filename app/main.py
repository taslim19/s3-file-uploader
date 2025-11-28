from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import models
from app.auth import get_current_active_user
from app.database import Base, engine
from app.routers import admin, files, users

app = FastAPI(title="Mini Cloud Drive")

app.include_router(users.router)
app.include_router(files.router)
app.include_router(admin.router)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
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


@app.get("/admin-panel", response_class=HTMLResponse)
def admin_panel(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

