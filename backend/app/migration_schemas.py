from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanCreate(StrictModel):
    analysis_id: UUID


class PlanItem(StrictModel):
    action: Literal["review_change", "inspect_usage", "review_documentation", "test_candidate"]
    source_ids: list[str] = Field(min_length=1, max_length=20)


class PlanDraft(StrictModel):
    steps: list[PlanItem] = Field(min_length=1, max_length=20)


class Step(PlanItem):
    order: int
    instruction: str


class ProposedTask(StrictModel):
    title: str
    description: str
    source_ids: list[str]


class MigrationPlan(StrictModel):
    schema_version: Literal[1] = 1
    status: Literal["needs_review"] = "needs_review"
    provider: Literal["offline"] = "offline"
    steps: list[Step]
    test_checklist: list[Step]
    open_questions: list[str]
    evidence_gaps: list[str]
    proposed_task: ProposedTask


class PlanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    analysis_id: UUID
    created_at: datetime


class PlanView(PlanSummary):
    plan: MigrationPlan
