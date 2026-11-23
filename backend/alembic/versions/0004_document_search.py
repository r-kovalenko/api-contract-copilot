"""Index existing and future document chunks for literal-token full-text retrieval."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

from alembic import op

revision = "0004_document_search"
down_revision = "0003_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column(
            "search_vector",
            TSVECTOR,
            sa.Computed("to_tsvector('simple'::regconfig, content)", persisted=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_document_chunks_search", "document_chunks", ["search_vector"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_document_chunks_search", table_name="document_chunks")
    op.drop_column("document_chunks", "search_vector")
