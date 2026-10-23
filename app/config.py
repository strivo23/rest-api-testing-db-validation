"""Application settings loaded from environment variables / the .env file."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Every value can be overridden through an environment variable of the same
    name (upper case) or through a local ``.env`` file.  No credential is ever
    hardcoded: the default below only points at a *local* PostgreSQL instance
    and must be replaced through the ``DATABASE_URL`` variable.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "REST API Testing & Database Validation Platform"
    app_version: str = "1.0.0"
    description: str = (
        "Defect-tracking REST API with PostgreSQL persistence, automated test "
        "coverage and database validation assets."
    )

    # --- Database ---------------------------------------------------------
    database_url: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/defect_tracker"
    )
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    auto_create_tables: bool = False

    # --- API --------------------------------------------------------------
    cors_origins: str = "*"
    default_page_size: int = 20
    max_page_size: int = 100

    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS origins as a list (``*`` means "allow everything")."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
