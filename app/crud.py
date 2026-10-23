"""Business logic / data access layer for defect records.

The functions below only talk to the database - they never raise HTTP errors,
which keeps the routing layer thin and the logic unit testable.
"""

from __future__ import annotations

import math
from typing import Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app import models, schemas

#: Columns that clients are allowed to sort by.
SORTABLE_COLUMNS = ("id", "title", "severity", "status", "category", "environment", "created_at", "updated_at")


def create_issue(db: Session, payload: schemas.IssueCreate) -> models.Issue:
    """Persist a new defect and return the stored row."""
    issue = models.Issue(**payload.model_dump())
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


def get_issue(db: Session, issue_id: int) -> models.Issue | None:
    """Return a single defect or ``None`` when it does not exist."""
    return db.get(models.Issue, issue_id)


def _apply_filters(
    stmt: Select,
    *,
    severity: str | None = None,
    status: str | None = None,
    category: str | None = None,
    environment: str | None = None,
    search: str | None = None,
) -> Select:
    """Attach optional WHERE clauses to ``stmt``."""
    if severity:
        stmt = stmt.where(models.Issue.severity == severity)
    if status:
        stmt = stmt.where(models.Issue.status == status)
    if category:
        stmt = stmt.where(models.Issue.category == category)
    if environment:
        stmt = stmt.where(models.Issue.environment == environment)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(models.Issue.title.ilike(pattern), models.Issue.description.ilike(pattern))
        )
    return stmt


def list_issues(
    db: Session,
    *,
    severity: str | None = None,
    status: str | None = None,
    category: str | None = None,
    environment: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "created_at",
    order: str = "desc",
) -> tuple[Sequence[models.Issue], int]:
    """Return ``(items, total)`` for the requested page of defects."""
    filters = {
        "severity": severity,
        "status": status,
        "category": category,
        "environment": environment,
        "search": search,
    }

    total = db.scalar(_apply_filters(select(func.count()).select_from(models.Issue), **filters)) or 0

    column_name = sort_by if sort_by in SORTABLE_COLUMNS else "created_at"
    column = getattr(models.Issue, column_name)
    ordering = column.asc() if order == "asc" else column.desc()

    stmt = _apply_filters(select(models.Issue), **filters)
    # ``id`` is appended as a tie-breaker so pagination stays deterministic.
    stmt = stmt.order_by(ordering, models.Issue.id.desc()).offset((page - 1) * page_size).limit(page_size)

    return db.scalars(stmt).all(), int(total)


def total_pages(total: int, page_size: int) -> int:
    """Number of pages required to expose ``total`` records."""
    if page_size <= 0:
        return 0
    return math.ceil(total / page_size)


def update_issue(db: Session, issue: models.Issue, payload: schemas.IssueUpdate) -> models.Issue:
    """Apply a partial update to ``issue`` and return the refreshed row."""
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(issue, field, value)
    issue.updated_at = models.utcnow()
    db.commit()
    db.refresh(issue)
    return issue


def delete_issue(db: Session, issue: models.Issue) -> None:
    """Delete ``issue`` from the database."""
    db.delete(issue)
    db.commit()


def get_stats(db: Session) -> dict:
    """Return defect counts grouped by status and by severity."""
    by_status = {
        value: 0 for value in models.STATUS_VALUES
    }
    by_severity = {value: 0 for value in models.SEVERITY_VALUES}

    for value, count in db.execute(
        select(models.Issue.status, func.count(models.Issue.id)).group_by(models.Issue.status)
    ):
        by_status[value] = int(count)

    for value, count in db.execute(
        select(models.Issue.severity, func.count(models.Issue.id)).group_by(models.Issue.severity)
    ):
        by_severity[value] = int(count)

    total = db.scalar(select(func.count()).select_from(models.Issue)) or 0
    return {"total": int(total), "by_status": by_status, "by_severity": by_severity}
