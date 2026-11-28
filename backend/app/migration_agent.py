"""Pure advisory planner. Providers select grounded templates, never executable actions."""

from typing import Protocol

from app.analysis_schemas import ImpactReport
from app.migration_schemas import MigrationPlan, PlanDraft, ProposedTask, Step

INSTRUCTIONS = {
    "review_change": "Review the selected contract change before choosing a migration approach.",
    "inspect_usage": "Inspect the cited code match; confirm whether this consumer is affected.",
    "review_documentation": "Check the cited documentation against the candidate contract.",
    "test_candidate": "Add a compatibility test and run it against the candidate contract.",
}


class PlanProvider(Protocol):
    def generate(self, sources: dict[str, str]) -> str: ...


class FakePlanProvider:
    def generate(self, sources: dict[str, str]) -> str:
        return PlanDraft(
            steps=[{"action": kind, "source_ids": [sid]} for sid, kind in sources.items()]
        ).model_dump_json()


def generate_plan(report: ImpactReport, provider: PlanProvider | None = None) -> MigrationPlan:
    # Only IDs and source kinds cross this boundary: retrieved text cannot inject instructions.
    sources = {report.change.id: "review_change"}
    if report.code:
        sources.update({hit.id: "inspect_usage" for hit in report.code.hits})
    if report.knowledge:
        sources.update(
            {str(hit.source_id): "review_documentation" for hit in report.knowledge.hits}
        )
    raw = (provider or FakePlanProvider()).generate(dict(sources))
    if len(raw.encode("utf-8")) > 16384:
        raise ValueError("Plan output too large")
    draft = PlanDraft.model_validate_json(raw)
    covered = set()
    for item in draft.steps:
        if len(set(item.source_ids)) != len(item.source_ids):
            raise ValueError("Duplicate citation")
        for sid in item.source_ids:
            if sources.get(sid) != item.action or sid in covered:
                raise ValueError("Unsupported plan output")
            covered.add(sid)
    if covered != set(sources):
        raise ValueError("Incomplete plan output")
    steps = [
        Step(**item.model_dump(), order=i, instruction=INSTRUCTIONS[item.action])
        for i, item in enumerate(draft.steps, 1)
    ]
    questions = ["What consumer behavior and rollout criteria must the migration preserve?"]
    if not report.code or not report.code.hits:
        questions.append("Which consumer repository and call sites require migration?")
    if not report.knowledge or not report.knowledge.hits:
        questions.append("Is there an authoritative migration guide for the candidate version?")
    questions.append(
        "Do the cited sources conflict? Resolve any disagreement before implementation."
    )
    return MigrationPlan(
        steps=steps,
        test_checklist=[
            Step(
                order=1,
                action="test_candidate",
                source_ids=[report.change.id],
                instruction=INSTRUCTIONS["test_candidate"],
            )
        ],
        open_questions=questions,
        evidence_gaps=list(
            dict.fromkeys([*report.evidence_gaps, "offline_template_plan_requires_review"])
        ),
        proposed_task=ProposedTask(
            title="Review and implement consumer migration",
            description="Resolve open questions, review the evidence-backed steps, then implement "
            "and verify the checklist. This proposal requires human review.",
            source_ids=list(sources),
        ),
    )
