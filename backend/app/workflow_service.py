"""Checkpoint persistence only. No agents, tool execution, approval, or automatic resume."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.contracts import require_project
from app.db import workflows as repository
from app.db.analyses import get_analysis
from app.db.models import ConversationSession, SessionMessage, WorkflowState
from app.workflow_schemas import (
    MessageCreate,
    MessageView,
    SessionCreate,
    SessionView,
    Transition,
    WorkflowView,
)

ALLOWED = {
    "running": frozenset({"waiting_for_user", "waiting_for_approval", "completed", "failed"}),
    "waiting_for_user": frozenset({"running", "failed"}),
    # Approval decisions must eventually bind to an exact action. This checkpoint cannot grant one.
    "waiting_for_approval": frozenset({"failed"}),
    "completed": frozenset(),
    "failed": frozenset(),
}


def require_session(db: Session, project_id: UUID, session_id: UUID, lock=False):
    row = repository.get_session(db, project_id, session_id, lock)
    if row is None:
        raise HTTPException(404, "Session not found in this project")
    return row


def create_session(db: Session, project_id: UUID, data: SessionCreate) -> SessionView:
    require_project(db, project_id)
    if data.analysis_id is not None and get_analysis(db, project_id, data.analysis_id) is None:
        raise HTTPException(404, "Analysis not found in this project")
    row = ConversationSession(project_id=project_id, title=data.title)
    db.add(row)
    db.flush()
    db.add(
        WorkflowState(
            session_id=row.id,
            project_id=project_id,
            analysis_id=data.analysis_id,
            status="running",
            revision=0,
            reason="Session checkpoint created",
        )
    )
    view = SessionView.model_validate(row)
    db.commit()
    return view


def append_message(
    db: Session, project_id: UUID, session_id: UUID, data: MessageCreate
) -> MessageView:
    require_session(db, project_id, session_id, lock=True)
    old = repository.duplicate_message(db, session_id, data.request_id)
    if old is not None:
        if old.content != data.content or old.role != "user":
            raise HTTPException(409, "Request ID already used for different message content")
        return MessageView.model_validate(old)
    sequence = repository.next_sequence(db, session_id)
    if sequence > 1000:
        raise HTTPException(409, "Session message limit reached; start a new session")
    row = SessionMessage(
        project_id=project_id,
        session_id=session_id,
        request_id=data.request_id,
        sequence=sequence,
        role="user",
        content=data.content,
    )
    db.add(row)
    db.flush()
    view = MessageView.model_validate(row)
    db.commit()
    return view


def transition(db: Session, project_id: UUID, session_id: UUID, data: Transition) -> WorkflowView:
    require_session(db, project_id, session_id, lock=True)
    row = repository.workflow(db, project_id, session_id)
    if row.revision != data.expected_revision:
        raise HTTPException(409, "Workflow changed; reload before submitting another transition")
    if data.status not in ALLOWED[row.status]:
        raise HTTPException(409, "Workflow transition is not allowed")
    row.status = data.status
    row.revision += 1
    row.reason = data.reason
    row.updated_at = datetime.now(UTC)
    db.flush()
    view = WorkflowView.model_validate(row)
    db.commit()
    return view
