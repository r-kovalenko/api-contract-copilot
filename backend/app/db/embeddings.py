"""Database access for embedding snapshots. Caller holds the document row lock."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import ChunkEmbedding, Document, DocumentChunk


def lock_document(session: Session, project_id: UUID, document_id: UUID):
    return session.scalar(
        select(Document)
        .where(Document.id == document_id, Document.project_id == project_id)
        .with_for_update()
    )


def chunks(session: Session, document_id: UUID):
    return list(
        session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.ordinal)
            .limit(133)
        )
    )


def embeddings(session: Session, document_id: UUID):
    return list(
        session.scalars(
            select(ChunkEmbedding)
            .join(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .limit(133)
        )
    )


def replace(session: Session, chunk_rows, spec, vectors):
    session.execute(
        delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_([row.id for row in chunk_rows]))
    )
    session.add_all(
        [
            ChunkEmbedding(
                chunk_id=row.id, model=spec.model, dimensions=spec.dimensions, embedding=vector
            )
            for row, vector in zip(chunk_rows, vectors, strict=True)
        ]
    )
    session.flush()
