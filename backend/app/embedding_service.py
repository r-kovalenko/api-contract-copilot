"""Atomic per-document embedding lifecycle with explicit replacement consent."""

import asyncio
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import embeddings as repository
from app.document_service import require_document
from app.embedding_provider import EmbeddingError, EmbeddingProvider, EmbeddingSpec, embed_chunks


class EmbeddingStatus(BaseModel):
    document_id: UUID
    model: str | None
    dimensions: int | None
    chunks: int
    embedded_chunks: int
    ready: bool


def status(session: Session, project_id: UUID, document_id: UUID) -> EmbeddingStatus:
    require_document(session, project_id, document_id)
    chunks = repository.chunks(session, document_id)
    rows = repository.embeddings(session, document_id)
    identities = {(r.model, r.dimensions) for r in rows}
    identity = next(iter(identities)) if len(identities) == 1 else (None, None)
    return EmbeddingStatus(
        document_id=document_id,
        model=identity[0],
        dimensions=identity[1],
        chunks=len(chunks),
        embedded_chunks=len(rows),
        ready=bool(chunks) and len(rows) == len(chunks) and len(identities) == 1,
    )


def index_document(
    session: Session,
    project_id: UUID,
    document_id: UUID,
    provider: EmbeddingProvider,
    reindex: bool = False,
) -> EmbeddingStatus:
    if repository.lock_document(session, project_id, document_id) is None:
        raise HTTPException(404, "Document not found in this project")
    spec = EmbeddingSpec.model_validate(provider.spec)
    current = status(session, project_id, document_id)
    same = (current.model, current.dimensions) == (spec.model, spec.dimensions)
    if current.embedded_chunks and not same and not reindex:
        raise HTTPException(409, "Embedding model changed; explicitly request reindex")
    if current.ready and same:
        return current
    chunks = repository.chunks(session, document_id)
    try:
        vectors = asyncio.run(embed_chunks(provider, [row.content for row in chunks]))
    except EmbeddingError:
        session.rollback()
        raise HTTPException(
            503, "Embedding generation failed; previous snapshot retained. Retry later."
        ) from None
    repository.replace(session, chunks, spec, vectors)
    result = status(session, project_id, document_id)
    session.commit()
    return result
