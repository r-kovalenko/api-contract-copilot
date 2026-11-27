"""Durable bounded read-only execution plans and fenced step claims."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0008_workflow_execution"
down_revision = "0007_session_workflows"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tool_runs", sa.Column("step_index", sa.Integer(), nullable=True))
    op.add_column("tool_runs", sa.Column("attempt", sa.Integer(), nullable=True))
    op.create_unique_constraint(
        "uq_tool_step_attempt", "tool_runs", ["session_id", "step_index", "attempt"]
    )
    op.create_table(
        "workflow_executions",
        sa.Column("session_id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("plan", JSONB(), nullable=False),
        sa.Column("cursor", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_id", sa.Uuid(), nullable=True),
        sa.Column("lease_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", JSONB(none_as_null=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id", "session_id"], ["sessions.project_id", "sessions.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(plan) = 'array' AND jsonb_array_length(plan) BETWEEN 1 AND 5",
            name="ck_execution_plan",
        ),
        sa.CheckConstraint("cursor BETWEEN 0 AND 5", name="ck_execution_cursor"),
        sa.CheckConstraint("attempts BETWEEN 0 AND 2", name="ck_execution_attempts"),
        sa.CheckConstraint(
            "(lease_id IS NULL) = (lease_expires IS NULL)", name="ck_execution_lease"
        ),
    )


def downgrade():
    op.drop_table("workflow_executions")
    op.drop_constraint("uq_tool_step_attempt", "tool_runs", type_="unique")
    op.drop_column("tool_runs", "attempt")
    op.drop_column("tool_runs", "step_index")
