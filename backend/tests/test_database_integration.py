import json
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


def test_contract_upload_versions_isolation_and_failures(migrated, monkeypatch):
    monkeypatch.setattr("app.projects.get_engine", lambda: migrated)
    specification = {
        "openapi": "3.1.0",
        "info": {"title": "Synthetic", "version": "1"},
        "paths": {},
    }
    with TestClient(app) as client:
        first = client.post("/api/projects", json={"name": "First"}).json()["id"]
        second = client.post("/api/projects", json={"name": "Second"}).json()["id"]
        url = f"/api/projects/{first}/contracts"
        assert client.get(url).json() == []
        created = client.post(
            url,
            params={"version": " v1 ", "source_name": "api-v1.json"},
            content=json.dumps(specification),
            headers={"Content-Type": "application/json"},
        )
        assert created.status_code == 201, created.text
        metadata = created.json()
        assert metadata["version"] == "v1"
        assert metadata["source_name"] == "api-v1.json"
        assert "specification" not in metadata
        assert metadata["created_at"]
        detail = client.get(f"{url}/{metadata['id']}").json()
        assert detail["specification"] == specification
        assert client.get(f"/api/projects/{second}/contracts/{metadata['id']}").status_code == 404
        assert client.get(f"{url}/{uuid4()}").status_code == 404
        assert client.post(f"{url}?version=v1", json=specification).status_code == 409
        # Identical labels are independent in different projects.
        assert (
            client.post(
                f"/api/projects/{second}/contracts?version=v1", json=specification
            ).status_code
            == 201
        )
        yaml_body = 'openapi: 3.0.3\ninfo:\n  title: Synthetic\n  version: "2"\npaths: {}\n'
        candidate = client.post(
            f"{url}?version=v2&source_name=api-v2.yaml",
            content=yaml_body,
            headers={"Content-Type": "application/yaml"},
        )
        assert candidate.status_code == 201, candidate.text
        assert client.get(url, params={"limit": 1}).json() == [candidate.json()]
        assert client.get(url, params={"limit": 1, "offset": 1}).json() == [metadata]
        assert client.get(url, params={"limit": 101}).status_code == 422
        assert client.get(f"/api/projects/{uuid4()}/contracts").status_code == 404
        assert (
            client.post(
                f"/api/projects/{uuid4()}/contracts?version=v1", json=specification
            ).status_code
            == 404
        )
        assert client.post(f"{url}?version=bad", json={"openapi": "3.1.0"}).status_code == 422
        assert (
            client.post(
                f"{url}?version=bad", content=yaml_body, headers={"Content-Type": "text/plain"}
            ).status_code
            == 415
        )
        assert (
            client.post(f"{url}?version=bad&source_name=../x.json", json=specification).status_code
            == 422
        )
        assert client.put(f"{url}/{metadata['id']}", json=specification).status_code == 405
        assert len(client.get(url).json()) == 2
        assert client.get(f"{url}/{metadata['id']}").json() == detail
    with session_scope(migrated) as session:
        assert len(session.scalars(select(ApiContract)).all()) == 3


def test_simultaneous_duplicate_uploads_are_atomic(migrated, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setattr("app.projects.get_engine", lambda: migrated)
    with TestClient(app) as client:
        pid = client.post("/api/projects", json={"name": "Race test"}).json()["id"]

    def upload_once():
        with TestClient(app) as client:
            return client.post(
                f"/api/projects/{pid}/contracts?version=v1",
                json={
                    "openapi": "3.1.0",
                    "info": {"title": "Synthetic", "version": "1"},
                    "paths": {},
                },
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: upload_once(), range(2))) == [201, 409]
    with session_scope(migrated) as session:
        assert len(session.scalars(select(ApiContract)).all()) == 1


def test_failed_contract_commit_rolls_back(migrated, monkeypatch):
    from unittest.mock import patch

    from sqlalchemy.exc import OperationalError

    monkeypatch.setattr("app.projects.get_engine", lambda: migrated)
    with TestClient(app) as client:
        pid = client.post("/api/projects", json={"name": "Rollback test"}).json()["id"]
        with patch(
            "sqlalchemy.orm.Session.commit",
            side_effect=OperationalError("private connection", {}, Exception("private password")),
        ):
            response = client.post(
                f"/api/projects/{pid}/contracts?version=v1",
                json={
                    "openapi": "3.1.0",
                    "info": {"title": "Synthetic", "version": "1"},
                    "paths": {},
                },
            )
        assert response.status_code == 503
        assert "private" not in response.text
        assert client.get(f"/api/projects/{pid}/contracts").json() == []


