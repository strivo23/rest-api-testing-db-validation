"""CRUD endpoints for defect records."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.config import get_settings
from app.database import get_db
from app.errors import APIError

router = APIRouter(prefix="/issues", tags=["issues"])
settings = get_settings()


def _get_issue_or_404(db: Session, issue_id: int) -> models.Issue:
    """Fetch a defect or raise a 404 APIError."""
    issue = crud.get_issue(db, issue_id)
    if issue is None:
        raise APIError(
            f"Issue with id {issue_id} was not found",
            status_code=status.HTTP_404_NOT_FOUND,
            error_type="not_found",
        )
    return issue


@router.post(
    "",
    response_model=schemas.IssueRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a defect",
    responses={422: {"description": "Validation error"}, 500: {"description": "Database error"}},
)
def create_issue(payload: schemas.IssueCreate, db: Session = Depends(get_db)) -> models.Issue:
    """Create a new defect record and return it with the generated id."""
    return crud.create_issue(db, payload)


@router.get(
    "",
    response_model=schemas.IssueListResponse,
    summary="List defects with pagination, filtering and sorting",
)
def list_issues(
    severity: models.Severity | None = Query(default=None, description="Filter by severity"),
    status_filter: models.Status | None = Query(
        default=None, alias="status", description="Filter by status"
    ),
    category: models.Category | None = Query(default=None, description="Filter by category"),
    environment: models.Environment | None = Query(
        default=None, description="Filter by environment"
    ),
    search: str | None = Query(default=None, max_length=200, description="Case-insensitive text search in title/description"),
    page: int = Query(default=1, ge=1, description="Page number, starting at 1"),
    page_size: int = Query(
        default=settings.default_page_size,
        ge=1,
        le=settings.max_page_size,
        description="Records per page",
    ),
    sort_by: Literal[
        "id", "title", "severity", "status", "category", "environment", "created_at", "updated_at"
    ] = Query(default="created_at", description="Column used for sorting"),
    order: Literal["asc", "desc"] = Query(default="desc", description="Sort direction"),
    db: Session = Depends(get_db),
) -> schemas.IssueListResponse:
    """Return a filtered, sorted and paginated page of defects."""
    items, total = crud.list_issues(
        db,
        severity=severity.value if severity else None,
        status=status_filter.value if status_filter else None,
        category=category.value if category else None,
        environment=environment.value if environment else None,
        search=search,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        order=order,
    )
    return schemas.IssueListResponse(
        total=total,
        page=page,
        page_size=page_size,
        pages=crud.total_pages(total, page_size),
        items=[schemas.IssueRead.model_validate(item) for item in items],
    )


@router.get(
    "/{issue_id}",
    response_model=schemas.IssueRead,
    summary="Retrieve one defect",
    responses={404: {"description": "Defect not found"}},
)
def get_issue(issue_id: int, db: Session = Depends(get_db)) -> models.Issue:
    """Return a single defect by its identifier."""
    return _get_issue_or_404(db, issue_id)


@router.patch(
    "/{issue_id}",
    response_model=schemas.IssueRead,
    summary="Partially update a defect",
    responses={404: {"description": "Defect not found"}, 422: {"description": "Validation error"}},
)
def patch_issue(
    issue_id: int, payload: schemas.IssueUpdate, db: Session = Depends(get_db)
) -> models.Issue:
    """Update only the fields that were sent in the request body."""
    issue = _get_issue_or_404(db, issue_id)
    return crud.update_issue(db, issue, payload)


@router.delete(
    "/{issue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a defect",
    responses={404: {"description": "Defect not found"}},
)
def delete_issue(issue_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete a defect; responds with 204 and an empty body."""
    issue = _get_issue_or_404(db, issue_id)
    crud.delete_issue(db, issue)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
