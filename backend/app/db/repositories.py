from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ApiContract


def get_contract(session: Session, *, project_id: UUID, contract_id: UUID) -> ApiContract | None:
    """Contract IDs alone never authorize reading another project's evidence."""
    return session.scalar(
        select(ApiContract).where(
            ApiContract.id == contract_id, ApiContract.project_id == project_id
        )
    )
