# Evaluation ground truth — #47

`backend/evaluation/ground_truth.json` is the reviewable, versioned 1.0.0 fixture corpus.
All content is repository-authored synthetic material: no customer data, copied external
text, credentials, or paid model output. Contract rename examples reuse the repository's
synthetic customer v1/v2 examples. Labels are explicit expectations, not generated from
retrieval output. The pinned oasdiff 1.37.0 verifies contract expectations.

## Reproduce from the repository root

Use the backend development environment described in the README, then:

```powershell
cd backend
python -m evaluation.dataset
python install_oasdiff.py
python -m pytest tests/test_evaluation_dataset.py -q
```

The manifest command validates schema, provenance, citation identities, source references,
metadata scope, and split membership, then prints counts. Tests also validate OpenAPI
specifications and compare all six contract scenarios with the real pinned engine.
Installation may download the pinned tool; execution is offline and needs no model key.
The existing PostgreSQL CI tests verify that actual ingestion reproduces every expected
source UUID and exact snippet/offset. To run that check locally, use the README's disposable
`TEST_DATABASE_URL` setup and run:

```powershell
python -m pytest tests/test_database_integration.py -k evaluation_citation -q
```

## Corpus and labels

| Set | Development | Held out |
| --- | --- | --- |
| Retrieval cases | 5 customer migration/pagination/retry cases | 3 billing currency/idempotency/refund cases |
| Contract cases | endpoint removal, newly required input, optional input, unchanged | documentation-only change, apparent response rename |

Ten short documents fit one ingestion chunk each. Documents record their project UUID,
provider, API version, type, source reference, normalized text, split, and persisted chunk
UUID. UUIDs follow ingestion's current chunking version and content hash. Changing text,
metadata, project or chunking requires updating citation labels deliberately.

Each retrieval case separates the natural-language question from the explicit bounded
search request. `relevant_source_ids` is an unordered set of defensible source citations;
`rationale` explains why. Both members of an ambiguous case's set are relevant, not mutually
exclusive alternative answers. Negative cases have an empty set: no supplied document
answers the question. An empty gold set does not imply hybrid search will return no
candidates—nearest-neighbor retrieval can return irrelevant documents. Task #48 must report
negative-case behavior separately and must not divide recall by zero.

The corpus includes v1, other-provider, other-project, and document-type distractors.
An evaluation should ingest the full corpus so metadata isolation is exercised. Relevant
source labels cannot cross project/version/provider/type filters or development/held-out
splits. Citation metadata is preserved, and raw source text remains evidence, not authority.

Contract labels contain exact rule ID, severity, method and path tuples; an empty list
means no normalized changelog. The apparent rename deliberately expects removal plus
addition rather than inferred semantic equivalence. Human explanations accompany each.

## Holdout policy and limitations

Use development cases for retrieval tuning. Reserve held-out case labels for final
assessment; do not change labels to make a failed score pass. Retrieval documents are
split by topic; contract splits are by scenario, with shared synthetic API structure.
These public repository fixtures are a regression holdout, not a secret or statistically
independent benchmark. Report development and held-out results separately. Any correction
needs review, an explained rationale, and a dataset-version bump; do not silently regenerate
gold labels from the algorithm under test.

This checkpoint validates fixture integrity and reproducible contract facts. It does not
claim Recall@5 >=80%, semantic embedding quality, or broad API coverage. The small curated
corpus omits many real-world patterns and long multi-chunk documents. The default embedding
provider remains synthetic. Scoring commands, per-case evaluation reports and deliberate
retrieval-regression gates belong to #48; no live-provider evaluation is triggered here.
