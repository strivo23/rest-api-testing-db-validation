"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check and database connectivity status",
    responses={503: {"description": "Database is unreachable"}},
)
def health_check(db: Session = Depends(get_db)):
    """Report API liveness plus whether the configured database answers ``SELECT 1``."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "unavailable",
                "dialect": None,
                "version": settings.app_version,
            },
        )

    return {
        "status": "ok",
        "database": "connected",
        "dialect": db.bind.dialect.name if db.bind is not None else None,
        "version": settings.app_version,
    }
