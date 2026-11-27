"""Local workflow execution endpoints. Payloads can only select registered read tools."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine
from app.orchestration import control_execution, read_execution, resume_execution, start_execution
from app.orchestration_schemas import ExecutionPlan, ExecutionView, Revision

router = APIRouter(
    prefix="/api/projects/{project_id}/sessions/{session_id}/execution", tags=["execution"]
)


def invoke(action, *args, **kwargs):
    try:
        return action(get_engine(), *args, **kwargs)
    except (SQLAlchemyError, ValueError):
        raise HTTPException(
            503, "Workflow storage is unavailable; reload before retrying"
        ) from None


@router.post("", response_model=ExecutionView)
def start(project_id: UUID, session_id: UUID, data: ExecutionPlan):
    return invoke(start_execution, project_id, session_id, data)


@router.get("", response_model=ExecutionView)
def read(project_id: UUID, session_id: UUID):
    return invoke(read_execution, project_id, session_id)


@router.post("/resume", response_model=ExecutionView)
def resume(project_id: UUID, session_id: UUID, data: Revision):
    return invoke(resume_execution, project_id, session_id, data.expected_revision)


@router.post("/pause", response_model=ExecutionView)
def pause(project_id: UUID, session_id: UUID, data: Revision):
    return invoke(control_execution, project_id, session_id, data.expected_revision)


@router.post("/cancel", response_model=ExecutionView)
def cancel(project_id: UUID, session_id: UUID, data: Revision):
    return invoke(control_execution, project_id, session_id, data.expected_revision, cancel=True)
