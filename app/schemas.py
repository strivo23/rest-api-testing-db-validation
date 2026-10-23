"""Pydantic schemas: request validation and response serialization."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import Category, Environment, Severity, Status


class IssueBase(BaseModel):
    """Fields shared by the create request and the stored representation."""

    title: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Short summary of the defect (3-200 characters)",
        examples=["Login fails with valid credentials"],
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
        description="Optional detailed description or reproduction notes",
        examples=["Steps: open /login, submit valid credentials, page stays blank."],
    )
    severity: Severity = Field(..., description="Impact of the defect")
    status: Status = Field(..., description="Current workflow state")
    category: Category = Field(..., description="Area the defect belongs to")
    environment: Environment = Field(..., description="Platform where it was observed")

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("title must contain at least 3 non-whitespace characters")
        return cleaned

    @field_validator("description")
    @classmethod
    def _normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class IssueCreate(IssueBase):
    """Payload accepted by ``POST /issues``."""


class IssueUpdate(BaseModel):
    """Payload accepted by ``PATCH /issues/{id}`` - every field is optional."""

    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    severity: Severity | None = None
    status: Status | None = None
    category: Category | None = None
    environment: Environment | None = None

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("title must contain at least 3 non-whitespace characters")
        return cleaned

    @field_validator("description")
    @classmethod
    def _normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "IssueUpdate":
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided for the update")
        return self


class IssueRead(BaseModel):
    """Representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    severity: Severity
    status: Status
    category: Category
    environment: Environment
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _ensure_utc(cls, value: datetime) -> datetime:
        """Always expose UTC timestamps, even when the driver returns naive ones."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class IssueListResponse(BaseModel):
    """Paginated list of defects."""

    total: int = Field(..., description="Total number of defects matching the filters")
    page: int
    page_size: int
    pages: int = Field(..., description="Total number of pages for the current page size")
    items: list[IssueRead]


class StatsResponse(BaseModel):
    """Aggregated defect counts."""

    total: int
    by_status: dict[str, int] = Field(..., description="Counts keyed by status value")
    by_severity: dict[str, int] = Field(..., description="Counts keyed by severity value")


class HealthResponse(BaseModel):
    """Health check payload."""

    status: str = Field(..., description="'ok' when the API and database are reachable")
    database: str = Field(..., description="'connected' when a SELECT 1 succeeded")
    dialect: str | None = Field(default=None, description="Database dialect name")
    version: str


class ErrorDetail(BaseModel):
    """Consistent error body returned for every failing request."""

    type: str = Field(..., description="Machine readable error type")
    message: str = Field(..., description="Human readable error message")
    details: list[dict] | None = Field(default=None, description="Field level validation errors")


class ErrorResponse(BaseModel):
    """Wrapper so that errors are always nested under an ``error`` key."""

    error: ErrorDetail
