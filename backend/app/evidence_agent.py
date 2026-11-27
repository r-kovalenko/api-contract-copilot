"""A pure evidence specialist: typed input/output, no registry or other agent access."""

from app.orchestration_schemas import EvidenceSummary
from app.tool_registry import ToolResponse


def summarize_evidence(results: list[ToolResponse]) -> EvidenceSummary:
    sources = []
    gaps = []
    for index, response in enumerate(results):
        if response.status != "ok":
            gaps.append(f"step_{index}:{response.code}")
            continue
        evidence = response.result
        if not evidence.hits:
            gaps.append(f"step_{index}:no_matches")
        if evidence.truncated:
            gaps.append(f"step_{index}:truncated")
        if response.operation == "search_code":
            sources.extend(hit.id for hit in evidence.hits)
            if evidence.skipped_entries or any(hit.snippet_truncated for hit in evidence.hits):
                gaps.append(f"step_{index}:incomplete_code_coverage")
        else:
            sources.extend(str(hit.source_id) for hit in evidence.hits)
    return EvidenceSummary(
        status="partial" if gaps else "evidence_ready",
        source_ids=list(dict.fromkeys(sources)),
        evidence_gaps=gaps,
    )
