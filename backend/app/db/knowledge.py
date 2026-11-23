"""Parameterized, project/version-filtered PostgreSQL full-text lookup."""

from uuid import UUID

from sqlalchemy import func, literal_column, select, text
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentChunk
from app.knowledge_schemas import KnowledgeRequest


def search_chunks(session: Session, project_id: UUID, request: KnowledgeRequest):
    # Transaction-local timeout also covers project lookup. The service owns this
    # transaction; neither timeout nor cancellation is converted to empty evidence.
    session.execute(text("SET LOCAL statement_timeout = '3000ms'"))
    query = func.plainto_tsquery(literal_column("'simple'::regconfig"), request.query)
    score = func.ts_rank_cd(DocumentChunk.search_vector, query).label("score")
    statement = (
        select(DocumentChunk, Document, score)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.project_id == project_id,
            Document.api_version == request.api_version,
            DocumentChunk.search_vector.op("@@")(query),
        )
    )
    if request.provider is not None:
        statement = statement.where(Document.provider == request.provider)
    if request.document_type is not None:
        statement = statement.where(Document.document_type == request.document_type)
    return session.execute(
        statement.order_by(score.desc(), DocumentChunk.id).limit(request.limit + 1)
    ).all()
