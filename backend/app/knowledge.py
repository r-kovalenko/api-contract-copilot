"""Context-bound retrieval with explicit storage failure, never fabricated evidence."""

from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.db.knowledge import search_chunks
from app.db.repositories import get_project
from app.db.session import session_scope
from app.knowledge_schemas import KnowledgeHit, KnowledgeRequest, KnowledgeResult


class KnowledgeError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class KnowledgeSearch:
    """Host selects an authorized project; tool arguments cannot override it."""

    def __init__(self, engine: Engine, project_id: UUID):
        self.engine = engine
        self.project_id = project_id

    def search(self, request: KnowledgeRequest) -> KnowledgeResult:
        try:
            with session_scope(self.engine) as session:
                rows = search_chunks(session, self.project_id, request)
                if get_project(session, self.project_id) is None:
                    raise KnowledgeError("unknown_project")
                return KnowledgeResult(
                    project_id=self.project_id,
                    query=request.query,
                    api_version=request.api_version,
                    truncated=len(rows) > request.limit,
                    hits=[
                        KnowledgeHit(
                            source_id=chunk.id,
                            document_id=document.id,
                            provider=document.provider,
                            api_version=document.api_version,
                            document_type=document.document_type,
                            source_ref=document.source_ref,
                            start_char=chunk.start_char,
                            end_char=chunk.end_char,
                            snippet=chunk.content,
                            score=score,
                        )
                        for chunk, document, score in rows[: request.limit]
                    ],
                )
        except SQLAlchemyError:
            raise KnowledgeError("knowledge_unavailable") from None
