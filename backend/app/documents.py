"""Local single-user documentation API. No parsing of Markdown, HTML or remote links."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import select

from app.contracts import require_project
from app.db.models import Document, DocumentChunk
from app.document_service import (
    ChunkView,
    DocumentMetadata,
    DocumentView,
    ingest_document,
    require_document,
)
from app.projects import Database

router = APIRouter(prefix="/api/projects/{project_id}/documents", tags=["documents"])


async def document_body(request: Request) -> tuple[bytes, str]:
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type not in {"text/plain", "text/markdown"}:
        raise HTTPException(415, "Send UTF-8 text/plain or text/markdown")
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise HTTPException(415, "Compressed uploads are not supported")
    return await request.body(), media_type


@router.post("", response_model=DocumentView, status_code=201)
def upload(
    project_id: UUID,
    metadata: Annotated[DocumentMetadata, Query()],
    body: Annotated[tuple[bytes, str], Depends(document_body)],
    session: Database,
    response: Response,
) -> DocumentView:
    view, created = ingest_document(session, project_id, metadata, *body)
    response.status_code = 201 if created else 200
    return view


@router.get("", response_model=list[DocumentView])
def documents(
    project_id: UUID,
    session: Database,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[DocumentView]:
    require_project(session, project_id)
    rows = session.scalars(
        select(Document)
        .where(Document.project_id == project_id)
        .order_by(Document.created_at.desc(), Document.id)
        .offset(offset)
        .limit(limit)
    )
    return [DocumentView.model_validate(row) for row in rows]


@router.get("/{document_id}", response_model=DocumentView)
def document(project_id: UUID, document_id: UUID, session: Database) -> DocumentView:
    return DocumentView.model_validate(require_document(session, project_id, document_id))


@router.get("/{document_id}/chunks", response_model=list[ChunkView])
def chunks(
    project_id: UUID,
    document_id: UUID,
    session: Database,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ChunkView]:
    require_document(session, project_id, document_id)
    rows = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.ordinal)
        .offset(offset)
        .limit(limit)
    )
    return [ChunkView.model_validate(row) for row in rows]
