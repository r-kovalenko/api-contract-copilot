from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MigrationPlanRecord


def get_plan(db: Session, project_id: UUID, plan_id: UUID):
    return db.scalar(
        select(MigrationPlanRecord).where(
            MigrationPlanRecord.project_id == project_id, MigrationPlanRecord.id == plan_id
        )
    )


def list_plans(db: Session, project_id: UUID, offset: int, limit: int):
    return (
        db.execute(
            select(
                MigrationPlanRecord.id,
                MigrationPlanRecord.project_id,
                MigrationPlanRecord.analysis_id,
                MigrationPlanRecord.created_at,
            )
            .where(MigrationPlanRecord.project_id == project_id)
            .order_by(MigrationPlanRecord.created_at.desc(), MigrationPlanRecord.id.desc())
            .offset(offset)
            .limit(limit)
        )
        .mappings()
        .all()
    )


def insert_plan(db: Session, **values):
    row = MigrationPlanRecord(**values)
    db.add(row)
    db.flush()
    return row
