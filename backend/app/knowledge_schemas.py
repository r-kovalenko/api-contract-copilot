"""Typed evidence contract shared by the API and application-owned tool registry."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)
    mode: Literal["keyword", "hybrid"] = "keyword"
    query: str = Field(min_length=1, max_length=200)
    api_version: str = Field(min_length=1, max_length=100)
    provider: str | None = Field(default=None, min_length=1, max_length=100)
    document_type: Literal["reference", "migration", "changelog", "guide"] | None = None
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("query", "api_version", "provider")
    @classmethod
    def plain_text(cls, value: str | None) -> str | None:
        if value is not None and any(
            ord(c) < 32 or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value
        ):
            raise ValueError("Search fields must contain plain text")
        return value


class KnowledgeHit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_id: UUID
    document_id: UUID
    provider: str
    api_version: str
    document_type: str
    source_ref: str
    start_char: int
    end_char: int
    snippet: str = Field(max_length=2000)
    score: float = Field(ge=0, allow_inf_nan=False)


class KnowledgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    project_id: UUID
    query: str
    api_version: str
    hits: list[KnowledgeHit] = Field(max_length=20)
    truncated: bool
    mode: Literal["keyword", "hybrid"] = "keyword"
    embedding_model: str | None = None
