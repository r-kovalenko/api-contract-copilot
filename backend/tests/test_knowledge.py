from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.code_search import RepositorySearch
from app.knowledge import KnowledgeError, KnowledgeSearch
from app.knowledge_schemas import KnowledgeRequest
from app.main import app
from app.tool_registry import ToolRegistry


@pytest.mark.parametrize(
    "changes",
    [
        {"query": " "},
        {"query": "a" * 201},
        {"query": "a\x00b"},
        {"api_version": ""},
        {"provider": " "},
        {"limit": 21},
        {"limit": 0},
        {"project_id": str(uuid4())},
        {"document_type": "unsupported"},
    ],
)
def test_bounded_request(changes):
    with pytest.raises(ValidationError):
        KnowledgeRequest.model_validate({"query": "customer", "api_version": "v1", **changes})


def test_unconfigured_tool_is_not_empty_success():
    result = ToolRegistry(RepositorySearch({})).invoke(
        {
            "operation": "search_knowledge",
            "query": "customer",
            "api_version": "v1",
        }
    )
    assert result.model_dump() == {"status": "unavailable", "code": "knowledge_unavailable"}


def test_storage_failure_sanitized_in_service_api_and_tool():
    failure = OperationalError("private-host", {}, Exception("private-password"))
    service = KnowledgeSearch(None, uuid4())
    with patch("app.knowledge.session_scope", side_effect=failure):
        with pytest.raises(KnowledgeError) as error:
            service.search(KnowledgeRequest(query="customer", api_version="v1"))
        assert str(error.value) == "knowledge_unavailable"
        result = ToolRegistry(RepositorySearch({}), service).invoke(
            {
                "operation": "search_knowledge",
                "query": "customer",
                "api_version": "v1",
            }
        )
        assert result.model_dump() == {"status": "unavailable", "code": "knowledge_unavailable"}
    with patch("app.knowledge_api.get_engine", side_effect=failure), TestClient(app) as client:
        response = client.get(
            f"/api/projects/{uuid4()}/knowledge/search",
            params={"query": "customer", "api_version": "v1"},
        )
        assert response.status_code == 503
        assert "private" not in response.text


def test_rrf_known_ranking_duplicates_and_ties():
    from types import SimpleNamespace
    from uuid import UUID

    from app.rank_fusion import fuse

    def row(n):
        return SimpleNamespace(id=UUID(int=n)), SimpleNamespace(id=n), 999

    a, b, c = row(1), row(2), row(3)
    result = fuse([a, a, b], [b, c])
    assert [r[0].id.int for r in result] == [2, 1, 3]
    assert result[0][2] == pytest.approx(1 / 62 + 1 / 61)
    assert fuse([], []) == []
    assert [r[0].id.int for r in fuse([b], [a])] == [1, 2]
    assert fuse([a, b], [b, c]) == result


def test_hybrid_provider_failure_is_not_empty_success():
    from contextlib import contextmanager

    from app.embedding_provider import EmbeddingError, FakeEmbeddingProvider

    class Broken(FakeEmbeddingProvider):
        async def embed(self, texts):
            raise EmbeddingError("private-key")

    @contextmanager
    def session(_):
        yield None

    with (
        patch("app.knowledge.session_scope", session),
        patch("app.knowledge.get_project", return_value=object()),
    ):
        with pytest.raises(KnowledgeError, match="knowledge_unavailable"):
            KnowledgeSearch(None, uuid4(), Broken()).search(
                KnowledgeRequest(query="customer", api_version="v1", mode="hybrid")
            )


def test_rrf_candidate_cap():
    from types import SimpleNamespace
    from uuid import UUID

    from app.rank_fusion import fuse

    rows = [(SimpleNamespace(id=UUID(int=n)), None, 0) for n in range(1, 52)]
    assert len(fuse(rows, [])) == 50
