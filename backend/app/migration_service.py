from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.analysis_schemas import ImpactReport
from app.db.analyses import get_analysis
from app.db.migration_plans import insert_plan
from app.migration_agent import generate_plan
from app.migration_schemas import PlanView


def create_plan(db: Session, project_id: UUID, analysis_id: UUID) -> PlanView:
    analysis = get_analysis(db, project_id, analysis_id)
    if analysis is None:
        raise HTTPException(404, "Analysis not found in this project")
    plan = generate_plan(ImpactReport.model_validate(analysis.report))
    row = insert_plan(
        db, project_id=project_id, analysis_id=analysis_id, plan=plan.model_dump(mode="json")
    )
    view = PlanView.model_validate(row)
    db.commit()
    return view
