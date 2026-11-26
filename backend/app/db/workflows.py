"""Project-bound conversation storage. Services own locks and transaction completion."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ConversationSession, SessionMessage, ToolRun, WorkflowState


def get_session(db: Session, project_id: UUID, session_id: UUID, lock: bool = False):
    statement = select(ConversationSession).where(
        ConversationSession.project_id == project_id, ConversationSession.id == session_id
    )
    return db.scalar(statement.with_for_update() if lock else statement)


def sessions(db, project_id, offset, limit):
    return db.scalars(
        select(ConversationSession)
        .where(ConversationSession.project_id == project_id)
        .order_by(ConversationSession.created_at.desc(), ConversationSession.id.desc())
        .offset(offset)
        .limit(limit)
    )


def workflow(db, project_id, session_id):
    return db.scalar(
        select(WorkflowState).where(
            WorkflowState.project_id == project_id, WorkflowState.session_id == session_id
        )
    )


def messages(db, project_id, session_id, offset, limit):
    return db.scalars(
        select(SessionMessage)
        .where(SessionMessage.project_id == project_id, SessionMessage.session_id == session_id)
        .order_by(SessionMessage.sequence)
        .offset(offset)
        .limit(limit)
    )


def duplicate_message(db, session_id, request_id):
    return db.scalar(
        select(SessionMessage).where(
            SessionMessage.session_id == session_id, SessionMessage.request_id == request_id
        )
    )


def next_sequence(db, session_id):
    return (
        db.scalar(
            select(func.max(SessionMessage.sequence)).where(SessionMessage.session_id == session_id)
        )
        or 0
    ) + 1


def tool_runs(db, project_id, session_id, offset, limit):
    return db.scalars(
        select(ToolRun)
        .where(ToolRun.project_id == project_id, ToolRun.session_id == session_id)
        .order_by(ToolRun.created_at, ToolRun.id)
        .offset(offset)
        .limit(limit)
    )