def test_project_api_persists_lists_selects_and_paginates(migrated):
    from unittest.mock import patch

    with patch("app.projects.get_engine", return_value=migrated), TestClient(app) as client:
        assert client.get("/api/projects").json() == []
        response = client.post(
            "/api/projects", json={"name": "  Customer API  ", "description": "Synthetic demo"}
        )
        assert response.status_code == 201
        first = response.json()
        assert first["name"] == "Customer API"
        assert first["created_at"]
        assert client.get(f"/api/projects/{first['id']}").json() == first
        assert client.get(f"/api/projects/{uuid4()}").status_code == 404
        assert client.get("/api/projects/not-a-uuid").status_code == 422
        second = client.post("/api/projects", json={"name": "Another API"}).json()
        assert client.get("/api/projects?limit=1").json() == [second]
        assert client.get("/api/projects?limit=1&offset=1").json() == [first]
        assert client.get("/api/projects?limit=101").status_code == 422
        assert client.get("/api/projects?offset=-1").status_code == 422
    # A new connection observes committed data, as a browser reload would.
    with session_scope(migrated) as session:
        assert len(session.scalars(select(Project)).all()) == 2


def test_failed_project_commit_returns_error_and_rolls_back(migrated):
    from unittest.mock import patch

    from sqlalchemy.exc import OperationalError

    with (
        patch("app.projects.get_engine", return_value=migrated),
        patch(
            "sqlalchemy.orm.Session.commit",
            side_effect=OperationalError("private connection", {}, Exception("private password")),
        ),
        TestClient(app) as client,
    ):
        response = client.post("/api/projects", json={"name": "Must not be saved"})
        assert response.status_code == 503
        assert "private" not in response.text
    with session_scope(migrated) as session:
        assert list(session.scalars(select(Project))) == []


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


@pytest.fixture
def comparison_client(migrated, monkeypatch):
    monkeypatch.setattr("app.projects.get_engine", lambda: migrated)
    with TestClient(app) as client:
        pid = client.post("/api/projects", json={"name": "Comparison"}).json()["id"]
        ids = []
        for version in ("v1", "v2"):
            spec = {
                "openapi": "3.0.3",
                "info": {"title": "Synthetic", "version": version},
                "paths": {"/customers": {"get": {"responses": {"200": {"description": "OK"}}}}}
                if version == "v1"
                else {},
            }
            uploaded = client.post(f"/api/projects/{pid}/contracts?version={version}", json=spec)
            assert uploaded.status_code == 201, uploaded.text
            ids.append(uploaded.json()["id"])
        yield client, pid, {"baseline_id": ids[0], "candidate_id": ids[1]}


def test_saved_comparison_roundtrip_and_isolation(comparison_client, monkeypatch):
    client, pid, pair = comparison_client
    url = f"/api/projects/{pid}/comparisons"
    created = client.post(url, json=pair)
    assert created.status_code == 201, created.text
    saved = created.json()
    assert saved["change_count"] > 0
    assert any(c["severity"] == "breaking" for c in saved["result"]["changes"])
    reverse = client.post(
        url, json={"baseline_id": pair["candidate_id"], "candidate_id": pair["baseline_id"]}
    )
    assert reverse.status_code == 201, reverse.text
    assert reverse.json()["id"] != saved["id"]

    def unexpected(*args):
        pytest.fail("Cached comparisons must not execute the engine")

    monkeypatch.setattr("app.comparison_service.compare_contracts", unexpected)
    cached = client.post(url, json=pair)
    assert cached.status_code == 200
    assert cached.json() == saved
    assert client.get(f"{url}/{saved['id']}").json() == saved
    change = saved["result"]["changes"][0]
    assert client.get(f"{url}/{saved['id']}/changes/{change['id']}").json() == change
    assert client.get(f"{url}/{saved['id']}/changes/{'0' * 64}").status_code == 404
    listing = client.get(url, params={"limit": 1, "offset": 1}).json()
    assert listing[0]["id"] == saved["id"]
    assert "result" not in listing[0]
    assert client.get(url, params={"limit": 101}).status_code == 422
    other = client.post("/api/projects", json={"name": "Other"}).json()["id"]
    other_url = f"/api/projects/{other}/comparisons"
    assert client.post(other_url, json=pair).status_code == 404
    assert client.get(f"{other_url}/{saved['id']}").status_code == 404
    assert client.get(f"{other_url}/{saved['id']}/changes/{change['id']}").status_code == 404
    assert client.post(url, json=pair | {"candidate_id": pair["baseline_id"]}).status_code == 422
    assert client.post(url, json=pair | {"candidate_id": str(uuid4())}).status_code == 404
    assert client.post(url, json=pair | {"command": "ignored"}).status_code == 422
    assert client.get(f"/api/projects/{uuid4()}/comparisons").status_code == 404


