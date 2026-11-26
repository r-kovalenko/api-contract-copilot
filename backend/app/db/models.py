from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db.vector import Vector


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (CheckConstraint("length(btrim(name)) > 0", name="ck_projects_name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    contracts: Mapped[list["ApiContract"]] = relationship(
        back_populates="project", passive_deletes="all"
    )


class ApiContract(Base):
    __tablename__ = "api_contracts"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_contracts_project_version"),
        UniqueConstraint("project_id", "id", name="uq_contracts_project_id"),
        CheckConstraint("length(btrim(version)) > 0", name="ck_contracts_version"),
        CheckConstraint("openapi_version LIKE '3.%'", name="ck_contracts_openapi_version"),
        CheckConstraint(
            "jsonb_typeof(specification) = 'object'", name="ck_contracts_specification"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    version: Mapped[str] = mapped_column(String(100))
    openapi_version: Mapped[str] = mapped_column(String(20))
    specification: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    project: Mapped[Project] = relationship(back_populates="contracts")


class ContractComparison(Base):
    __tablename__ = "contract_comparisons"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_comparisons_project_id"),
        ForeignKeyConstraint(
            ["project_id", "baseline_id"],
            ["api_contracts.project_id", "api_contracts.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["project_id", "candidate_id"],
            ["api_contracts.project_id", "api_contracts.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "project_id",
            "baseline_id",
            "candidate_id",
            "engine_version",
            "normalization_version",
            name="uq_comparisons_pair_engine",
        ),
        CheckConstraint("baseline_id <> candidate_id", name="ck_comparisons_distinct"),
        CheckConstraint("jsonb_typeof(result) = 'object'", name="ck_comparisons_result"),
        CheckConstraint("change_count >= 0 AND change_count <= 2000", name="ck_comparisons_count"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    baseline_id: Mapped[UUID]
    candidate_id: Mapped[UUID]
    engine_version: Mapped[str] = mapped_column(String(40))
    normalization_version: Mapped[int] = mapped_column(Integer)
    change_count: Mapped[int] = mapped_column(Integer)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[str] = mapped_column(String(100))
    api_version: Mapped[str] = mapped_column(String(100))
    document_type: Mapped[str] = mapped_column(String(40))
    source_ref: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(30))
    content_sha256: Mapped[str] = mapped_column(String(64))
    chunking_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_search", "search_vector", postgresql_using="gin"),
        UniqueConstraint("document_id", "ordinal", name="uq_document_chunk_ordinal"),
        CheckConstraint("ordinal >= 0", name="ck_document_chunk_ordinal"),
        CheckConstraint(
            "length(content) > 0 AND length(content) <= 2000", name="ck_document_chunk_size"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(Integer)
    start_char: Mapped[int] = mapped_column(Integer)
    end_char: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    search_vector: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple'::regconfig, content)", persisted=True)
    )


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_analysis_project_id"),
        ForeignKeyConstraint(
            ["project_id", "comparison_id"],
            ["contract_comparisons.project_id", "contract_comparisons.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("jsonb_typeof(request) = 'object'", name="ck_analysis_request"),
        CheckConstraint("jsonb_typeof(report) = 'object'", name="ck_analysis_report"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(index=True)
    comparison_id: Mapped[UUID]
    change_id: Mapped[str] = mapped_column(String(64))
    request: Mapped[dict[str, Any]] = mapped_column(JSONB)
    report: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        CheckConstraint("dimensions BETWEEN 1 AND 2000", name="ck_embedding_dimensions"),
        CheckConstraint("vector_dims(embedding) = dimensions", name="ck_embedding_vector"),
        CheckConstraint("length(btrim(model)) > 0", name="ck_embedding_model"),
    )
    chunk_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(String(100))
    dimensions: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConversationSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        UniqueConstraint("project_id", "id", name="uq_sessions_project_id"),
        CheckConstraint("length(btrim(title)) BETWEEN 1 AND 200", name="ck_session_title"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionMessage(Base):
    __tablename__ = "session_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "session_id"], ["sessions.project_id", "sessions.id"], ondelete="CASCADE"
        ),
        UniqueConstraint("session_id", "sequence", name="uq_message_sequence"),
        UniqueConstraint("session_id", "request_id", name="uq_message_request"),
        CheckConstraint("sequence BETWEEN 1 AND 1000", name="ck_message_sequence"),
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="ck_message_role"),
        CheckConstraint("length(btrim(content)) BETWEEN 1 AND 4000", name="ck_message_content"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID]
    session_id: Mapped[UUID]
    request_id: Mapped[UUID]
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkflowState(Base):
    __tablename__ = "workflow_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "session_id"], ["sessions.project_id", "sessions.id"], ondelete="CASCADE"
        ),
        ForeignKeyConstraint(
            ["project_id", "analysis_id"],
            ["analysis_runs.project_id", "analysis_runs.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN ('running', 'waiting_for_user', 'waiting_for_approval', "
            "'completed', 'failed')",
            name="ck_workflow_status",
        ),
        CheckConstraint("revision >= 0", name="ck_workflow_revision"),
        CheckConstraint("length(btrim(reason)) BETWEEN 1 AND 1000", name="ck_workflow_reason"),
    )
    session_id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    analysis_id: Mapped[UUID | None]
    status: Mapped[str] = mapped_column(String(30))
    revision: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(1000))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ToolRun(Base):
    __tablename__ = "tool_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "session_id"], ["sessions.project_id", "sessions.id"], ondelete="CASCADE"
        ),
        CheckConstraint(
            "operation IN ('search_code', 'search_knowledge')", name="ck_tool_run_operation"
        ),
        CheckConstraint("status IN ('ok', 'rejected', 'unavailable')", name="ck_tool_run_status"),
        CheckConstraint("jsonb_typeof(result) = 'object'", name="ck_tool_run_result"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    project_id: Mapped[UUID]
    session_id: Mapped[UUID] = mapped_column(index=True)
    operation: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
