"""Immutable project-bound advisory migration plans."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0009_migration_plans"
down_revision = "0008_workflow_execution"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "migration_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("plan", JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "analysis_id"],
            ["analysis_runs.project_id", "analysis_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("jsonb_typeof(plan) = 'object'", name="ck_migration_plan"),
    )
    op.create_index("ix_migration_plans_project_id", "migration_plans", ["project_id"])


def downgrade():
    op.drop_index("ix_migration_plans_project_id", table_name="migration_plans")
    op.drop_table("migration_plans")
