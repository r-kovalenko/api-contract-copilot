"""Fixture correctness, not retrieval quality scoring (task #48)."""

import copy

import pytest
from pydantic import ValidationError

from app.comparison import compare_contracts
from app.contract_validation import parse_contract
from evaluation.dataset import Dataset, load_dataset


def test_manifest_is_versioned_synthetic_and_contains_holdout():
    data = load_dataset()
    assert len(data.documents) == 10
    assert len(data.retrieval_cases) == 8
    assert {c.kind for c in data.retrieval_cases} == {"positive", "negative", "ambiguous"}
    assert len([c for c in data.retrieval_cases if c.split == "held_out"]) == 3
    assert len([c for c in data.contract_cases if c.split == "held_out"]) == 2


@pytest.mark.parametrize("case", load_dataset().contract_cases, ids=lambda c: c.id)
def test_contract_ground_truth_matches_pinned_engine(case):
    import json

    baseline = parse_contract(json.dumps(case.baseline).encode(), "application/json")
    candidate = parse_contract(json.dumps(case.candidate).encode(), "application/json")
    result = compare_contracts(baseline, candidate)
    actual = sorted((c.rule_id, c.severity, c.operation, c.path) for c in result.changes)
    expected = sorted((c.rule_id, c.severity, c.operation, c.path) for c in case.expected_changes)
    assert actual == expected
    assert result.engine_version == load_dataset().oasdiff_version


@pytest.mark.parametrize(
    "corruption",
    ["source", "scope", "split", "duplicate", "provenance", "negative", "text", "version"],
)
def test_invalid_or_drifting_labels_are_rejected(corruption):
    data = copy.deepcopy(load_dataset().model_dump(mode="json"))
    case = data["retrieval_cases"][0]
    if corruption == "source":
        case["relevant_source_ids"] = ["00000000-0000-0000-0000-000000000000"]
    elif corruption == "scope":
        case["request"]["api_version"] = "v1"
    elif corruption == "split":
        case["split"] = "held_out"
    elif corruption == "duplicate":
        data["retrieval_cases"].append(case)
    elif corruption == "provenance":
        data["provenance"] = "Unknown production export"
    elif corruption == "negative":
        case["kind"] = "negative"
    elif corruption == "text":
        data["documents"][0]["text"] += "changed"
    else:
        data["schema_version"] = 2
    with pytest.raises(ValidationError):
        Dataset.model_validate(data)
