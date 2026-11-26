"""Bounded local API contracts; callers cannot forge assistant messages or tool runs."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

State = Literal["running", "waiting_for_user", "waiting_for_approval", "completed", "failed"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*")
    @classmethod
    def plain_text(cls, value):
        if isinstance(value, str) and any(
            (ord(c) < 32 and c not in "\n\t") or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF
            for c in value
        ):
            raise ValueError("Text contains unsupported control characters")
        return value


class SessionCreate(Input):
    title: str = Field(min_length=1, max_length=200)
    analysis_id: UUID | None = None


class MessageCreate(Input):
    request_id: UUID
    content: str = Field(min_length=1, max_length=4000)


class Transition(Input):
    expected_revision: int = Field(ge=0, le=2147483646, strict=True)
    status: State
    reason: str = Field(min_length=1, max_length=1000)


class SessionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    title: str
    created_at: datetime


class MessageView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    request_id: UUID
    sequence: int
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime


class WorkflowView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    session_id: UUID
    project_id: UUID
    analysis_id: UUID | None
    status: State
    revision: int
    reason: str
    updated_at: datetime


class ToolRunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    operation: Literal["search_code", "search_knowledge"]
    status: Literal["ok", "rejected", "unavailable"]
    created_at: datetime
