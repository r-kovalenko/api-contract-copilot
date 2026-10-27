import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import inspect, make_url, select, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.db.models import ApiContract, Base, Project
from app.db.readiness import database_ready
from app.db.repositories import get_contract
from app.db.session import create_database_engine, session_scope
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def engine():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        if os.environ.get("REQUIRE_DATABASE_TESTS") == "1":
            pytest.fail("TEST_DATABASE_URL is required in CI")
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test")
    url = make_url(value)
    if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith("_test"):
        pytest.fail("Integration tests require a disposable PostgreSQL database ending in _test")
    db = create_database_engine(url)
    # Never run destructive migration tests against an existing application schema.
    with db.connect() as conn:
        if inspect(conn).get_table_names():
            pytest.fail("Integration test database must be empty")
    yield db
    db.dispose()


def migrate(engine, direction, revision):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        getattr(command, direction)(config, revision)


@pytest.fixture
def migrated(engine):
    migrate(engine, "upgrade", "head")
    yield engine
    migrate(engine, "downgrade", "base")


def contract(project_id, **overrides):
    values = {
        "project_id": project_id,
        "version": "v1",
        "openapi_version": "3.1.0",
        "specification": {"openapi": "3.1.0", "info": {"title": "Synthetic", "version": "v1"}},
    }
    return ApiContract(**(values | overrides))


def test_migrations_round_trip_and_metadata_match(engine):
    assert not database_ready(engine)
    migrate(engine, "upgrade", "head")
    assert database_ready(engine)
    with engine.connect() as conn:
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
        assert conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
    migrate(engine, "downgrade", "base")
    assert not database_ready(engine)
    with engine.connect() as conn:
        assert "projects" not in inspect(conn).get_table_names()
        assert conn.scalar(text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")) == 1
    migrate(engine, "upgrade", "head")
    assert database_ready(engine)
    migrate(engine, "downgrade", "base")


def test_project_scoped_versions_and_evidence(migrated):
    first, second = uuid4(), uuid4()
    cid = uuid4()
    with session_scope(migrated) as session:
        session.add_all([Project(id=first, name="First"), Project(id=second, name="Second")])
        session.flush()
        session.add_all([contract(first, id=cid), contract(second)])
    with session_scope(migrated) as session:
        found = get_contract(session, project_id=first, contract_id=cid)
        assert found.specification["openapi"] == "3.1.0"
        assert found.created_at.tzinfo is not None
        assert get_contract(session, project_id=second, contract_id=cid) is None
    with pytest.raises(IntegrityError), session_scope(migrated) as session:
        session.add(contract(first))
    with session_scope(migrated) as session:
        assert len(session.scalars(select(ApiContract)).all()) == 2


def test_foreign_key_restriction_and_transaction_rollback(migrated):
    pid = uuid4()
    with pytest.raises(IntegrityError), session_scope(migrated) as session:
        session.add(Project(id=pid, name="Must roll back"))
        session.flush()
        session.add(contract(uuid4()))
    with session_scope(migrated) as session:
        assert session.get(Project, pid) is None
        session.add(Project(id=pid, name="Retained"))
        session.flush()
        session.add(contract(pid))
    with pytest.raises(IntegrityError), session_scope(migrated) as session:
        session.delete(session.get(Project, pid))


@pytest.mark.parametrize(
    "overrides", [{"version": " "}, {"openapi_version": "2.0"}, {"specification": []}]
)
def test_contract_constraints(migrated, overrides):
    pid = uuid4()
    with session_scope(migrated) as session:
        session.add(Project(id=pid, name="Synthetic"))
    with pytest.raises(IntegrityError), session_scope(migrated) as session:
        session.add(contract(pid, **overrides))


def test_ready_endpoint_requires_migrations(engine, monkeypatch):
    monkeypatch.setattr("app.main.get_engine", lambda: engine)
    with TestClient(app) as client:
        assert client.get("/api/ready").status_code == 503
        migrate(engine, "upgrade", "head")
        assert client.get("/api/ready").json()["status"] == "ready"
        migrate(engine, "downgrade", "base")
        assert client.get("/api/ready").status_code == 503


def test_documented_migration_cli_uses_environment_configuration(engine):
    env = os.environ.copy()
    env["DATABASE_URL"] = engine.url.render_as_string(hide_password=False)
    for arguments in (("upgrade", "head"), ("check",), ("downgrade", "base")):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", *arguments],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
