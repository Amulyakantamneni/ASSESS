# app/main.py
# FastAPI app: mounts routers, static frontend, session + rate-limit middleware.

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import SESSION_SECRET
from app.routers import leads, industries, assessments, dashboard, admin

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = BASE_DIR / "public"

limiter = Limiter(key_func=get_remote_address, default_limits=["100/15minute"])

app = FastAPI(title="KVH Assessment Platform")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
app.add_middleware(SlowAPIMiddleware)

app.include_router(leads.router)
app.include_router(industries.router)
app.include_router(assessments.router)
app.include_router(dashboard.router)
app.include_router(admin.router)


@app.get("/api/health")
async def health():
    return {"ok": True, "status": "healthy"}


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=404, content={"ok": False, "errors": ["Not found."]})
    # SPA-style fallback for non-API routes (deep links to client-rendered pages)
    index = PUBLIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(status_code=404, content={"ok": False, "errors": ["Not found."]})


# Pretty routes for the multi-page frontend
@app.get("/dashboard")
async def dashboard_page():
    return FileResponse(PUBLIC_DIR / "dashboard.html")


@app.get("/assessment")
async def assessment_page():
    return FileResponse(PUBLIC_DIR / "assessment.html")


@app.get("/connect")
async def connect_page():
    return FileResponse(PUBLIC_DIR / "connect.html")


@app.get("/admin")
async def admin_page():
    return FileResponse(PUBLIC_DIR / "admin" / "index.html")


@app.get("/admin/login")
async def admin_login_page():
    return FileResponse(PUBLIC_DIR / "admin" / "login.html")


# Static assets (CSS/JS baked into the HTML files) + serves index.html at "/"
app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="static")
