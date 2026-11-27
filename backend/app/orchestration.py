"""Central read-only dispatch with durable claims, bounded retries and fenced results."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Engine

from app.analysis_service import AnalysisError, project_repositories
from app.code_search import RepositorySearch
from app.db import orchestration as repository
from app.db.models import ToolRun, WorkflowExecution
from app.db.session import session_scope
from app.db.workflows import workflow
from app.evidence_agent import summarize_evidence
from app.knowledge import KnowledgeSearch
from app.orchestration_schemas import (
    AttemptView,
    Claim,
    EvidenceSummary,
    ExecutionPlan,
    ExecutionView,
)
from app.tool_registry import ToolRegistry, ToolUnavailable, response_adapter
from app.workflow_schemas import WorkflowView
from app.workflow_service import require_session

LEASE_SECONDS = 120
MAX_ATTEMPTS = 2


def registry_for(engine, project_id):
    return ToolRegistry(
        RepositorySearch(project_repositories(project_id)), KnowledgeSearch(engine, project_id)
    )


def checkpoint(state, status, reason):
    state.status, state.reason = status, reason
    state.revision += 1
    state.updated_at = datetime.now(UTC)


def require_execution(db, project_id, session_id, lock=False):
    require_session(db, project_id, session_id, lock=lock)
    row = repository.execution(db, project_id, session_id)
    if row is None:
        raise HTTPException(404, "Execution not found in this project session")
    return row, workflow(db, project_id, session_id)


def view(db, project_id, session_id):
    row, state = require_execution(db, project_id, session_id, lock=True)
    return ExecutionView(
        workflow=WorkflowView.model_validate(state),
        plan=ExecutionPlan(steps=row.plan),
        next_step=row.cursor,
        attempts=row.attempts,
        lease_expires=row.lease_expires,
        summary=EvidenceSummary.model_validate(row.summary) if row.summary else None,
        results=[
            AttemptView(
                step_index=r.step_index,
                attempt=r.attempt,
                response=response_adapter.validate_python(r.result),
            )
            for r in repository.attempts(db, project_id, session_id)
        ],
    )


def read_execution(engine, project_id, session_id):
    with session_scope(engine) as db:
        return view(db, project_id, session_id)


def start_execution(engine, project_id, session_id, plan: ExecutionPlan):
    with session_scope(engine) as db:
        require_session(db, project_id, session_id, lock=True)
        existing = repository.execution(db, project_id, session_id)
        steps = plan.model_dump(mode="json")["steps"]
        if existing is not None:
            if existing.plan != steps:
                raise HTTPException(409, "Execution plan is immutable; start a new session")
            return view(db, project_id, session_id)
        state = workflow(db, project_id, session_id)
        if state.status != "running":
            raise HTTPException(409, "Execution must start from a running session")
        db.add(
            WorkflowExecution(
                session_id=session_id, project_id=project_id, plan=steps, cursor=0, attempts=0
            )
        )
        checkpoint(state, "running", "Execution plan saved; resume to run the next step")
        db.flush()
        return view(db, project_id, session_id)


def require_revision(state, revision):
    if state.revision != revision:
        raise HTTPException(409, "Workflow changed; reload before continuing")


def record_result(db, row, state, response):
    step = row.plan[row.cursor]
    db.add(
        ToolRun(
            project_id=row.project_id,
            session_id=row.session_id,
            step_index=row.cursor,
            attempt=row.attempts,
            operation=step["operation"],
            status=response.status,
            result=response.model_dump(mode="json"),
        )
    )
    row.lease_id = row.lease_expires = None
    if response.status == "unavailable" and row.attempts < MAX_ATTEMPTS:
        checkpoint(state, "running", "Tool unavailable; explicit resume may retry once")
    else:
        row.cursor += 1
        row.attempts = 0
        checkpoint(state, "running", "Tool result checkpointed")
        db.flush()
        if row.cursor == len(row.plan):
            latest = {}
            for run in repository.attempts(db, row.project_id, row.session_id):
                latest[run.step_index] = response_adapter.validate_python(run.result)
            summary = summarize_evidence([latest[i] for i in range(len(row.plan))])
            row.summary = summary.model_dump(mode="json")
            state.status = "completed"
            state.reason = (
                "Evidence collection completed"
                if not summary.evidence_gaps
                else "Evidence collection completed with gaps"
            )
    db.flush()


def claim_step(engine, project_id, session_id, revision):
    with session_scope(engine) as db:
        row, state = require_execution(db, project_id, session_id, lock=True)
        require_revision(state, revision)
        if state.status not in {"running", "waiting_for_user"}:
            raise HTTPException(
                409, "This workflow cannot resume; approvals are not authorized here"
            )
        now = datetime.now(UTC)
        if row.lease_expires is not None and row.lease_expires > now:
            raise HTTPException(409, "Another resume owns the current step")
        if row.lease_expires is not None:
            exhausted = row.attempts >= MAX_ATTEMPTS
            record_result(db, row, state, ToolUnavailable(code="timeout"))
            if exhausted:
                return view(db, project_id, session_id)
        if row.attempts >= MAX_ATTEMPTS:
            record_result(db, row, state, ToolUnavailable(code="timeout"))
            return view(db, project_id, session_id)
        token = uuid4()
        row.attempts += 1
        row.lease_id = token
        row.lease_expires = now + timedelta(seconds=LEASE_SECONDS)
        checkpoint(state, "running", "Tool step claimed")
        return Claim(token=token, step=row.plan[row.cursor])


def resume_execution(engine: Engine, project_id, session_id, revision):
    claim = claim_step(engine, project_id, session_id, revision)
    if isinstance(claim, ExecutionView):
        return claim
    # No transaction or row lock is held during bounded read-only tool execution.
    try:
        response = registry_for(engine, project_id).invoke(claim.step.model_dump(mode="json"))
        response = response_adapter.validate_python(response)
        if response.status == "ok" and (
            response.operation != claim.step.operation
            or response.operation == "search_knowledge"
            and response.result.project_id != project_id
        ):
            response = ToolUnavailable(code="invalid_output")
    except TimeoutError:
        response = ToolUnavailable(code="timeout")
    except (AnalysisError, ValidationError, ValueError, OSError):
        response = ToolUnavailable(code="engine_failed")
    with session_scope(engine) as db:
        row, state = require_execution(db, project_id, session_id, lock=True)
        if (
            row.lease_id != claim.token
            or state.status != "running"
            or row.lease_expires is None
            or row.lease_expires <= datetime.now(UTC)
        ):
            raise HTTPException(409, "Step claim expired or was cancelled; result discarded")
        record_result(db, row, state, response)
        return view(db, project_id, session_id)


def control_execution(engine, project_id, session_id, revision, cancel=False):
    with session_scope(engine) as db:
        row, state = require_execution(db, project_id, session_id, lock=True)
        require_revision(state, revision)
        if state.status in {"completed", "failed"}:
            raise HTTPException(409, "Execution is terminal")
        if cancel:
            row.lease_id = row.lease_expires = None
            latest = {}
            for run in repository.attempts(db, project_id, session_id):
                latest[run.step_index] = response_adapter.validate_python(run.result)
            summary = summarize_evidence([latest[i] for i in sorted(latest)])
            summary.status = "partial"
            summary.evidence_gaps.append("cancelled")
            row.summary = summary.model_dump(mode="json")
            checkpoint(
                state, "failed", "Execution cancelled; any in-flight result will be discarded"
            )
        else:
            if state.status != "running" or row.lease_id is not None:
                raise HTTPException(409, "Pause is allowed only between steps")
            checkpoint(state, "waiting_for_user", "Paused by user; explicit resume required")
        return view(db, project_id, session_id)
