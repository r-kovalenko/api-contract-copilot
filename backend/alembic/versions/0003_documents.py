"""Immutable documentation and deterministic citation chunks."""

import sqlalchemy as sa

from alembic import op

revision = "0003_documents"
down_revision = "0002_contract_comparisons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("api_version", sa.String(100), nullable=False),
        sa.Column("document_type", sa.String(40), nullable=False),
        sa.Column("source_ref", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(30), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("chunking_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Uuid(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_document_chunk_ordinal"),
        sa.CheckConstraint("ordinal >= 0", name="ck_document_chunk_ordinal"),
        sa.CheckConstraint(
            "length(content) > 0 AND length(content) <= 2000", name="ck_document_chunk_size"
        ),
    )


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_table("documents")
