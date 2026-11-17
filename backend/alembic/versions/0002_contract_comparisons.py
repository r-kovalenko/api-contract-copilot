"""Immutable ordered comparisons with database-enforced project provenance."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0002_contract_comparisons"
down_revision = "0001_projects_contracts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_contracts_project_id", "api_contracts", ["project_id", "id"])
    op.create_table(
        "contract_comparisons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("baseline_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("engine_version", sa.String(40), nullable=False),
        sa.Column("normalization_version", sa.Integer(), nullable=False),
        sa.Column("change_count", sa.Integer(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["project_id", "baseline_id"],
            ["api_contracts.project_id", "api_contracts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "candidate_id"],
            ["api_contracts.project_id", "api_contracts.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "project_id",
            "baseline_id",
            "candidate_id",
            "engine_version",
            "normalization_version",
            name="uq_comparisons_pair_engine",
        ),
        sa.CheckConstraint("baseline_id <> candidate_id", name="ck_comparisons_distinct"),
        sa.CheckConstraint("jsonb_typeof(result) = 'object'", name="ck_comparisons_result"),
        sa.CheckConstraint(
            "change_count >= 0 AND change_count <= 2000", name="ck_comparisons_count"
        ),
    )


def downgrade() -> None:
    op.drop_table("contract_comparisons")
    op.drop_constraint("uq_contracts_project_id", "api_contracts", type_="unique")
