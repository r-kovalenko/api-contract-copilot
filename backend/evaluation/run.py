"""Run real PostgreSQL retrieval and pinned oasdiff on the versioned synthetic corpus."""

import argparse
import hashlib
import os
from pathlib import Path

from alembic.config import Config
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Engine, inspect, make_url, select, text
from sqlalchemy.exc import ArgumentError, SQLAlchemyError

from alembic import command
from app.comparison import ComparisonError, compare_contracts
from app.db.models import Project
from app.db.session import create_database_engine, session_scope
from app.document_service import ingest_document
from app.embedding_provider import FakeEmbeddingProvider
from app.embedding_service import index_document
from app.knowledge import KnowledgeError, KnowledgeSearch
from evaluation.dataset import Dataset, ExpectedChange, load_dataset
from evaluation.metrics import (
    ContractScore,
    ResultModel,
    RetrievalScore,
    Summary,
    score_contract,
    score_retrieval,
    summarize,
)


class Report(ResultModel):
    schema_version: int = 1
    dataset_version: str
    dataset_sha256: str
    engine_version: str
    embedding_model: str = "fake-sha256-v1"
    recall_target: float = 0.8
    status: str
    retrieval: list[RetrievalScore]
    contracts: list[ContractScore]
    summaries: list[Summary]


def evaluate(engine: Engine, data: Dataset) -> Report:
    # This function requires migrated, empty project tables; the CLI enforces an empty database.
    with session_scope(engine) as session:
        if session.scalar(select(Project.id).limit(1)) is not None:
            raise ValueError("Evaluation requires an empty project corpus")
        session.add_all(
            [
                Project(id=pid, name="Synthetic evaluation")
                for pid in sorted({d.project_id for d in data.documents})
            ]
        )
    provider = FakeEmbeddingProvider()  # Never resolve a provider from environment variables.
    for doc in data.documents:
        with session_scope(engine) as session:
            saved, _ = ingest_document(
                session, doc.project_id, doc.metadata, doc.text.encode(), "text/plain"
            )
        with session_scope(engine) as session:
            index_document(session, doc.project_id, saved.id, provider)
    retrieval = []
    for case in data.retrieval_cases:
        allowed = {
            d.source_id
            for d in data.documents
            if d.project_id == case.project_id
            and d.metadata.api_version == case.request.api_version
            and (case.request.provider is None or d.metadata.provider == case.request.provider)
            and (
                case.request.document_type is None
                or d.metadata.document_type == case.request.document_type
            )
        }
        for mode in ("keyword", "hybrid"):
            error = None
            try:
                result = KnowledgeSearch(engine, case.project_id, provider).search(
                    case.request.model_copy(update={"mode": mode, "limit": 5})
                )
                returned = [hit.source_id for hit in result.hits]
            except KnowledgeError:
                returned, error = [], "retrieval_unavailable"
            retrieval.append(score_retrieval(case, mode, returned, allowed, error))
    contracts = []
    for case in data.contract_cases:
        error = None
        try:
            result = compare_contracts(case.baseline, case.candidate)
            actual = [
                ExpectedChange(
                    rule_id=c.rule_id, severity=c.severity, operation=c.operation, path=c.path
                )
                for c in result.changes
            ]
            if result.engine_version != data.oasdiff_version:
                error = "engine_version_mismatch"
        except ComparisonError:
            actual, error = [], "comparison_unavailable"
        contracts.append(score_contract(case, actual, error))
    summaries = summarize(retrieval)
    passed = all(r.passed for r in summaries) and all(c.passed for c in contracts)
    return Report(
        dataset_version=data.dataset_version,
        dataset_sha256=hashlib.sha256(data.model_dump_json().encode()).hexdigest(),
        engine_version=data.oasdiff_version,
        status="passed" if passed else "failed",
        retrieval=retrieval,
        contracts=contracts,
        summaries=summaries,
    )


def test_database_url(value: str):
    try:
        url = make_url(value)
    except ArgumentError:
        raise ValueError("Invalid test database URL") from None
    if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith("_test"):
        raise ValueError("Use a disposable PostgreSQL database ending in _test")
    return url


def migrate(engine, direction, revision):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        getattr(command, direction)(config, revision)


def run_database(value: str) -> Report:
    data = load_dataset()
    engine = create_database_engine(test_database_url(value))
    try:
        with engine.connect() as connection:
            if inspect(connection).get_table_names():
                raise ValueError("Evaluation database must have no existing tables")
        # Only remove the schema we created after the empty-database guard succeeded.
        migrate(engine, "upgrade", "head")
        try:
            return evaluate(engine, data)
        finally:
            migrate(engine, "downgrade", "base")
            with engine.begin() as connection:
                connection.execute(text("DROP TABLE alembic_version"))
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("evaluation-results/report.json"))
    args = parser.parse_args()
    try:
        report = run_database(os.environ.get("TEST_DATABASE_URL", ""))
        payload = report.model_dump_json(indent=2)
        code = 0 if report.status == "passed" else 1
    except (SQLAlchemyError, ValueError, ValidationError, HTTPException, OSError, ComparisonError):
        # No URLs, SQL parameters, provider messages or credentials in artifacts/logs.
        payload = '{"schema_version":1,"status":"error","error":"evaluation_unavailable"}'
        code = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload + "\n", encoding="utf-8")
    print("Evaluation " + ("passed" if code == 0 else "failed") + "; report written.")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
