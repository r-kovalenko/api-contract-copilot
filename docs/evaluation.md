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

## Run evaluation and inspect reports (#48)

From `backend`, set `TEST_DATABASE_URL` to an **empty, disposable** PostgreSQL/pgvector
database whose name ends in `_test`, using the same connection format as the README's
test setup. Never use the application database. Then run:

```powershell
python -m evaluation.run --output evaluation-results/report.json
$LASTEXITCODE
Get-Content evaluation-results/report.json
```

The runner refuses existing tables, migrates its empty database, ingests the full synthetic
corpus, indexes it with the explicit offline SHA-256 provider, and runs real keyword and
hybrid searches plus pinned oasdiff comparisons. It removes its application tables and its own Alembic version table afterward
and retains the shared vector extension. A failed setup may require inspecting/recreating
this disposable database; it never bypasses the empty-database check on retry. No model
provider is selected from environment configuration, so live keys cannot enable paid calls.

Exit codes: **0** all gates pass; **1** a completed evaluation detects regression; **2**
setup/storage/validation failure. Operational failures emit a generic error artifact without
connection details. A failed report write also exits nonzero. CI runs the same command before
tests and uploads `evaluation-results/report.json` as the `evaluation-results` artifact for
seven days, including failed evaluations. Existing required CI and security gates remain.

### Metrics and gates

- Retrieval scores the first five returned IDs against each case's relevant set. Recall@5
  is relevant IDs found divided by relevant IDs expected. Missing and unexpected IDs are
  saved per case. Duplicate IDs, more than five hits, and out-of-scope IDs fail validation.
- Macro Recall@5 is reported separately for development/held-out and keyword/hybrid.
  Each positive/ambiguous case and each split/mode aggregate must reach **80%**. Per-case
  gates prevent an average from hiding a regression; with the current one/two-source cases,
  this effectively requires every relevant source. Absent positive cases cannot pass.
- Negative cases have `recall_at_5: null` and are excluded from recall averages. Keyword
  negatives must return no results. Hybrid negatives record the number of returned
  candidates as a diagnostic: cosine retrieval is not an abstention classifier, so those
  candidates alone do not fail the gate. Scope violations and operational errors always fail.
- Contract precision is matching expected tuples divided by actual tuples; coverage is
  matching tuples divided by expected tuples. Multisets detect duplicate findings. Every
  scenario requires exact expected findings, with no missing or unexpected change, and
  records missed breaking changes. Empty expected/actual lists score 1/1; missing all
  expected findings scores 0/0. Empty expected with unexpected output has precision 0,
  coverage 1 and fails. Operational errors always fail, including unchanged cases.

Reports carry schema/dataset/engine/provider versions and a SHA-256 of the validated
serialized dataset. Case IDs and split membership remain visible. Order is deterministic;
reports omit wall-clock timestamps and credentials. Tests inject missing retrieval evidence
and suppress breaking findings in the real database evaluation to prove failed gates.

The hybrid score uses a fake provider and a tiny corpus, so passing demonstrates deterministic
pipeline behavior, not semantic quality or production recall. Dataset 1.0.0 and its labels
remain unchanged. Public held-out cases are regression fixtures, not a blinded benchmark.
