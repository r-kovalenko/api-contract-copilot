from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import ContractComparison


def find_pair(
    session: Session,
    project_id: UUID,
    baseline_id: UUID,
    candidate_id: UUID,
    engine_version: str,
    normalization_version: int,
) -> ContractComparison | None:
    return session.scalar(
        select(ContractComparison).filter_by(
            project_id=project_id,
            baseline_id=baseline_id,
            candidate_id=candidate_id,
            engine_version=engine_version,
            normalization_version=normalization_version,
        )
    )


def get_comparison(
    session: Session, project_id: UUID, comparison_id: UUID
) -> ContractComparison | None:
    return session.scalar(
        select(ContractComparison).filter_by(id=comparison_id, project_id=project_id)
    )


def list_comparisons(session: Session, project_id: UUID, offset: int, limit: int):
    # Return metadata only: do not load every potentially large JSON result for list pages.
    return (
        session.execute(
            select(
                ContractComparison.id,
                ContractComparison.project_id,
                ContractComparison.baseline_id,
                ContractComparison.candidate_id,
                ContractComparison.engine_version,
                ContractComparison.normalization_version,
                ContractComparison.change_count,
                ContractComparison.created_at,
            )
            .where(ContractComparison.project_id == project_id)
            .order_by(ContractComparison.created_at.desc(), ContractComparison.id.desc())
            .offset(offset)
            .limit(limit)
        )
        .mappings()
        .all()
    )


def insert_comparison(session: Session, values: dict) -> UUID | None:
    return session.scalar(
        insert(ContractComparison)
        .values(**values)
        .on_conflict_do_nothing(constraint="uq_comparisons_pair_engine")
        .returning(ContractComparison.id)
    )