@pytest.mark.parametrize(
    "code,status", [("timeout", 504), ("busy", 503), ("engine_failed", 503), ("invalid_input", 422)]
)
def test_failed_comparison_has_no_partial_record(comparison_client, monkeypatch, code, status):
    from app.comparison import ComparisonError

    client, pid, pair = comparison_client

    def fail(*args):
        raise ComparisonError(code)

    monkeypatch.setattr("app.comparison_service.compare_contracts", fail)
    url = f"/api/projects/{pid}/comparisons"
    response = client.post(url, json=pair)
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert client.get(url).json() == []


def test_comparison_commit_failure_rolls_back(comparison_client, monkeypatch):
    from unittest.mock import patch

    from sqlalchemy.exc import OperationalError

    client, pid, pair = comparison_client
    url = f"/api/projects/{pid}/comparisons"
    with patch(
        "sqlalchemy.orm.Session.commit",
        side_effect=OperationalError("private", {}, Exception("private")),
    ):
        response = client.post(url, json=pair)
    assert response.status_code == 503
    assert "private" not in response.text
    assert client.get(url).json() == []


def test_comparison_race_reuses_one_record(comparison_client, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.comparison import compare_contracts

    client, pid, pair = comparison_client
    barrier = Barrier(2)

    def synchronized(*args):
        result = compare_contracts(*args)
        barrier.wait(timeout=15)
        return result

    monkeypatch.setattr("app.comparison_service.compare_contracts", synchronized)
    url = f"/api/projects/{pid}/comparisons"

    def create_once(_):
        with TestClient(app) as concurrent_client:
            return concurrent_client.post(url, json=pair)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(create_once, range(2)))
    assert sorted(r.status_code for r in responses) == [200, 201], [r.text for r in responses]
    assert responses[0].json() == responses[1].json()
    assert len(client.get(url).json()) == 1


def test_comparison_downgrade_preserves_contracts(comparison_client, migrated):
    client, pid, pair = comparison_client
    assert client.post(f"/api/projects/{pid}/comparisons", json=pair).status_code == 201
    migrate(migrated, "downgrade", "0001_projects_contracts")
    with migrated.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM api_contracts")) == 2
        assert conn.scalar(text("SELECT count(*) FROM projects")) == 1
    migrate(migrated, "upgrade", "head")
    assert client.get(f"/api/projects/{pid}/comparisons").json() == []


def test_comparison_foreign_keys_enforce_project_boundary(comparison_client, migrated):
    from uuid import UUID

    from app.db.models import ContractComparison

    client, pid, pair = comparison_client
    other = client.post("/api/projects", json={"name": "Other"}).json()["id"]
    with pytest.raises(IntegrityError), session_scope(migrated) as session:
        session.add(
            ContractComparison(
                project_id=UUID(other),
                baseline_id=UUID(pair["baseline_id"]),
                candidate_id=UUID(pair["candidate_id"]),
                engine_version="test",
                normalization_version=1,
                change_count=0,
                result={},
            )
        )


