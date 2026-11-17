import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app import comparison
from app.comparison import ComparisonError, compare_contracts, normalize
from app.contract_validation import parse_contract

EXAMPLES = Path(__file__).resolve().parents[2] / "docs" / "examples"


def spec():
    return {
        "openapi": "3.1.0",
        "info": {"title": "Synthetic API", "version": "1"},
        "paths": {
            "/customers": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}},
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }


def test_real_rename_fixture_is_removal_and_addition_not_inferred_rename():
    baseline = parse_contract((EXAMPLES / "customer-v1.json").read_bytes(), "application/json")
    candidate = parse_contract((EXAMPLES / "customer-v2.yaml").read_bytes(), "application/yaml")
    result = compare_contracts(baseline, candidate)
    assert {(c.rule_id, c.severity) for c in result.changes} == {
        ("response-required-property-removed", "breaking"),
        ("response-required-property-added", "non_breaking"),
    }
    assert all(c.path == "/customers" and c.operation == "GET" for c in result.changes)
    assert result.engine_version == "1.37.0"
    assert result.baseline_sha256 != result.candidate_sha256
    assert compare_contracts(baseline, candidate) == result


@pytest.mark.parametrize("kind", ["removal", "required", "optional"])
def test_real_engine_semantics(kind):
    baseline = spec()
    candidate = copy.deepcopy(baseline)
    schema = candidate["paths"]["/customers"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ]
    if kind == "removal":
        candidate["paths"] = {}
    elif kind == "required":
        schema["required"] = ["name"]
    else:
        schema["properties"]["locale"] = {"type": "string"}
    changes = compare_contracts(baseline, candidate).changes
    assert changes
    if kind == "optional":
        assert all(c.severity == "non_breaking" for c in changes)
        assert any(c.rule_id == "new-optional-request-property" for c in changes)
    else:
        assert any(c.severity == "breaking" for c in changes)
        assert any(
            "removed" in c.rule_id if kind == "removal" else "required" in c.rule_id
            for c in changes
        )


@pytest.mark.parametrize("version", ["3.0.3", "3.1.0", "3.2.0"])
def test_identical_specs_and_documentation_only_edits_have_no_changelog(version):
    baseline = spec()
    baseline["openapi"] = version
    assert compare_contracts(baseline, baseline).changes == []
    candidate = copy.deepcopy(baseline)
    candidate["info"]["description"] = "Documentation only"
    assert compare_contracts(baseline, candidate).changes == []


@pytest.mark.parametrize(
    "ref",
    [
        "https://example.com/api.json",
        "file:///etc/passwd",
        "../other.json",
        "http://169.254.169.254/latest/meta-data",
    ],
)
def test_external_refs_rejected_before_executing(monkeypatch, ref):
    baseline = spec()
    baseline["components"] = {"schemas": {"X": {"$ref": ref}}}
    monkeypatch.setattr(comparison, "verified_binary", lambda: pytest.fail("Must not execute"))
    with pytest.raises(ComparisonError, match="invalid_input"):
        compare_contracts(baseline, spec())


def test_input_limits_and_schema_rebasing():
    for addition in [{"description": "x" * (1024 * 1024)}, {"$id": "https://example.com"}]:
        baseline = spec() | addition
        with pytest.raises(ComparisonError, match="invalid_input"):
            compare_contracts(baseline, spec())


def record(**kwargs):
    return {
        "id": "test-rule",
        "text": "Synthetic finding",
        "level": 3,
        "fingerprint": "012345abcdef",
        "operation": "GET",
        "path": "/x",
        **kwargs,
    }


def test_normalization_preserves_warning_and_evidence_with_stable_ids():
    first = record(baseSource={"file": "baseline.json", "line": 10})
    second = record(fingerprint="012345abcdee", level=2, disclaimers=["Potential effect"])
    result = normalize(json.dumps([first, second]).encode())
    assert result == normalize(json.dumps([second, first]).encode())
    assert {c.severity for c in result} == {"breaking", "potentially_breaking"}
    first["baseSource"]["line"] = 20
    assert normalize(json.dumps([first]).encode())[0].id in {c.id for c in result}


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"null",
        b"{}",
        b"not json",
        b"[{}]",
        json.dumps([record(level=4)]).encode(),
        json.dumps([record(baseSource={"file": "/private/path"})]).encode(),
        json.dumps([record(unknown="field")]).encode(),
        json.dumps([record(), record(text="conflicting finding")]).encode(),
    ],
)
def test_invalid_output_fails_closed(raw):
    with pytest.raises(ComparisonError, match="invalid_output"):
        normalize(raw)


