"""Defect statistics endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

# NOTE: this router is registered *before* the issues router in app.main so that
# "/issues/stats" is not captured by "/issues/{issue_id}".
router = APIRouter(prefix="/issues", tags=["statistics"])


@router.get(
    "/stats",
    response_model=schemas.StatsResponse,
    summary="Defect counts grouped by status and severity",
)
def get_stats(db: Session = Depends(get_db)) -> dict:
    """Return aggregated counts for status and severity, including empty buckets."""
    return crud.get_stats(db)
