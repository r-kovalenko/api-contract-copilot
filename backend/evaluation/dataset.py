"""Typed fixture manifest and cross-reference validation for offline evaluation."""

import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.document_service import CHUNK_SIZE, CHUNKING_VERSION, DocumentMetadata
from app.knowledge_schemas import KnowledgeRequest

Split = Literal["development", "held_out"]


class FixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentFixture(FixtureModel):
    key: str = Field(min_length=1)
    split: Split
    project_id: UUID
    metadata: DocumentMetadata
    text: str = Field(min_length=1, max_length=CHUNK_SIZE)
    source_id: UUID

    @model_validator(mode="after")
    def stable_citation(self):
        if not self.text.strip() or "\r" in self.text or self.text.startswith("\ufeff"):
            raise ValueError("Fixture text must be nonempty normalized UTF-8")
        doc_id = uuid5(self.project_id, json.dumps(self.metadata.model_dump(), sort_keys=True))
        digest = hashlib.sha256(self.text.encode()).hexdigest()
        if self.source_id != uuid5(doc_id, f"{CHUNKING_VERSION}:{digest}:0"):
            raise ValueError("Source ID does not match immutable ingestion identity")
        return self


class RetrievalCase(FixtureModel):
    id: str = Field(min_length=1)
    split: Split
    kind: Literal["positive", "negative", "ambiguous"]
    project_id: UUID
    question: str = Field(min_length=1)
    request: KnowledgeRequest
    relevant_source_ids: list[UUID]
    rationale: str = Field(min_length=1)


class ExpectedChange(FixtureModel):
    rule_id: str
    severity: Literal["breaking", "potentially_breaking", "non_breaking"]
    operation: str
    path: str


class ContractCase(FixtureModel):
    id: str = Field(min_length=1)
    split: Split
    baseline: dict
    candidate: dict
    expected_changes: list[ExpectedChange]
    rationale: str = Field(min_length=1)


class Dataset(FixtureModel):
    schema_version: Literal[1]
    dataset_version: Literal["1.0.0"]
    provenance: Literal["Repository-authored synthetic data; no customer or external content"]
    oasdiff_version: Literal["1.37.0"]
    documents: list[DocumentFixture] = Field(min_length=1)
    retrieval_cases: list[RetrievalCase] = Field(min_length=1)
    contract_cases: list[ContractCase] = Field(min_length=1)

    @model_validator(mode="after")
    def references(self):
        def unique(values):
            if len(values) != len(set(values)):
                raise ValueError("Duplicate fixture identifier")

        unique([d.key for d in self.documents])
        unique([d.source_id for d in self.documents])
        unique([c.id for c in self.retrieval_cases + self.contract_cases])
        sources = {d.source_id: d for d in self.documents}
        for case in self.retrieval_cases:
            unique(case.relevant_source_ids)
            if (case.kind == "negative") != (not case.relevant_source_ids):
                raise ValueError("Only negative cases have no relevant sources")
            if case.kind == "ambiguous" and len(case.relevant_source_ids) < 2:
                raise ValueError("Ambiguous cases require multiple defensible sources")
            for source_id in case.relevant_source_ids:
                doc = sources.get(source_id)
                if doc is None:
                    raise ValueError("Unknown expected source")
                req, meta = case.request, doc.metadata
                if (
                    doc.split != case.split
                    or doc.project_id != case.project_id
                    or meta.api_version != req.api_version
                    or req.provider is not None
                    and meta.provider != req.provider
                    or req.document_type is not None
                    and meta.document_type != req.document_type
                ):
                    raise ValueError("Expected source violates split or metadata scope")
        for cases in (self.retrieval_cases, self.contract_cases):
            if {c.split for c in cases} != {"development", "held_out"}:
                raise ValueError("Both development and held-out cases are required")
        return self


def load_dataset() -> Dataset:
    return Dataset.model_validate_json(
        Path(__file__).with_name("ground_truth.json").read_text(encoding="utf-8")
    )


if __name__ == "__main__":
    dataset = load_dataset()
    print(
        f"Dataset {dataset.dataset_version}: {len(dataset.documents)} documents, "
        f"{len(dataset.retrieval_cases)} retrieval cases, "
        f"{len(dataset.contract_cases)} contract cases"
    )
