import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.analysis_schemas import AnalysisCreate
from app.analysis_service import AnalysisError, project_repositories
from app.main import app


@pytest.mark.parametrize(
    "override",
    [
        {"code_query": " "},
        {"knowledge_query": "a\n"},
        {"change_id": "unknown"},
        {"code_query": "x" * 201},
        {"repository": "../private"},
        {"root": "/private"},
    ],
)
def test_analysis_request_boundaries(override):
    with pytest.raises(ValidationError):
        AnalysisCreate.model_validate(
            {
                "comparison_id": uuid4(),
                "change_id": "a" * 64,
                "code_query": "customers",
                "knowledge_query": "customers",
                **override,
            }
        )


def test_project_config_is_scoped_and_not_request_controlled(monkeypatch, tmp_path):
    first, second = uuid4(), uuid4()
    monkeypatch.setenv("COPILOT_REPOSITORIES", json.dumps({str(first): {"demo": str(tmp_path)}}))
    assert project_repositories(first) == {"demo": tmp_path}
    assert project_repositories(second) == {}
    for config in ["[]", '{"bad"', json.dumps({str(first): {"demo": "../private"}})]:
        monkeypatch.setenv("COPILOT_REPOSITORIES", config)
        with pytest.raises(AnalysisError, match="invalid_repository_configuration"):
            project_repositories(first)


def test_analysis_body_is_limited_before_database_access():
    with TestClient(app) as client:
        assert (
            client.post(f"/api/projects/{uuid4()}/analyses", content=b"x" * 16385).status_code
            == 413
        )
