"""Per-chunk vectors with explicit model identity and dimensions."""

import sqlalchemy as sa

from alembic import op
from app.db.vector import Vector

revision = "0006_chunk_embeddings"
down_revision = "0005_analysis_runs"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chunk_embeddings",
        sa.Column(
            "chunk_id",
            sa.Uuid(),
            sa.ForeignKey("document_chunks.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("dimensions BETWEEN 1 AND 2000", name="ck_embedding_dimensions"),
        sa.CheckConstraint("vector_dims(embedding) = dimensions", name="ck_embedding_vector"),
        sa.CheckConstraint("length(btrim(model)) > 0", name="ck_embedding_model"),
    )


def downgrade():
    op.drop_table("chunk_embeddings")
