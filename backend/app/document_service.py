"""Immutable, bounded documentation ingestion; references are labels, never URLs to fetch."""

import hashlib
import json
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid5

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.contracts import require_project
from app.db.models import Document, DocumentChunk

MAX_DOCUMENT_BYTES = 256 * 1024
CHUNK_SIZE = 2000
CHUNKING_VERSION = 1


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    provider: str = Field(min_length=1, max_length=100)
    api_version: str = Field(min_length=1, max_length=100)
    document_type: Literal["reference", "migration", "changelog", "guide"]
    source_ref: str = Field(min_length=1, max_length=255)

    @field_validator("provider", "api_version", "source_ref")
    @classmethod
    def plain_label(cls, value: str) -> str:
        if any(ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise ValueError("Metadata must not contain control characters")
        return value


class DocumentView(DocumentMetadata):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    media_type: str
    content_sha256: str
    chunking_version: int
    created_at: datetime


class ChunkView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    ordinal: int
    start_char: int
    end_char: int
    content: str


def decode_document(raw: bytes) -> str:
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise HTTPException(413, "Document exceeds 256 KiB")
    try:
        text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError:
        raise HTTPException(422, "Document must be UTF-8 text") from None
    if not text.strip() or any(ord(c) < 32 and c not in "\n\t" or ord(c) == 127 for c in text):
        raise HTTPException(422, "Document is empty or contains unsupported control characters")
    return text


def ingest_document(
    session: Session, project_id: UUID, metadata: DocumentMetadata, raw: bytes, media_type: str
) -> tuple[DocumentView, bool]:
    require_project(session, project_id)
    text = decode_document(raw)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    document_id = uuid5(project_id, json.dumps(metadata.model_dump(), sort_keys=True))
    inserted = session.scalar(
        insert(Document)
        .values(
            id=document_id,
            project_id=project_id,
            **metadata.model_dump(),
            media_type=media_type,
            content_sha256=digest,
            chunking_version=CHUNKING_VERSION,
        )
        .on_conflict_do_nothing(index_elements=[Document.id])
        .returning(Document.id)
    )
    if inserted is not None:
        session.add_all(
            [
                DocumentChunk(
                    id=uuid5(document_id, f"{CHUNKING_VERSION}:{digest}:{start}"),
                    document_id=document_id,
                    ordinal=start // CHUNK_SIZE,
                    start_char=start,
                    end_char=min(start + CHUNK_SIZE, len(text)),
                    content=text[start : start + CHUNK_SIZE],
                )
                for start in range(0, len(text), CHUNK_SIZE)
            ]
        )
        session.flush()
    document = session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.project_id == project_id,
        )
    )
    if document.content_sha256 != digest or document.media_type != media_type:
        session.rollback()
        raise HTTPException(
            409,
            "Source already exists with different content or media type; "
            "use a new source reference or API version",
        )
    view = DocumentView.model_validate(document)
    session.commit()
    return view, inserted is not None


def require_document(session: Session, project_id: UUID, document_id: UUID) -> Document:
    require_project(session, project_id)
    document = session.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.project_id == project_id,
        )
    )
    if document is None:
        raise HTTPException(404, "Document not found in this project")
    return document
