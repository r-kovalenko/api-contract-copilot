"""Offline metrics; labels are never used by the retrieval implementation."""

from collections import Counter
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from evaluation.dataset import ContractCase, ExpectedChange, RetrievalCase, Split

RECALL_TARGET = 0.8


class ResultModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RetrievalScore(ResultModel):
    case_id: str
    split: Split
    mode: Literal["keyword", "hybrid"]
    expected: list[UUID]
    returned: list[UUID]
    missing: list[UUID]
    unexpected: list[UUID]
    recall_at_5: float | None
    negative_returned_count: int | None
    scope_valid: bool
    passed: bool
    error: str | None = None


def score_retrieval(
    case: RetrievalCase,
    mode: str,
    returned: list[UUID],
    allowed: set[UUID],
    error: str | None = None,
) -> RetrievalScore:
    top = returned[:5]
    gold, found = set(case.relevant_source_ids), set(top)
    recall = len(gold & found) / len(gold) if gold else None
    valid = len(returned) <= 5 and len(returned) == len(set(returned)) and set(returned) <= allowed
    # Hybrid ranks nearest neighbors, not an abstention classifier. Negative returns are diagnostic.
    passed = (
        not error and valid and (recall >= RECALL_TARGET if gold else mode == "hybrid" or not top)
    )
    return RetrievalScore(
        case_id=case.id,
        split=case.split,
        mode=mode,
        expected=sorted(gold),
        returned=top,
        missing=sorted(gold - found),
        unexpected=sorted(found - gold),
        recall_at_5=recall,
        negative_returned_count=None if gold else len(top),
        scope_valid=valid,
        passed=passed,
        error=error,
    )


class ContractScore(ResultModel):
    case_id: str
    split: Split
    expected: list[ExpectedChange]
    actual: list[ExpectedChange]
    missing: list[ExpectedChange]
    unexpected: list[ExpectedChange]
    missed_breaking: int
    precision: float
    coverage: float
    passed: bool
    error: str | None = None


def score_contract(
    case: ContractCase, actual: list[ExpectedChange], error: str | None = None
) -> ContractScore:
    def key(change):
        return (change.rule_id, change.severity, change.operation, change.path)

    expected_counts = Counter(key(c) for c in case.expected_changes)
    actual_counts = Counter(key(c) for c in actual)

    def expand(counts):
        return [
            ExpectedChange(rule_id=r, severity=s, operation=o, path=p)
            for r, s, o, p in sorted(counts.elements())
        ]

    correct = sum((expected_counts & actual_counts).values())
    missing = expand(expected_counts - actual_counts)
    unexpected = expand(actual_counts - expected_counts)
    return ContractScore(
        case_id=case.id,
        split=case.split,
        expected=case.expected_changes,
        actual=actual,
        missing=missing,
        unexpected=unexpected,
        missed_breaking=sum(c.severity == "breaking" for c in missing),
        precision=correct / len(actual) if actual else (1.0 if not case.expected_changes else 0.0),
        coverage=correct / len(case.expected_changes) if case.expected_changes else 1.0,
        passed=not error and not missing and not unexpected,
        error=error,
    )


class Summary(ResultModel):
    split: Split
    mode: Literal["keyword", "hybrid"]
    positive_cases: int
    negative_cases: int
    macro_recall_at_5: float
    negative_cases_with_results: int
    passed: bool


def summarize(rows: list[RetrievalScore]) -> list[Summary]:
    results = []
    for split in ("development", "held_out"):
        for mode in ("keyword", "hybrid"):
            selected = [r for r in rows if r.split == split and r.mode == mode]
            positive = [r for r in selected if r.recall_at_5 is not None]
            recall = sum(r.recall_at_5 for r in positive) / len(positive) if positive else 0.0
            results.append(
                Summary(
                    split=split,
                    mode=mode,
                    positive_cases=len(positive),
                    negative_cases=len(selected) - len(positive),
                    macro_recall_at_5=recall,
                    negative_cases_with_results=sum(
                        bool(r.negative_returned_count) for r in selected
                    ),
                    passed=bool(positive)
                    and recall >= RECALL_TARGET
                    and all(r.passed for r in selected),
                )
            )
    return results
