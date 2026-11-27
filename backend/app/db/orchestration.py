from sqlalchemy import select

from app.db.models import ToolRun, WorkflowExecution


def execution(db, project_id, session_id):
    return db.scalar(
        select(WorkflowExecution).where(
            WorkflowExecution.project_id == project_id, WorkflowExecution.session_id == session_id
        )
    )


def attempts(db, project_id, session_id):
    return list(
        db.scalars(
            select(ToolRun)
            .where(
                ToolRun.project_id == project_id,
                ToolRun.session_id == session_id,
                ToolRun.step_index.is_not(None),
            )
            .order_by(ToolRun.step_index, ToolRun.attempt)
            .limit(10)
        )
    )