def test_document_ingestion_citations_idempotency_and_isolation(migrated, monkeypatch):
    monkeypatch.setattr("app.projects.get_engine", lambda: migrated)
    params = {
        "provider": "demo",
        "api_version": "v1",
        "document_type": "migration",
        "source_ref": "https://example.invalid/guide.md",
    }
    body = "é" * 2001 + "\n<script>untrusted</script>"
    with TestClient(app) as client:
        first = client.post("/api/projects", json={"name": "First"}).json()["id"]
        second = client.post("/api/projects", json={"name": "Second"}).json()["id"]
        url = f"/api/projects/{first}/documents"

        def upload(content=body, **options):
            return client.post(
                url,
                params=params,
                content=content.encode(),
                headers={"Content-Type": "text/markdown"},
                **options,
            )

        created = upload()
        assert created.status_code == 201, created.text
        doc = created.json()
        assert all(doc[key] == value for key, value in params.items())
        assert upload().status_code == 200
        assert upload().json() == doc
        chunks = client.get(f"{url}/{doc['id']}/chunks").json()
        assert len(chunks) == 2
        assert "".join(c["content"] for c in chunks) == body
        assert [(c["start_char"], c["end_char"]) for c in chunks] == [(0, 2000), (2000, len(body))]
        assert (
            client.get(f"{url}/{doc['id']}/chunks", params={"limit": 1, "offset": 1}).json()
            == chunks[1:]
        )
        assert upload("changed").status_code == 409
        assert client.get(f"{url}/{doc['id']}/chunks").json() == chunks
        assert client.get(url).json() == [doc]
        assert client.get(f"/api/projects/{second}/documents").json() == []
        assert client.get(f"/api/projects/{second}/documents/{doc['id']}").status_code == 404
        assert client.get(f"/api/projects/{second}/documents/{doc['id']}/chunks").status_code == 404
        other = client.post(
            f"/api/projects/{second}/documents",
            params=params,
            content=body.encode(),
            headers={"Content-Type": "text/markdown"},
        )
        assert other.status_code == 201
        assert other.json()["id"] != doc["id"]
        assert upload(" ").status_code == 422
        assert (
            client.post(
                url, params=params, content=b"x", headers={"Content-Type": "application/pdf"}
            ).status_code
            == 415
        )
        assert (
            client.post(
                url,
                params=params,
                content=b"x",
                headers={"Content-Type": "text/plain", "Content-Encoding": "gzip"},
            ).status_code
            == 415
        )
        assert client.get(f"/api/projects/{uuid4()}/documents").status_code == 404
        assert client.get(f"{url}/{doc['id']}/chunks", params={"limit": 101}).status_code == 422


def test_document_failed_commit_leaves_no_partial_chunks(migrated, monkeypatch):
    from unittest.mock import patch

    from sqlalchemy.exc import OperationalError

    from app.db.models import Document, DocumentChunk

    monkeypatch.setattr("app.projects.get_engine", lambda: migrated)
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "Rollback"}).json()["id"]
        with patch(
            "sqlalchemy.orm.Session.commit",
            side_effect=OperationalError("private host", {}, Exception("private password")),
        ):
            response = client.post(
                f"/api/projects/{project}/documents",
                params={
                    "provider": "demo",
                    "api_version": "v1",
                    "document_type": "guide",
                    "source_ref": "guide.md",
                },
                content=b"synthetic",
                headers={"Content-Type": "text/plain"},
            )
        assert response.status_code == 503
        assert "private" not in response.text
    with session_scope(migrated) as session:
        assert list(session.scalars(select(Document))) == []
        assert list(session.scalars(select(DocumentChunk))) == []


def test_concurrent_document_retries_create_one_chunk_set(migrated):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.db.models import DocumentChunk
    from app.document_service import DocumentMetadata, ingest_document

    project = uuid4()
    with session_scope(migrated) as session:
        session.add(Project(id=project, name="Concurrent"))
    barrier = Barrier(2)
    metadata = DocumentMetadata(
        provider="demo", api_version="v1", document_type="guide", source_ref="guide.md"
    )

    def upload():
        with session_scope(migrated) as session:
            barrier.wait(timeout=10)
            return ingest_document(session, project, metadata, b"synthetic", "text/plain")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: upload(), range(2)))
    assert sorted(created for _, created in results) == [False, True]
    assert results[0][0] == results[1][0]
    with session_scope(migrated) as session:
        assert len(list(session.scalars(select(DocumentChunk)))) == 1


