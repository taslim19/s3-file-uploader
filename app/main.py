from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, Response
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

