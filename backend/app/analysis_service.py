"""Evidence-first reports: model text cannot override facts or invent affected files."""

import asyncio
import json
import os
import threading
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import Engine

from app.analysis_schemas import (
    AffectedFile,
    AnalysisCreate,
    AnalysisView,
    ImpactReport,
    Recommendation,
)
from app.code_search import RepositorySearch, SearchRequest
from app.comparison import ComparisonResult
from app.db.analyses import insert_analysis
from app.db.comparisons import get_comparison
from app.db.repositories import get_contract
from app.db.session import session_scope
from app.knowledge import KnowledgeSearch
from app.model_provider import (
    Evidence,
    FakeProvider,
    GenerationRequest,
    ModelProvider,
    ProviderError,
    provider_from_environment,
    validate_answer,
)
from app.tool_registry import ToolRegistry

_slots = threading.BoundedSemaphore(2)


class AnalysisError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def project_repositories(project_id: UUID) -> dict[str, Path]:
    """Trusted server configuration, keyed by project; never paths from API requests."""
    try:
        raw = os.environ.get("COPILOT_REPOSITORIES", "{}")
        if len(raw.encode("utf-8")) > 16384:
            raise ValueError
        mapping = json.loads(raw)
        if not isinstance(mapping, dict):
            raise ValueError
        selected = mapping.get(str(project_id), {})
        if not isinstance(selected, dict) or len(selected) > 20:
            raise ValueError
        result = {}
        for name, path in selected.items():
            SearchRequest(repository=name, query="validate")
            if not isinstance(path, str) or not Path(path).is_absolute():
                raise ValueError
            result[name] = Path(path)
        return result
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise AnalysisError("invalid_repository_configuration") from None


def create_analysis(
    engine: Engine,
    project_id: UUID,
    data: AnalysisCreate,
    repositories: dict[str, Path],
    provider: ModelProvider | None = None,
) -> AnalysisView:
    if data.repository is not None and data.repository not in repositories:
        raise AnalysisError("unknown_repository")
    if not _slots.acquire(blocking=False):
        raise AnalysisError("busy")
    try:
        return _create(engine, project_id, data, repositories, provider)
    finally:
        _slots.release()


def _create(engine, project_id, data, repositories, provider):
    with session_scope(engine) as session:
        comparison = get_comparison(session, project_id, data.comparison_id)
        if comparison is None:
            raise AnalysisError("not_found")
        parsed = ComparisonResult.model_validate(comparison.result)
        change = next((item for item in parsed.changes if item.id == data.change_id), None)
        candidate = get_contract(
            session, project_id=project_id, contract_id=comparison.candidate_id
        )
        if change is None or candidate is None:
            raise AnalysisError("not_found")
        version = candidate.version
    # Release the read transaction/connection before tools or external model calls.
    registry = ToolRegistry(RepositorySearch(repositories), KnowledgeSearch(engine, project_id))
    gaps = []
    code = None
    knowledge = None
    if data.repository is None:
        gaps.append("code_repository_not_selected")
    else:
        response = registry.invoke(
            {
                "operation": "search_code",
                "repository": data.repository,
                "query": data.code_query,
                "limit": 5,
            }
        )
        if response.status == "ok":
            code = response.result
            if not code.hits:
                gaps.append("no_exact_code_matches")
            if (
                code.truncated
                or code.skipped_entries
                or any(h.snippet_truncated for h in code.hits)
            ):
                gaps.append("code_coverage_incomplete")
        else:
            gaps.append(f"code_{response.code}")
    response = registry.invoke(
        {
            "operation": "search_knowledge",
            "query": data.knowledge_query,
            "api_version": version,
            "provider": data.provider,
            "limit": 5,
        }
    )
    if response.status == "ok":
        knowledge = response.result
        if not knowledge.hits:
            gaps.append("no_documentation_matches")
        if knowledge.truncated:
            gaps.append("documentation_results_truncated")
    else:
        gaps.append(f"documentation_{response.code}")
    sources = {change.id: change.summary}
    if code:
        sources.update({hit.id: hit.snippet for hit in code.hits})
    if knowledge:
        sources.update({str(hit.source_id): hit.snippet for hit in knowledge.hits})
    observations = []
    model_status = "unavailable"
    try:
        configured = provider if provider is not None else provider_from_environment()
        # Bound model context independently from the full persisted evidence snapshot.
        evidence = []
        for source_id, text in sources.items():
            excerpt = text.encode("utf-8")[:500].decode("utf-8", errors="ignore")
            evidence.append(Evidence(source_id=source_id, text=excerpt))
        model_request = GenerationRequest(
            question="Return short verbatim quotations relevant to the selected change. "
            "Do not paraphrase or invent recommendations. Report absent support as gaps.",
            evidence=evidence,
        )
        answer = asyncio.run(configured.generate(model_request))
        answer = validate_answer(answer.model_dump_json(), model_request)
        supplied = {item.source_id: item.text for item in evidence}
        for claim in answer.claims:
            if claim.text.strip() and all(claim.text in supplied[sid] for sid in claim.source_ids):
                observations.append(claim)
            else:
                gaps.append("unsupported_model_claim_omitted")
        model_status = "offline" if isinstance(configured, FakeProvider) else "validated_quotes"
        if model_status == "offline":
            gaps.append("offline_provider_no_model_analysis")
        if answer.evidence_gaps:
            # Do not present arbitrary model text as an application-owned recommendation.
            gaps.append("model_reported_evidence_gaps")
    except (ProviderError, ValidationError):
        model_status = "rejected"
        gaps.append("model_output_unavailable_or_rejected")
    affected = (
        [AffectedFile(path=h.path, line=h.line, source_id=h.id) for h in code.hits] if code else []
    )
    recommendations = [
        Recommendation(
            text="Review this contract change and test the consumer against the candidate version.",
            source_ids=[change.id],
        )
    ]
    if affected:
        recommendations.append(
            Recommendation(
                text="Inspect the exact matching call sites; "
                "a textual match alone does not prove impact.",
                source_ids=[item.source_id for item in affected],
            )
        )
    report = ImpactReport(
        status="partial" if gaps else "evidence_ready",
        severity=change.severity,
        summary=f"{change.summary} Found {len(affected)} potentially affected code matches "
        f"and {len(knowledge.hits) if knowledge else 0} documentation chunks.",
        change=change,
        api_version=version,
        code=code,
        knowledge=knowledge,
        affected_files=affected,
        recommendations=recommendations,
        model_observations=observations,
        model_status=model_status,
        evidence_gaps=list(dict.fromkeys(gaps)),
    )
    # Validate all persisted report citations against gathered evidence, even for offline output.
    if any(sid not in sources for rec in report.recommendations for sid in rec.source_ids):
        raise AnalysisError("invalid_report")
    with session_scope(engine) as session:
        row = insert_analysis(
            session,
            project_id=project_id,
            comparison_id=data.comparison_id,
            change_id=data.change_id,
            request=data.model_dump(mode="json"),
            report=report.model_dump(mode="json"),
        )
        view = AnalysisView.model_validate(row)
    return view
