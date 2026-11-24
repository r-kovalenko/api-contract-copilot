"""Saved impact evidence with project-bound comparison provenance."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0005_analysis_runs"
down_revision = "0004_document_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_comparisons_project_id", "contract_comparisons", ["project_id", "id"]
    )
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("comparison_id", sa.Uuid(), nullable=False),
        sa.Column("change_id", sa.String(64), nullable=False),
        sa.Column("request", JSONB(), nullable=False),
        sa.Column("report", JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "comparison_id"],
            ["contract_comparisons.project_id", "contract_comparisons.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("jsonb_typeof(request) = 'object'", name="ck_analysis_request"),
        sa.CheckConstraint("jsonb_typeof(report) = 'object'", name="ck_analysis_report"),
    )
    op.create_index("ix_analysis_runs_project_id", "analysis_runs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_analysis_runs_project_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_constraint("uq_comparisons_project_id", "contract_comparisons", type_="unique")