def test_knowledge_retrieval_filters_scores_limits_and_tools(migrated, monkeypatch):
    from app.code_search import RepositorySearch
    from app.document_service import DocumentMetadata, ingest_document
    from app.knowledge import KnowledgeSearch
    from app.tool_registry import ToolRegistry, response_adapter

    first, second = uuid4(), uuid4()
    with session_scope(migrated) as session:
        session.add_all([Project(id=first, name="First"), Project(id=second, name="Second")])

    def ingest(project, version, provider, kind, ref, body):
        with session_scope(migrated) as session:
            return ingest_document(
                session,
                project,
                DocumentMetadata(
                    api_version=version,
                    provider=provider,
                    document_type=kind,
                    source_ref=ref,
                ),
                body.encode(),
                "text/plain",
            )[0]

    wanted = ingest(first, "v2", "demo", "migration", "migration.md", "rename customer field")
    ingest(first, "v2", "demo", "migration", "repeat.md", "rename customer field " * 50)
    ingest(first, "v1", "demo", "migration", "old.md", "rename customer field " * 60)
    ingest(second, "v2", "demo", "migration", "secret.md", "rename customer field " * 60)
    ingest(first, "v2", "other", "migration", "other.md", "rename customer field")
    ingest(first, "v2", "demo", "guide", "guide.md", "rename customer field")
    monkeypatch.setattr("app.knowledge_api.get_engine", lambda: migrated)
    monkeypatch.setattr("app.projects.get_engine", lambda: migrated)
    params = {
        "query": "RENAME customer",
        "api_version": "v2",
        "provider": "demo",
        "document_type": "migration",
        "limit": 1,
    }
    url = f"/api/projects/{first}/knowledge/search"
    with TestClient(app) as client:
        response = client.get(url, params=params)
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["truncated"]
        assert len(result["hits"]) == 1
        assert result["hits"][0]["source_ref"] == "repeat.md"
        assert result["hits"][0]["score"] > 0
        assert result == client.get(url, params=params).json()
        all_hits = client.get(url, params=params | {"limit": 20}).json()
        assert not all_hits["truncated"]
        assert {h["source_ref"] for h in all_hits["hits"]} == {"migration.md", "repeat.md"}
        hit = next(h for h in all_hits["hits"] if h["document_id"] == str(wanted.id))
        chunk = client.get(f"/api/projects/{first}/documents/{wanted.id}/chunks").json()[0]
        assert hit["source_id"] == chunk["id"]
        assert hit["snippet"] == chunk["content"]
        assert (hit["start_char"], hit["end_char"]) == (chunk["start_char"], chunk["end_char"])
        for query in ["missing", "!!!", "'; DROP TABLE documents; --"]:
            empty = client.get(url, params=params | {"query": query}).json()
            assert empty["hits"] == []
        assert client.get(url, params=params | {"api_version": "v9"}).json()["hits"] == []
        assert client.get(url, params=params | {"limit": 21}).status_code == 422
        assert (
            client.get(f"/api/projects/{uuid4()}/knowledge/search", params=params).status_code
            == 404
        )
    registry = ToolRegistry(RepositorySearch({}), KnowledgeSearch(migrated, first))
    evidence = registry.invoke({"operation": "search_knowledge", **params})
    assert evidence.status == "ok"
    assert evidence.result.model_dump(mode="json") == result
    assert response_adapter.validate_json(evidence.model_dump_json()) == evidence
    assert (
        registry.invoke(
            {"operation": "search_knowledge", **params, "project_id": str(second)}
        ).status
        == "rejected"
    )


def test_document_search_migration_backfills_existing_chunks(engine):
    migrate(engine, "upgrade", "0003_documents")
    project, document, chunk = uuid4(), uuid4(), uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO projects (id,name) VALUES (:id,'Existing')"), {"id": project}
        )
        connection.execute(
            text("""INSERT INTO documents
            (id,project_id,provider,api_version,document_type,source_ref,media_type,content_sha256,chunking_version)
            VALUES (:id,:project,'demo','v1','guide','existing.md','text/plain',:digest,1)"""),
            {"id": document, "project": project, "digest": "a" * 64},
        )
        connection.execute(
            text("""INSERT INTO document_chunks
            (id,document_id,ordinal,start_char,end_char,content)
            VALUES (:id,:document,0,0,8,'customer')"""),
            {"id": chunk, "document": document},
        )
    migrate(engine, "upgrade", "head")
    from app.knowledge import KnowledgeSearch
    from app.knowledge_schemas import KnowledgeRequest

    result = KnowledgeSearch(engine, project).search(
        KnowledgeRequest(query="customer", api_version="v1")
    )
    assert result.hits[0].source_id == chunk
    with engine.connect() as connection:
        assert "ix_document_chunks_search" in {
            i["name"] for i in inspect(connection).get_indexes("document_chunks")
        }
    migrate(engine, "downgrade", "0003_documents")
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT content FROM document_chunks WHERE id=:id"), {"id": chunk}
            )
            == "customer"
        )
    migrate(engine, "downgrade", "base")
