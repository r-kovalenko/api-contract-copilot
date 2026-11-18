import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from app import code_search as search


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "consumer"
    root.mkdir()
    (root / "client.py").write_text(
        'def label(customer):\n    return customer["full_name"]\n', encoding="utf-8"
    )
    return root


def engine(root):
    assert shutil.which("rg"), "Install ripgrep; CI requires real-engine search tests"
    return search.RepositorySearch({"consumer": root})


def request(**kwargs):
    return search.SearchRequest(repository="consumer", query="full_name", **kwargs)


def test_real_literal_search_evidence_and_stable_ids(repository):
    service = engine(repository)
    result = service.search(request())
    assert result == service.search(request())
    assert result.searched_files == 1
    assert not result.truncated
    hit = result.hits[0]
    assert (hit.path, hit.line, hit.snippet) == ("client.py", 2, '    return customer["full_name"]')
    assert len(hit.id) == len(hit.file_sha256) == 64
    (repository / "client.py").write_text("full_name\n", encoding="utf-8")
    assert service.search(request()).hits[0].id != hit.id


@pytest.mark.parametrize(
    "query", ["--pre=echo bad", "$(touch stolen)", "; echo bad", "[a-z].*", "café"]
)
def test_flags_shell_and_regex_are_literal(repository, query, monkeypatch):
    (repository / "literal.py").write_text(query + "\n", encoding="utf-8")
    monkeypatch.setenv("RIPGREP_CONFIG_PATH", str(repository / "malicious-config"))
    (repository / "malicious-config").write_text("--pre=nonexistent-command\n", encoding="utf-8")
    result = engine(repository).search(search.SearchRequest(repository="consumer", query=query))
    assert [(hit.path, hit.snippet) for hit in result.hits] == [("literal.py", query)]
    assert not (repository / "stolen").exists()


def test_no_matches_and_case_sensitive(repository):
    assert (
        engine(repository)
        .search(search.SearchRequest(repository="consumer", query="FULL_NAME"))
        .hits
        == []
    )


@pytest.mark.parametrize(
    "scope", ["../outside", "/tmp", "C:/outside", "x\\y", "a/../b", "./a", "a//b"]
)
def test_reject_path_traversal(scope):
    with pytest.raises(ValidationError):
        request(scope=scope)


@pytest.mark.parametrize("query", ["", " ", "one\ntwo", "one\0two", "x" * 201])
def test_reject_invalid_queries(query):
    with pytest.raises(ValidationError):
        search.SearchRequest(repository="consumer", query=query)


def test_scopes_and_unknown_repository(repository):
    child = repository / "src"
    child.mkdir()
    (child / "nested.ts").write_text("full_name\n", encoding="utf-8")
    service = engine(repository)
    assert [hit.path for hit in service.search(request(scope="src")).hits] == ["src/nested.ts"]
    assert len(service.search(request(scope="client.py")).hits) == 1
    with pytest.raises(search.SearchError, match="unknown_repository"):
        service.search(search.SearchRequest(repository="unknown", query="full_name"))
    with pytest.raises(search.SearchError, match="repository_unavailable"):
        service.search(request(scope="missing"))


def test_exclusions_binary_encoding_and_hard_links(repository):
    for name in [
        ".env",
        ".env.py",
        "credentials.py",
        "secrets.ts",
        "private_key.py",
        "data.pem",
        "node_modules/lib.js",
        ".git/config.py",
        "dist/bundle.js",
    ]:
        file = repository / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("full_name\n", encoding="utf-8")
    (repository / "binary.py").write_bytes(b"full_name\0private")
    (repository / "encoding.py").write_bytes(b"full_name\xff")
    (repository / "large.py").write_bytes(b"x" * (search.MAX_FILE_BYTES + 1))
    original = repository.parent / "outside.py"
    original.write_text("full_name\n", encoding="utf-8")
    os.link(original, repository / "hard.py")
    result = engine(repository).search(request())
    assert [hit.path for hit in result.hits] == ["client.py"]
    assert result.skipped_entries > 0
    with pytest.raises(search.SearchError, match="unsafe_scope"):
        engine(repository).search(request(scope="credentials.py"))


