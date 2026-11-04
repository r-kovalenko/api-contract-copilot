from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApiContract, Project


def list_projects(session: Session, offset: int, limit: int) -> list[Project]:
    return list(
        session.scalars(
            select(Project)
            .order_by(Project.created_at.desc(), Project.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )


def get_contract(session: Session, *, project_id: UUID, contract_id: UUID) -> ApiContract | None:
    """Contract IDs alone never authorize reading another project's evidence."""
    return session.scalar(
        select(ApiContract).where(
            ApiContract.id == contract_id, ApiContract.project_id == project_id
        )
    )
