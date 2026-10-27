import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import URL, Engine, create_engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session


def database_url() -> URL:
    """Read server-only settings without including credentials in validation errors."""
    value = os.environ.get("DATABASE_URL")
    try:
        if value:
            url = make_url(value)
        elif os.environ.get("PGHOST") and os.environ.get("POSTGRES_PASSWORD"):
            url = URL.create(
                "postgresql+psycopg",
                username=os.environ.get("POSTGRES_USER", "copilot"),
                password=os.environ["POSTGRES_PASSWORD"],
                host=os.environ["PGHOST"],
                port=int(os.environ.get("PGPORT", "5432")),
                database=os.environ.get("POSTGRES_DB", "copilot"),
            )
        else:
            raise ValueError("Database configuration is missing")
        if url.drivername not in {"postgresql", "postgresql+psycopg"} or not url.database:
            raise ValueError("Unsupported database URL")
        return url.set(drivername="postgresql+psycopg")
    except (ArgumentError, ValueError, TypeError):
        raise ValueError(
            "Configure a valid PostgreSQL DATABASE_URL or Compose database settings"
        ) from None


def create_database_engine(url: URL) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=0,
        pool_timeout=3,
        hide_parameters=True,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"},
    )


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_database_engine(database_url())


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """Commit successful service work; roll back failed work and always close."""
    with Session(engine) as session, session.begin():
        yield session
