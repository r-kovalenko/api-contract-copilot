"""Explicit local-only indexing; ingestion never triggers provider calls."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app import embedding_provider
from app.embedding_service import EmbeddingStatus, index_document, status
from app.projects import Database

router = APIRouter(prefix="/api/projects/{project_id}/documents", tags=["embeddings"])


@router.get("/{document_id}/embeddings", response_model=EmbeddingStatus)
def get_status(project_id: UUID, document_id: UUID, session: Database):
    return status(session, project_id, document_id)


@router.post("/{document_id}/embeddings", response_model=EmbeddingStatus)
def create(
    project_id: UUID,
    document_id: UUID,
    session: Database,
    provider: Annotated[embedding_provider.EmbeddingProvider, Depends(embedding_provider.provider)],
    reindex: Annotated[bool, Query()] = False,
):
    return index_document(session, project_id, document_id, provider, reindex)