def test_missing_or_modified_binary(monkeypatch, tmp_path):
    executable = tmp_path / "oasdiff"
    monkeypatch.setattr(comparison, "binary_path", lambda: executable)
    with pytest.raises(ComparisonError, match="engine_unavailable"):
        comparison.verified_binary()
    executable.write_bytes(b"untrusted executable")
    with pytest.raises(ComparisonError, match="engine_checksum_mismatch"):
        comparison.verified_binary()


@pytest.mark.parametrize(
    "script,code",
    [
        ("import time; time.sleep(10)", "timeout"),
        ("import sys; sys.stdout.write('x'*100000)", "output_limit"),
        ("import sys; sys.stderr.write('x'*100000)", "output_limit"),
        ("import sys; sys.stderr.write('private info'); sys.exit(2)", "engine_failed"),
    ],
)
def test_real_child_failure_limits_and_cleanup(monkeypatch, tmp_path, script, code):
    popen = subprocess.Popen
    children = []

    def start(_args, **kwargs):
        child = popen([sys.executable, "-c", script], **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(comparison.subprocess, "Popen", start)
    monkeypatch.setattr(comparison, "TIMEOUT_SECONDS", 0.5 if code == "timeout" else 5)
    monkeypatch.setattr(comparison, "MAX_OUTPUT_BYTES", 1024)
    with pytest.raises(ComparisonError, match=code) as exc:
        comparison.run_engine(Path(sys.executable), tmp_path)
    assert "private info" not in str(exc.value)
    assert children[0].poll() is not None
    assert children[0].stdout.closed and children[0].stderr.closed


def test_fixed_arguments_clean_environment_and_temporary_cleanup(monkeypatch):
    popen = subprocess.Popen
    directories = []
    monkeypatch.setenv("PROVIDER_API_KEY", "synthetic-must-not-inherit")
    monkeypatch.setenv("OASDIFF_CONFIG", "untrusted.yaml")

    def start(args, **kwargs):
        assert args[1:4] == ["changelog", "baseline.json", "candidate.json"]
        assert "--allow-external-refs=false" in args and "--open" not in args
        assert kwargs["shell"] is False
        assert "PROVIDER_API_KEY" not in kwargs["env"]
        assert "OASDIFF_CONFIG" not in kwargs["env"]
        directories.append(kwargs["cwd"])
        assert (kwargs["cwd"] / "config.json").read_text() == "{}"
        return popen(args, **kwargs)

    monkeypatch.setattr(comparison.subprocess, "Popen", start)
    compare_contracts(spec(), spec())
    assert not directories[0].exists()


def test_busy_and_slot_release_on_failure(monkeypatch):
    assert comparison._slots.acquire(blocking=False)
    assert comparison._slots.acquire(blocking=False)
    try:
        with pytest.raises(ComparisonError, match="busy"):
            compare_contracts(spec(), spec())
    finally:
        comparison._slots.release()
        comparison._slots.release()
    monkeypatch.setattr(comparison, "verified_binary", lambda: Path("missing"))
    for _ in range(3):
        with pytest.raises(ComparisonError, match="engine_unavailable"):
            compare_contracts(spec(), spec())


def test_malformed_levels_wrong_source_and_excess_changes():
    for records in [
        [record(level=True)],
        [record(baseSource={"file": "candidate.json"})],
        [record()] * (comparison.MAX_CHANGES + 1),
    ]:
        with pytest.raises(ComparisonError, match="invalid_output"):
            normalize(json.dumps(records).encode())


def test_real_engine_resolves_local_references():
    baseline = spec()
    baseline["components"] = {
        "schemas": {"Customer": {"type": "object", "properties": {"name": {"type": "string"}}}}
    }
    baseline["paths"]["/customers"]["post"]["requestBody"]["content"]["application/json"][
        "schema"
    ] = {"$ref": "#/components/schemas/Customer"}
    candidate = copy.deepcopy(baseline)
    candidate["components"]["schemas"]["Customer"]["required"] = ["name"]
    assert any(c.severity == "breaking" for c in compare_contracts(baseline, candidate).changes)
