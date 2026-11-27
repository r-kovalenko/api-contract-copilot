"""Typed execution plans: only the host registry's existing read-only calls."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.tool_registry import SearchCodeCall, SearchKnowledgeCall, ToolResponse
from app.workflow_schemas import WorkflowView

Step = Annotated[SearchCodeCall | SearchKnowledgeCall, Field(discriminator="operation")]


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    steps: list[Step] = Field(min_length=1, max_length=5)

    @field_validator("steps")
    @classmethod
    def bound_hits(cls, value):
        if any(step.limit > 5 for step in value):
            raise ValueError("Each workflow tool is limited to five hits")
        return value


class Revision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, le=2147483646, strict=True)


class EvidenceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["evidence_ready", "partial"]
    source_ids: list[str]
    evidence_gaps: list[str]


class AttemptView(BaseModel):
    step_index: int
    attempt: int
    response: ToolResponse


class ExecutionView(BaseModel):
    workflow: WorkflowView
    plan: ExecutionPlan
    next_step: int
    attempts: int
    lease_expires: datetime | None
    summary: EvidenceSummary | None
    results: list[AttemptView]


class Claim(BaseModel):
    token: UUID
    step: Step
