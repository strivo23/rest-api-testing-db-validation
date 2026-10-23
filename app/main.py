"""FastAPI application entry point.

Run locally with::

    uvicorn app.main:app --reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import Base, engine
from app.errors import register_exception_handlers
from app.routes import health, issues, stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("app.main")

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Optionally create missing tables (AUTO_CREATE_TABLES=true)."""
    if settings.auto_create_tables:
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Tables ensured via AUTO_CREATE_TABLES")
        except Exception as exc:  # pragma: no cover - depends on the local database
            logger.error("Could not create tables at startup: %s", exc.__class__.__name__)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.description,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# "/issues/stats" must be matched before "/issues/{issue_id}".
app.include_router(health.router)
app.include_router(stats.router)
app.include_router(issues.router)

static_dir = Path(__file__).resolve().parent / "static"
if static_dir.is_dir():  # pragma: no branch - dashboard is optional
    app.mount("/dashboard", StaticFiles(directory=static_dir, html=True), name="dashboard")


@app.get("/", include_in_schema=False)
def root() -> dict:
    """Small discovery document for humans and Postman smoke checks."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "dashboard": "/dashboard/",
        "health": "/health",
        "issues": "/issues",
    }
