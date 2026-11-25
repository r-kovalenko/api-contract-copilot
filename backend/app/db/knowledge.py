"""Parameterized, project/version-filtered PostgreSQL full-text lookup."""

from uuid import UUID

from sqlalchemy import Float, case, cast, func, literal_column, select, text
from sqlalchemy.orm import Session

from app.db.models import ChunkEmbedding, Document, DocumentChunk
from app.db.vector import Vector
from app.embedding_provider import EmbeddingSpec
from app.knowledge_schemas import KnowledgeRequest
from app.rank_fusion import CANDIDATE_LIMIT


def search_chunks(
    session: Session,
    project_id: UUID,
    request: KnowledgeRequest,
    candidate_limit: int | None = None,
):
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
        statement.order_by(score.desc(), DocumentChunk.id).limit(
            (candidate_limit or request.limit) + 1
        )
    ).all()


def search_vectors(
    session: Session,
    project_id: UUID,
    request: KnowledgeRequest,
    spec: EmbeddingSpec,
    vector: list[float],
):
    session.execute(text("SET LOCAL statement_timeout = '3000ms'"))
    compatible = (ChunkEmbedding.model == spec.model) & (
        ChunkEmbedding.dimensions == spec.dimensions
    )
    # CASE prevents distance evaluation on incompatible dimensions regardless of SQL plan order.
    safe_vector = case((compatible, ChunkEmbedding.embedding), else_=None)
    distance = safe_vector.op("<=>", return_type=Float)(cast(vector, Vector())).label("distance")
    statement = (
        select(DocumentChunk, Document, distance)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
        .where(
            Document.project_id == project_id,
            Document.api_version == request.api_version,
            compatible,
        )
    )
    if request.provider is not None:
        statement = statement.where(Document.provider == request.provider)
    if request.document_type is not None:
        statement = statement.where(Document.document_type == request.document_type)
    return session.execute(
        statement.order_by(distance, DocumentChunk.id).limit(CANDIDATE_LIMIT + 1)
    ).all()
