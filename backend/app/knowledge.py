"""Context-bound retrieval with explicit storage failure, never fabricated evidence."""

import asyncio
from uuid import UUID

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.db.knowledge import search_chunks, search_vectors
from app.db.repositories import get_project
from app.db.session import session_scope
from app.embedding_provider import EmbeddingError, EmbeddingProvider, embed_chunks, provider
from app.knowledge_schemas import KnowledgeHit, KnowledgeRequest, KnowledgeResult
from app.rank_fusion import CANDIDATE_LIMIT, fuse


class KnowledgeError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class KnowledgeSearch:
    """Host selects an authorized project; tool arguments cannot override it."""

    def __init__(
        self, engine: Engine, project_id: UUID, embedding_provider: EmbeddingProvider | None = None
    ):
        self.engine = engine
        self.project_id = project_id
        self.embedding_provider = embedding_provider

    def search(self, request: KnowledgeRequest) -> KnowledgeResult:
        try:
            with session_scope(self.engine) as session:
                if request.mode == "hybrid":
                    session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                if get_project(session, self.project_id) is None:
                    raise KnowledgeError("unknown_project")
                model = None
                capped = False
                if request.mode == "hybrid":
                    embedding = self.embedding_provider or provider()
                    vector = asyncio.run(embed_chunks(embedding, [request.query]))[0]
                    keyword = search_chunks(session, self.project_id, request, CANDIDATE_LIMIT)
                    vectors = search_vectors(
                        session, self.project_id, request, embedding.spec, vector
                    )
                    capped = len(keyword) > CANDIDATE_LIMIT or len(vectors) > CANDIDATE_LIMIT
                    rows = fuse(keyword, vectors)
                    model = embedding.spec.model
                else:
                    rows = search_chunks(session, self.project_id, request)
                return KnowledgeResult(
                    mode=request.mode,
                    embedding_model=model,
                    project_id=self.project_id,
                    query=request.query,
                    api_version=request.api_version,
                    truncated=capped or len(rows) > request.limit,
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
        except (SQLAlchemyError, EmbeddingError):
            raise KnowledgeError("knowledge_unavailable") from None
