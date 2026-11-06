import json
import socket
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi import HTTPException
from pydantic import ValidationError

from app.contract_validation import MAX_BYTES, InvalidContract, parse_contract
from app.contracts import UploadMetadata, validate_upload, validation_slots


def sample(version="3.1.0"):
    return {"openapi": version, "info": {"title": "Synthetic API", "version": "1"}, "paths": {}}


@pytest.mark.parametrize("version", ["3.0.3", "3.1.0", "3.2.0"])
@pytest.mark.parametrize("media", ["application/json", "application/yaml"])
def test_supported_documents(version, media):
    spec = sample(version)
    text = json.dumps(spec) if media == "application/json" else yaml.safe_dump(spec)
    assert parse_contract(text.encode(), media) == spec


@pytest.mark.parametrize(
    "text,media,code",
    [
        ('{"openapi":"3.1.0","openapi":"3.0.3"}', "application/json", "duplicate_key"),
        ("info:\n  title: one\n  title: two", "application/yaml", "duplicate_key"),
        ("x: &a [1]\ny: *a", "application/yaml", "yaml_alias"),
        (
            "!!python/object/apply:os.system [echo forbidden]",
            "application/yaml",
            "invalid_document",
        ),
        ("---\na: 1\n---\nb: 2", "application/yaml", "invalid_document"),
        ("x: {200: response}", "application/yaml", "invalid_key"),
        ("[]", "application/json", "invalid_document"),
        ('{"openapi":"2.0"}', "application/json", "unsupported_openapi"),
        ('{"openapi":"3.1.0"}', "application/json", "invalid_openapi"),
        ('{"x":NaN}', "application/json", "invalid_number"),
        ('{"x":"\\u0000"}', "application/json", "invalid_text"),
        ('{"x":"\\ud800"}', "application/json", "invalid_text"),
        ("date: 2026-01-01", "application/yaml", "invalid_type"),
        ('{"', "application/json", "invalid_document"),
    ],
)
def test_invalid_documents(text, media, code):
    with pytest.raises(InvalidContract) as exc:
        parse_contract(text.encode(), media)
    assert exc.value.detail["code"] == code


@pytest.mark.parametrize(
    "ref",
    [
        "https://example.test/spec",
        "http://169.254.169.254/",
        "file:///etc/passwd",
        "../spec.yaml",
        "#missing",
    ],
)
def test_external_references_rejected_without_network(ref, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Validation attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    spec = sample()
    spec["components"] = {"schemas": {"Customer": {"$ref": ref}}}
    with pytest.raises(InvalidContract, match="Only local"):
        parse_contract(json.dumps(spec).encode(), "application/json")


def test_local_reference_and_recursive_schema_are_supported():
    spec = sample()
    spec["components"] = {
        "schemas": {
            "Node": {
                "type": "object",
                "properties": {"next": {"$ref": "#/components/schemas/Node"}},
            },
            "Other": {"$ref": "#/components/schemas/Node"},
        }
    }
    assert parse_contract(json.dumps(spec).encode(), "application/json") == spec
    spec["components"]["schemas"]["Other"]["$ref"] = "#/components/schemas/Missing"
    with pytest.raises(InvalidContract, match="does not resolve"):
        parse_contract(json.dumps(spec).encode(), "application/json")


@pytest.mark.parametrize("media", ["application/json", "application/yaml"])
def test_depth_and_node_limits(media):
    for value in [{"x": [0] * 21000}, {"x": [[[[0]]]]}]:
        if len(value["x"]) == 1:
            for _ in range(45):
                value = {"x": value}
        text = json.dumps(value) if media == "application/json" else yaml.safe_dump(value)
        with pytest.raises(InvalidContract, match="limit|nesting"):
            parse_contract(text.encode(), media)


def test_size_and_encoding_limits():
    with pytest.raises(InvalidContract):
        parse_contract(b"x" * (MAX_BYTES + 1), "application/json")
    with pytest.raises(InvalidContract):
        parse_contract(b"\xff", "application/json")


@pytest.mark.parametrize(
    "name", ["../api.json", "C:\\api.yaml", "/api.json", "a%2f.json", "api.json.exe", "a\x00.json"]
)
def test_source_name_rejects_paths(name):
    with pytest.raises(ValidationError):
        UploadMetadata(version="v1", source_name=name)


def test_real_worker_accepts_valid_and_rejects_invalid_input():
    assert validate_upload(json.dumps(sample()).encode(), "application/json") == sample()
    with pytest.raises(HTTPException) as exc:
        validate_upload(b'{"openapi":"3.1.0"}', "application/json")
    assert exc.value.status_code == 422


def test_worker_timeout_and_invalid_output_fail_closed():
    with patch(
        "app.contracts.subprocess.run", side_effect=subprocess.TimeoutExpired("validator", 10)
    ):
        with pytest.raises(HTTPException) as exc:
            validate_upload(b"{}", "application/json")
        assert exc.value.status_code == 422
    for result in [
        subprocess.CompletedProcess([], 1, b"", b"private error"),
        subprocess.CompletedProcess([], 0, b"not-json", b""),
        subprocess.CompletedProcess([], 0, b"{}", b""),
    ]:
        with (
            patch("app.contracts.subprocess.run", return_value=result),
            pytest.raises(HTTPException),
        ):
            validate_upload(b"{}", "application/json")


def test_validation_concurrency_is_bounded():
    assert validation_slots.acquire(blocking=False)
    assert validation_slots.acquire(blocking=False)
    try:
        with pytest.raises(HTTPException) as exc:
            validate_upload(b"{}", "application/json")
        assert exc.value.status_code == 503
    finally:
        validation_slots.release()
        validation_slots.release()


@pytest.mark.parametrize(
    "name,media",
    [("customer-v1.json", "application/json"), ("customer-v2.yaml", "application/yaml")],
)
def test_documented_examples(name, media):
    raw = (Path(__file__).resolve().parents[2] / "docs" / "examples" / name).read_bytes()
    assert parse_contract(raw, media)["info"]["title"] == "Synthetic Customer API"


@pytest.mark.parametrize(
    "keyword,value",
    [
        ("$id", "https://example.test/"),
        ("$dynamicRef", "#Node"),
        ("jsonSchemaDialect", "https://example.test/schema"),
    ],
)
def test_reference_rebasing_and_custom_dialects_are_rejected(keyword, value):
    spec = sample()
    spec[keyword] = value
    with pytest.raises(InvalidContract):
        parse_contract(json.dumps(spec).encode(), "application/json")


def test_worker_does_not_inherit_secrets(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "synthetic-private-url")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "synthetic-not-a-secret")
    result = subprocess.CompletedProcess([], 0, json.dumps({"specification": sample()}).encode())
    with patch("app.contracts.subprocess.run", return_value=result) as run:
        validate_upload(b"{}", "application/json")
    assert set(run.call_args.kwargs["env"]) <= {"SYSTEMROOT", "WINDIR"}
    assert run.call_args.kwargs["timeout"] == 10
