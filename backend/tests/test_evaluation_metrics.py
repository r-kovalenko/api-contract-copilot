from uuid import uuid4

import pytest

from evaluation.dataset import load_dataset
from evaluation.metrics import score_contract, score_retrieval, summarize
from evaluation.run import test_database_url as validate_database_url


def test_recall_uses_unique_top_five_and_rejects_invalid_scope():
    case = next(c for c in load_dataset().retrieval_cases if c.kind == "ambiguous")
    ids = case.relevant_source_ids
    assert score_retrieval(case, "keyword", ids, set(ids)).recall_at_5 == 1
    missed = score_retrieval(case, "keyword", ids[:1], set(ids))
    assert missed.recall_at_5 == 0.5 and not missed.passed
    assert missed.missing == ids[1:]
    assert not score_retrieval(case, "hybrid", [ids[0]] * 5, set(ids)).passed
    assert not score_retrieval(case, "keyword", ids + [uuid4()], set(ids)).scope_valid
    beyond = [uuid4() for _ in range(5)] + ids
    assert score_retrieval(case, "keyword", beyond, set(beyond)).recall_at_5 == 0


def test_negative_cases_are_not_counted_as_perfect_recall():
    case = next(c for c in load_dataset().retrieval_cases if c.kind == "negative")
    sid = uuid4()
    keyword = score_retrieval(case, "keyword", [sid], {sid})
    hybrid = score_retrieval(case, "hybrid", [sid], {sid})
    assert keyword.recall_at_5 is None and not keyword.passed
    assert hybrid.recall_at_5 is None and hybrid.passed
    assert hybrid.negative_returned_count == 1
    assert not score_retrieval(case, "hybrid", [], set(), "unavailable").passed
    assert all(not row.passed for row in summarize([hybrid]))


def test_diff_missing_breaking_and_extra_changes_fail():
    case = next(c for c in load_dataset().contract_cases if c.id == "endpoint-removal")
    assert score_contract(case, case.expected_changes).passed
    missed = score_contract(case, [])
    assert not missed.passed and missed.missed_breaking == 1
    assert missed.coverage == 0 and missed.precision == 0
    duplicate = score_contract(case, case.expected_changes * 2)
    assert not duplicate.passed and duplicate.precision == 0.5
    empty = next(c for c in load_dataset().contract_cases if c.id == "unchanged")
    assert score_contract(empty, []).passed
    assert not score_contract(empty, [], "unavailable").passed
    assert not score_contract(empty, case.expected_changes).passed


@pytest.mark.parametrize("url", ["", "sqlite:///test", "postgresql+psycopg://localhost/production"])
def test_cli_rejects_non_test_databases(url):
    with pytest.raises(ValueError):
        validate_database_url(url)


@pytest.mark.parametrize("status,expected", [("passed", 0), ("failed", 1), ("error", 2)])
def test_cli_exit_status_and_sanitized_artifact(monkeypatch, tmp_path, status, expected):
    import json
    from types import SimpleNamespace

    from evaluation import run

    path = tmp_path / "report.json"
    monkeypatch.setattr("sys.argv", ["evaluation", "--output", str(path)])

    def fake_run(_):
        if status == "error":
            raise ValueError("private-password")
        return SimpleNamespace(
            status=status, model_dump_json=lambda **_: json.dumps({"status": status})
        )

    monkeypatch.setattr(run, "run_database", fake_run)
    assert run.main() == expected
    assert json.loads(path.read_text())["status"] == status
    assert "private" not in path.read_text()
