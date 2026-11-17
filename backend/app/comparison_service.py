"""Persist complete deterministic results atomically; never persist a failed/partial run."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.comparison import NORMALIZATION_VERSION, compare_contracts
from app.db.comparisons import find_pair, get_comparison, insert_comparison
from app.db.models import ContractComparison
from app.db.repositories import get_contract, get_project
from app.oasdiff_pin import VERSION


class ComparisonRequestError(ValueError):
    pass


def require_project(session: Session, project_id: UUID) -> None:
    if get_project(session, project_id) is None:
        raise ComparisonRequestError("not_found")


def create_comparison(
    session: Session, project_id: UUID, baseline_id: UUID, candidate_id: UUID
) -> tuple[ContractComparison, bool]:
    require_project(session, project_id)
    baseline = get_contract(session, project_id=project_id, contract_id=baseline_id)
    candidate = get_contract(session, project_id=project_id, contract_id=candidate_id)
    if baseline is None or candidate is None:
        raise ComparisonRequestError("not_found")
    if baseline_id == candidate_id:
        raise ComparisonRequestError("same_version")
    pair = (project_id, baseline_id, candidate_id, VERSION, NORMALIZATION_VERSION)
    existing = find_pair(session, *pair)
    if existing is not None:
        return existing, False
    result = compare_contracts(baseline.specification, candidate.specification)
    values = dict(
        project_id=project_id,
        baseline_id=baseline_id,
        candidate_id=candidate_id,
        engine_version=result.engine_version,
        normalization_version=result.normalization_version,
        change_count=len(result.changes),
        result=result.model_dump(mode="json"),
    )
    inserted = insert_comparison(session, values)
    # READ COMMITTED: a racing insert waits for the winner, then reads its committed record.
    stored = (
        get_comparison(session, project_id, inserted) if inserted else find_pair(session, *pair)
    )
    if stored is None:
        raise RuntimeError("Comparison insert did not return a record")
    return stored, inserted is not None
