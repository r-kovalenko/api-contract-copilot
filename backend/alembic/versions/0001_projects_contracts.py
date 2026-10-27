"""Project and versioned contract foundation; pgvector for subsequent retrieval work."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_projects_contracts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_projects_name"),
    )
    op.create_table(
        "api_contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("openapi_version", sa.String(20), nullable=False),
        sa.Column("specification", postgresql.JSONB(), nullable=False),
        sa.Column("source_name", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "version", name="uq_contracts_project_version"),
        sa.CheckConstraint("length(btrim(version)) > 0", name="ck_contracts_version"),
        sa.CheckConstraint("openapi_version LIKE '3.%'", name="ck_contracts_openapi_version"),
        sa.CheckConstraint(
            "jsonb_typeof(specification) = 'object'", name="ck_contracts_specification"
        ),
    )


def downgrade() -> None:
    op.drop_table("api_contracts")
    op.drop_table("projects")
    # Extensions are database-wide and may predate this application. Never drop shared vector data.
