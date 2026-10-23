"""Schema initialisation helper.

Usage::

    python -m app.db_init

Creates every table declared on :class:`app.database.Base` using the
``DATABASE_URL`` from the environment / ``.env`` file.
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect

from app import models  # noqa: F401  (imported so the models are registered)
from app.database import Base, engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("app.db_init")


def init_db() -> list[str]:
    """Create all tables (idempotent) and return the table names."""
    Base.metadata.create_all(bind=engine)
    tables = sorted(inspect(engine).get_table_names())
    return tables


def main() -> None:
    logger.info("Creating tables on %s", engine.url.render_as_string(hide_password=True))
    tables = init_db()
    logger.info("Tables available: %s", ", ".join(tables) or "(none)")


if __name__ == "__main__":  # pragma: no cover
    main()
