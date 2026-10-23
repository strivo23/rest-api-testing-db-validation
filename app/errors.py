"""Centralised error handling.

Every failure is rendered as a consistent JSON document::

    {"error": {"type": "...", "message": "...", "details": [...]}}

Stack traces, SQL statements and credentials are never returned to the client;
they are only written to the server log.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")

# Pydantic reports the location of a validation error as a tuple whose first
# element is where the value came from ("body", "query", "path", ...). That
# prefix is dropped so that ``error.details[].field`` always names the offending
# parameter itself (for example "title" or "page") regardless of the location.
_REQUEST_LOCATIONS = frozenset({"body", "query", "path", "header", "cookie"})


class APIError(Exception):
    """Application level error carrying an HTTP status code."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        error_type: str = "api_error",
        details: list[dict] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.details = details
        self.headers = headers


def error_body(error_type: str, message: str, details: list[dict] | None = None) -> dict:
    """Build the standard error document."""
    body: dict = {"error": {"type": error_type, "message": message}}
    if details:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the global exception handlers to ``app``."""

    @app.exception_handler(APIError)
    async def _handle_api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.error_type, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(
                    str(part) for part in error.get("loc", ()) if part not in _REQUEST_LOCATIONS
                ),
                "message": error.get("msg", "invalid value"),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body(
                "validation_error", "Request validation failed", details
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body("http_error", str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(SQLAlchemyError)
    async def _handle_database_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        # Logged server side only - the client receives no SQL or connection data.
        logger.error("Database error: %s", exc.__class__.__name__)
        return JSONResponse(
            status_code=500,
            content=error_body(
                "database_error", "A database error occurred while processing the request"
            ),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=error_body("internal_error", "An unexpected error occurred"),
        )
