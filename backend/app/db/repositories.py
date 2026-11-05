from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApiContract, Project


def get_project(session: Session, project_id: UUID) -> Project | None:
    return session.get(Project, project_id)


def list_contracts(
    session: Session, project_id: UUID, offset: int, limit: int
) -> list[ApiContract]:
    return list(
        session.scalars(
            select(ApiContract)
            .where(ApiContract.project_id == project_id)
            .order_by(ApiContract.created_at.desc(), ApiContract.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )


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
