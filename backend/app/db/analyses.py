from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AnalysisRun


def get_analysis(session: Session, project_id: UUID, analysis_id: UUID):
    return session.scalar(
        select(AnalysisRun).where(
            AnalysisRun.project_id == project_id,
            AnalysisRun.id == analysis_id,
        )
    )


def list_analyses(session: Session, project_id: UUID, offset: int, limit: int):
    return (
        session.execute(
            select(
                AnalysisRun.id,
                AnalysisRun.project_id,
                AnalysisRun.comparison_id,
                AnalysisRun.change_id,
                AnalysisRun.created_at,
            )
            .where(AnalysisRun.project_id == project_id)
            .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
            .offset(offset)
            .limit(limit)
        )
        .mappings()
        .all()
    )


def insert_analysis(session: Session, **values) -> AnalysisRun:
    row = AnalysisRun(**values)
    session.add(row)
    session.flush()
    return row
