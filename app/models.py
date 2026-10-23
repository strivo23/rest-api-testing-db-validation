"""SQLAlchemy ORM models and the enumerated domain values."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Severity(str, enum.Enum):
    """Defect severity levels."""

    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class Status(str, enum.Enum):
    """Defect workflow states."""

    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    CLOSED = "Closed"


class Category(str, enum.Enum):
    """Defect categories."""

    FUNCTIONAL = "Functional"
    UI = "UI"
    API = "API"
    PERFORMANCE = "Performance"
    SECURITY = "Security"


class Environment(str, enum.Enum):
    """Platform / environment where the defect was observed."""

    WEB = "Web"
    ANDROID = "Android"
    IOS = "iOS"
    LINUX = "Linux"
    BACKEND_API = "Backend API"


SEVERITY_VALUES: tuple[str, ...] = tuple(item.value for item in Severity)
STATUS_VALUES: tuple[str, ...] = tuple(item.value for item in Status)
CATEGORY_VALUES: tuple[str, ...] = tuple(item.value for item in Category)
ENVIRONMENT_VALUES: tuple[str, ...] = tuple(item.value for item in Environment)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    """Build a ``column IN (...)`` SQL fragment for CHECK constraints."""
    joined = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({joined})"


class Issue(Base):
    """A single software defect record."""

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default=Severity.MEDIUM.value)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=Status.OPEN.value)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default=Category.FUNCTIONAL.value)
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default=Environment.WEB.value)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        # Business rules mirrored at database level so that raw SQL inserts
        # (and any future client) cannot break data integrity.
        CheckConstraint(
            "length(title) >= 3 AND length(title) <= 200", name="ck_issues_title_length"
        ),
        CheckConstraint(_in_list("severity", SEVERITY_VALUES), name="ck_issues_severity"),
        CheckConstraint(_in_list("status", STATUS_VALUES), name="ck_issues_status"),
        CheckConstraint(_in_list("category", CATEGORY_VALUES), name="ck_issues_category"),
        CheckConstraint(_in_list("environment", ENVIRONMENT_VALUES), name="ck_issues_environment"),
        # Indexes for the columns that are filtered / sorted most often.
        Index("ix_issues_severity", "severity"),
        Index("ix_issues_status", "status"),
        Index("ix_issues_category", "category"),
        Index("ix_issues_environment", "environment"),
        Index("ix_issues_created_at", "created_at"),
        Index("ix_issues_status_severity", "status", "severity"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<Issue id={self.id} severity={self.severity!r} status={self.status!r}>"
