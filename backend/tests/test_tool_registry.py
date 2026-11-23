import pytest

from app.code_search import RepositorySearch, SearchError
from app.tool_registry import ToolRegistry, response_adapter


def payload(**changes):
    return {"operation": "search_code", "repository": "consumer", "query": "full_name", **changes}


@pytest.fixture
def registry(tmp_path):
    (tmp_path / "client.py").write_text("full_name\nfull_name\n", encoding="utf-8")
    return ToolRegistry(RepositorySearch({"consumer": tmp_path}))


def test_evidence_roundtrip_preserves_references_and_truncation(registry):
    response = registry.invoke(payload(limit=1))
    assert response.status == "ok"
    assert response.result.truncated
    hit = response.result.hits[0]
    assert (hit.path, hit.line, hit.snippet) == ("client.py", 1, "full_name")
    assert len(hit.id) == len(hit.file_sha256) == 64
    assert response_adapter.validate_json(response.model_dump_json()) == response
    assert registry.invoke(payload(limit=1)) == response


def test_no_matches_is_success_without_invented_evidence(registry):
    response = registry.invoke(payload(query="missing"))
    assert response.status == "ok"
    assert response.result.hits == []
    assert not response.result.truncated


@pytest.mark.parametrize(
    "changes",
    [
        {"operation": "get_file"},
        {"operation": "__dict__"},
        {"scope": "../other"},
        {"query": ""},
        {"limit": True},
        {"limit": 101},
        {"root": "/private"},
        {"executable": "sh"},
        {"query": "a\nb"},
    ],
)
def test_invalid_calls_rejected_before_execution(changes, monkeypatch, registry):
    def forbidden(*args):
        pytest.fail("Invalid call executed search")

    monkeypatch.setattr(registry._search, "search", forbidden)
    assert registry.invoke(payload(**changes)).model_dump() == {
        "status": "rejected",
        "code": "invalid_request",
    }


def test_repository_allowlist_and_missing_source(registry, tmp_path):
    assert registry.invoke(payload(repository="other")).model_dump() == {
        "status": "rejected",
        "code": "unknown_repository",
    }
    unavailable = ToolRegistry(RepositorySearch({"consumer": tmp_path / "missing"}))
    result = unavailable.invoke(payload())
    assert result.status == "unavailable"
    assert "result" not in result.model_dump()
    assert str(tmp_path) not in result.model_dump_json()


@pytest.mark.parametrize(
    "code",
    [
        "repository_changed",
        "corpus_limit",
        "busy",
        "timeout",
        "engine_unavailable",
        "engine_failed",
        "output_limit",
        "invalid_output",
        "repository_unavailable",
    ],
)
def test_failures_cannot_become_empty_success(code, registry, monkeypatch):
    def fail(request):
        raise SearchError(code)

    monkeypatch.setattr(registry._search, "search", fail)
    response = registry.invoke(payload())
    assert response.model_dump() == {"status": "unavailable", "code": code}
    assert response_adapter.validate_json(response.model_dump_json()) == response


def test_unexpected_failure_is_not_swallowed(registry, monkeypatch):
    def fail(request):
        raise RuntimeError("internal")

    monkeypatch.setattr(registry._search, "search", fail)
    with pytest.raises(RuntimeError):
        registry.invoke(payload())