def test_symlink_file_and_directory_escape(repository):
    outside = repository.parent / "outside"
    outside.mkdir()
    (outside / "private.py").write_text("full_name\n", encoding="utf-8")
    try:
        (repository / "linked.py").symlink_to(outside / "private.py")
        (repository / "linked-dir").symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name == "nt":
            pytest.skip("Windows requires symlink privilege; mandatory on Linux CI")
        raise
    service = engine(repository)
    assert [hit.path for hit in service.search(request()).hits] == ["client.py"]
    for scope in ["linked.py", "linked-dir", "linked-dir/private.py"]:
        with pytest.raises(search.SearchError, match="unsafe_scope"):
            service.search(request(scope=scope))


def test_result_limit_and_long_snippet_are_explicit(repository):
    (repository / "a.py").write_text("full_name" + "x" * 1100 + "\nfull_name\n", encoding="utf-8")
    result = engine(repository).search(request(limit=1))
    assert result.truncated
    assert result.hits[0].path == "a.py"
    assert result.hits[0].snippet_truncated
    assert len(result.hits[0].snippet) == 1000


@pytest.mark.parametrize(
    "constant,value", [("MAX_FILES", 0), ("MAX_CORPUS_BYTES", 1), ("MAX_ENTRIES", 1)]
)
def test_corpus_limits_fail_without_partial_results(repository, monkeypatch, constant, value):
    monkeypatch.setattr(search, constant, value)
    with pytest.raises(search.SearchError, match="corpus_limit"):
        engine(repository).search(request())


def test_missing_engine_and_busy(repository):
    with pytest.raises(search.SearchError, match="engine_unavailable"):
        search.RepositorySearch({"consumer": repository}, repository / "absent").search(request())
    with search._slots, search._slots, pytest.raises(search.SearchError, match="busy"):
        engine(repository).search(request())


@pytest.mark.parametrize(
    "script,code",
    [
        ("import time; time.sleep(30)", "timeout"),
        ('import sys; sys.stdout.write("x" * 3000000)', "output_limit"),
        ('import sys; sys.stderr.write("x" * 3000000)', "output_limit"),
        ('import sys; sys.stderr.write("private password"); sys.exit(2)', "engine_failed"),
    ],
)
def test_process_failures_are_bounded_and_safe(tmp_path, monkeypatch, script, code):
    popen = subprocess.Popen
    processes = []

    def synthetic_process(args, **kwargs):
        assert kwargs["shell"] is False
        assert args[-3:] == ["--", "literal", "."]
        process = popen([sys.executable, "-c", script], **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(search.subprocess, "Popen", synthetic_process)
    with pytest.raises(search.SearchError, match=code) as caught:
        search.run_rg(
            Path(sys.executable),
            tmp_path,
            "literal",
            time.monotonic() + (0.1 if code == "timeout" else 10),
        )
    assert "private" not in str(caught.value)
    assert all(process.poll() is not None for process in processes)


@pytest.mark.parametrize(
    "raw", [b"not json", b"{}", b'{"type":"match","data":{}}', b'{"type":"unexpected"}']
)
def test_invalid_engine_output(raw):
    with pytest.raises(search.SearchError, match="invalid_output"):
        search.normalize(raw, request(), {}, 0)


def test_engine_cannot_return_outside_manifest():
    raw = json.dumps(
        {
            "type": "match",
            "data": {
                "path": {"text": "../outside.py"},
                "line_number": 1,
                "lines": {"text": "full_name"},
            },
        }
    ).encode()
    with pytest.raises(search.SearchError, match="invalid_output"):
        search.normalize(raw, request(), {}, 0)


def test_long_prefix_keeps_match_in_snippet(repository):
    (repository / "client.py").write_text("x" * 2000 + "full_name\n", encoding="utf-8")
    hit = engine(repository).search(request()).hits[0]
    assert "full_name" in hit.snippet
    assert hit.snippet_start_column == 1801
    assert hit.snippet_truncated


def test_snapshot_timeout(repository, monkeypatch):
    monkeypatch.setattr(search, "TIMEOUT_SECONDS", -1)
    with pytest.raises(search.SearchError, match="timeout"):
        engine(repository).search(request())
