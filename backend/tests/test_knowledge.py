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
