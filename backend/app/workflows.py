"""Single-user local conversation/checkpoint API; no execution permissions are granted."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.contracts import require_project
from app.db import workflows as repository
from app.projects import Database
from app.workflow_schemas import (
    MessageCreate,
    MessageView,
    SessionCreate,
    SessionView,
    ToolRunView,
    Transition,
    WorkflowView,
)
from app.workflow_service import append_message, create_session, require_session, transition

router = APIRouter(prefix="/api/projects/{project_id}/sessions", tags=["sessions"])
Offset = Annotated[int, Query(ge=0, le=100000)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post("", response_model=SessionView, status_code=201)
def create(project_id: UUID, data: SessionCreate, db: Database):
    return create_session(db, project_id, data)


@router.get("", response_model=list[SessionView])
def index(project_id: UUID, db: Database, offset: Offset = 0, limit: Limit = 20):
    require_project(db, project_id)
    return [
        SessionView.model_validate(r) for r in repository.sessions(db, project_id, offset, limit)
    ]


@router.get("/{session_id}", response_model=SessionView)
def detail(project_id: UUID, session_id: UUID, db: Database):
    return SessionView.model_validate(require_session(db, project_id, session_id))


@router.post("/{session_id}/messages", response_model=MessageView)
def message(project_id: UUID, session_id: UUID, data: MessageCreate, db: Database):
    return append_message(db, project_id, session_id, data)


@router.get("/{session_id}/messages", response_model=list[MessageView])
def history(
    project_id: UUID, session_id: UUID, db: Database, offset: Offset = 0, limit: Limit = 20
):
    require_session(db, project_id, session_id)
    return [
        MessageView.model_validate(r)
        for r in repository.messages(db, project_id, session_id, offset, limit)
    ]


@router.get("/{session_id}/workflow", response_model=WorkflowView)
def state(project_id: UUID, session_id: UUID, db: Database):
    require_session(db, project_id, session_id)
    return WorkflowView.model_validate(repository.workflow(db, project_id, session_id))


@router.post("/{session_id}/workflow/transitions", response_model=WorkflowView)
def change(project_id: UUID, session_id: UUID, data: Transition, db: Database):
    return transition(db, project_id, session_id, data)


@router.get("/{session_id}/tool-runs", response_model=list[ToolRunView])
def tools(project_id: UUID, session_id: UUID, db: Database, offset: Offset = 0, limit: Limit = 20):
    require_session(db, project_id, session_id)
    return [
        ToolRunView.model_validate(r)
        for r in repository.tool_runs(db, project_id, session_id, offset, limit)
    ]
