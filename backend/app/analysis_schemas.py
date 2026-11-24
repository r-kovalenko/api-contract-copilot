from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.code_search import SearchRequest, SearchResult
from app.comparison import ContractChange
from app.knowledge_schemas import KnowledgeResult
from app.model_provider import Claim


class AnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comparison_id: UUID
    change_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    repository: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")
    code_query: str = Field(min_length=1, max_length=200)
    knowledge_query: str = Field(min_length=1, max_length=200)
    provider: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("code_query", "knowledge_query", "provider")
    @classmethod
    def plain_text(cls, value: str | None) -> str | None:
        if value is not None:
            SearchRequest(repository="validation", query=value)
            if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
                raise ValueError("Invalid Unicode")
        return value


class AffectedFile(BaseModel):
    path: str
    line: int
    source_id: str


class Recommendation(BaseModel):
    text: str
    source_ids: list[str]


class ImpactReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    status: Literal["evidence_ready", "partial"]
    severity: Literal["breaking", "potentially_breaking", "non_breaking"]
    summary: str
    change: ContractChange
    api_version: str
    code: SearchResult | None
    knowledge: KnowledgeResult | None
    affected_files: list[AffectedFile]
    recommendations: list[Recommendation]
    model_observations: list[Claim]
    model_status: Literal["offline", "validated_quotes", "unavailable", "rejected"]
    evidence_gaps: list[str]


class AnalysisSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    comparison_id: UUID
    change_id: str
    created_at: datetime


class AnalysisView(AnalysisSummary):
    request: AnalysisCreate
    report: ImpactReport
