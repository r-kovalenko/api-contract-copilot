from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.contracts import require_project
from app.db.migration_plans import get_plan, list_plans
from app.migration_schemas import PlanCreate, PlanSummary, PlanView
from app.migration_service import create_plan
from app.projects import Database

router = APIRouter(prefix="/api/projects/{project_id}/migration-plans", tags=["migration plans"])


@router.post("", response_model=PlanView, status_code=201)
def create(project_id: UUID, data: PlanCreate, db: Database):
    return create_plan(db, project_id, data.analysis_id)


@router.get("", response_model=list[PlanSummary])
def index(
    project_id: UUID,
    db: Database,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    require_project(db, project_id)
    return list_plans(db, project_id, offset, limit)


@router.get("/{plan_id}", response_model=PlanView)
def detail(project_id: UUID, plan_id: UUID, db: Database):
    row = get_plan(db, project_id, plan_id)
    if row is None:
        raise HTTPException(404, "Migration plan not found in this project")
    return PlanView.model_validate(row)
