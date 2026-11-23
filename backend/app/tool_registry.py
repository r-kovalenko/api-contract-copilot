"""Application-owned, read-only tool dispatch; payloads never select implementations."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from app.code_search import RepositorySearch, SearchError, SearchRequest, SearchResult


class SearchCodeCall(SearchRequest):
    operation: Literal["search_code"]


class ToolEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["ok"] = "ok"
    operation: Literal["search_code"] = "search_code"
    result: SearchResult


class ToolRejected(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["rejected"] = "rejected"
    code: Literal["invalid_request", "unknown_repository", "unsafe_scope"]


class ToolUnavailable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["unavailable"] = "unavailable"
    code: Literal[
        "invalid_repository",
        "repository_unavailable",
        "repository_changed",
        "corpus_limit",
        "busy",
        "timeout",
        "engine_unavailable",
        "engine_failed",
        "output_limit",
        "invalid_output",
    ]


ToolResponse = Annotated[
    ToolEvidence | ToolRejected | ToolUnavailable, Field(discriminator="status")
]
response_adapter = TypeAdapter(ToolResponse)


class ToolRegistry:
    """Construct per authorized repository set; never share broader access by default."""

    def __init__(self, search: RepositorySearch):
        self._search = search

    def invoke(self, payload: object) -> ToolResponse:
        try:
            call = SearchCodeCall.model_validate(payload)
        except ValidationError:
            # Do not echo raw validation inputs, paths, or model-provided instructions.
            return ToolRejected(code="invalid_request")
        request = SearchRequest.model_validate(call.model_dump(exclude={"operation"}))
        try:
            return ToolEvidence(result=self._search.search(request))
        except SearchError as error:
            status = (
                "rejected"
                if error.code in {"unknown_repository", "unsafe_scope"}
                else "unavailable"
            )
            # Only known safe codes cross the boundary. Unexpected failures propagate
            # to the host, never masquerading as successful or missing evidence.
            return response_adapter.validate_python({"status": status, "code": error.code})
