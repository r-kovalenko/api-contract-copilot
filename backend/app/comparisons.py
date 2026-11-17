from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, Response
from pydantic import BaseModel, ConfigDict

from app.comparison import ComparisonError, ComparisonResult, ContractChange
from app.comparison_service import ComparisonRequestError, create_comparison, require_project
from app.db.comparisons import get_comparison, list_comparisons
from app.projects import Database

router = APIRouter(prefix="/api/projects/{project_id}/comparisons", tags=["comparisons"])


class ComparisonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseline_id: UUID
    candidate_id: UUID


class ComparisonSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    baseline_id: UUID
    candidate_id: UUID
    engine_version: str
    normalization_version: int
    change_count: int
    created_at: datetime


class ComparisonView(ComparisonSummary):
    result: ComparisonResult


@router.post("", response_model=ComparisonView, status_code=201)
def create(project_id: UUID, data: ComparisonCreate, response: Response, session: Database):
    try:
        stored, created = create_comparison(
            session, project_id, data.baseline_id, data.candidate_id
        )
    except ComparisonRequestError as exc:
        if str(exc) == "same_version":
            raise HTTPException(422, "Choose two different contract versions.") from None
        raise HTTPException(404, "Project or contract not found in this project.") from None
    except ComparisonError as exc:
        status = 422 if exc.code == "invalid_input" else 504 if exc.code == "timeout" else 503
        raise HTTPException(status, {"code": exc.code, "message": str(exc)}) from None
    response.status_code = 201 if created else 200
    view = ComparisonView.model_validate(stored)
    session.commit()  # Serialize before commit expires ORM fields; success must be durable.
    return view


@router.get("", response_model=list[ComparisonSummary])
def index(
    project_id: UUID,
    session: Database,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    try:
        require_project(session, project_id)
    except ComparisonRequestError:
        raise HTTPException(404, "Project not found") from None
    return [
        ComparisonSummary.model_validate(row)
        for row in list_comparisons(session, project_id, offset, limit)
    ]


@router.get("/{comparison_id}", response_model=ComparisonView)
def detail(project_id: UUID, comparison_id: UUID, session: Database):
    stored = get_comparison(session, project_id, comparison_id)
    if stored is None:
        raise HTTPException(404, "Comparison not found in this project")
    return ComparisonView.model_validate(stored)


@router.get("/{comparison_id}/changes/{change_id}", response_model=ContractChange)
def selected_change(
    project_id: UUID,
    comparison_id: UUID,
    change_id: Annotated[str, Path(pattern=r"^[a-f0-9]{64}$")],
    session: Database,
):
    saved = detail(project_id, comparison_id, session)
    for change in saved.result.changes:
        if change.id == change_id:
            return change
    raise HTTPException(404, "Change not found in this comparison")
