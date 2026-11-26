"""Project-bound conversation and workflow checkpoint persistence."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0007_session_workflows"
down_revision = "0006_chunk_embeddings"
branch_labels = None
depends_on = None


def timestamp(name="created_at"):
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def session_fk():
    return sa.ForeignKeyConstraint(
        ["project_id", "session_id"], ["sessions.project_id", "sessions.id"], ondelete="CASCADE"
    )


def upgrade():
    op.create_unique_constraint("uq_analysis_project_id", "analysis_runs", ["project_id", "id"])
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        timestamp(),
        sa.UniqueConstraint("project_id", "id", name="uq_sessions_project_id"),
        sa.CheckConstraint("length(btrim(title)) BETWEEN 1 AND 200", name="ck_session_title"),
    )
    op.create_index("ix_sessions_project_id", "sessions", ["project_id"])
    op.create_table(
        "session_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        timestamp(),
        session_fk(),
        sa.UniqueConstraint("session_id", "sequence", name="uq_message_sequence"),
        sa.UniqueConstraint("session_id", "request_id", name="uq_message_request"),
        sa.CheckConstraint("sequence BETWEEN 1 AND 1000", name="ck_message_sequence"),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_message_role"),
        sa.CheckConstraint("length(btrim(content)) BETWEEN 1 AND 4000", name="ck_message_content"),
    )
    op.create_table(
        "workflow_states",
        sa.Column("session_id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        timestamp("updated_at"),
        session_fk(),
        sa.ForeignKeyConstraint(
            ["project_id", "analysis_id"],
            ["analysis_runs.project_id", "analysis_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'waiting_for_user', 'waiting_for_approval', "
            "'completed', 'failed')",
            name="ck_workflow_status",
        ),
        sa.CheckConstraint("revision >= 0", name="ck_workflow_revision"),
        sa.CheckConstraint("length(btrim(reason)) BETWEEN 1 AND 1000", name="ck_workflow_reason"),
    )
    op.create_table(
        "tool_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("result", JSONB(), nullable=False),
        timestamp(),
        session_fk(),
        sa.CheckConstraint(
            "operation IN ('search_code', 'search_knowledge')", name="ck_tool_run_operation"
        ),
        sa.CheckConstraint(
            "status IN ('ok', 'rejected', 'unavailable')", name="ck_tool_run_status"
        ),
        sa.CheckConstraint("jsonb_typeof(result) = 'object'", name="ck_tool_run_result"),
    )
    op.create_index("ix_tool_runs_session_id", "tool_runs", ["session_id"])


def downgrade():
    op.drop_table("tool_runs")
    op.drop_table("workflow_states")
    op.drop_table("session_messages")
    op.drop_table("sessions")
    op.drop_constraint("uq_analysis_project_id", "analysis_runs", type_="unique")
