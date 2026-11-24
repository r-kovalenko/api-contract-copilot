from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError

from app.analysis_schemas import AnalysisCreate, AnalysisSummary, AnalysisView
from app.analysis_service import AnalysisError, create_analysis, project_repositories
from app.contracts import require_project
from app.db.analyses import get_analysis, list_analyses
from app.db.session import get_engine
from app.projects import Database

router = APIRouter(prefix="/api/projects/{project_id}/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisView, status_code=201)
def create(project_id: UUID, data: AnalysisCreate) -> AnalysisView:
    try:
        return create_analysis(get_engine(), project_id, data, project_repositories(project_id))
    except AnalysisError as error:
        status = (
            404 if error.code == "not_found" else 422 if error.code == "unknown_repository" else 503
        )
        raise HTTPException(status, {"code": error.code}) from None
    except (SQLAlchemyError, ValueError):
        raise HTTPException(503, "Analysis storage is unavailable") from None


@router.get("", response_model=list[AnalysisSummary])
def index(
    project_id: UUID,
    session: Database,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AnalysisSummary]:
    require_project(session, project_id)
    return [
        AnalysisSummary.model_validate(row)
        for row in list_analyses(session, project_id, offset, limit)
    ]


@router.get("/{analysis_id}", response_model=AnalysisView)
def detail(project_id: UUID, analysis_id: UUID, session: Database) -> AnalysisView:
    row = get_analysis(session, project_id, analysis_id)
    if row is None:
        raise HTTPException(404, "Analysis not found in this project")
    return AnalysisView.model_validate(row)
