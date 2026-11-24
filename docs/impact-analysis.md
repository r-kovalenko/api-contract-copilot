# Saved impact-analysis API — #38

The API combines one saved deterministic contract change, exact code search and candidate-version documentation into an immutable evidence report. Severity is copied from oasdiff; potentially affected files are only real code hits. Recommendations are bounded application templates citing the change/matches. Model text cannot change those facts. This is an API checkpoint; React analysis-start and report screens remain #39/#40.

## Run the offline demo

Rebuild and apply migrations:

```powershell
docker compose up -d --build backend
docker compose exec backend python -m alembic upgrade head
$project = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/projects -ContentType application/json -Body '{"name":"Impact demo"}'
$base = "http://localhost:8000/api/projects/$($project.id)"
$v1 = Invoke-RestMethod -Method Post -Uri "$base/contracts?version=v1" -ContentType application/json -InFile docs/examples/customer-v1.json
$v2 = Invoke-RestMethod -Method Post -Uri "$base/contracts?version=v2" -ContentType application/yaml -InFile docs/examples/customer-v2.yaml
$comparison = Invoke-RestMethod -Method Post -Uri "$base/comparisons" -ContentType application/json -Body (@{baseline_id=$v1.id; candidate_id=$v2.id} | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "$base/documents?provider=demo&api_version=v2&document_type=migration&source_ref=v2.md" -ContentType text/plain -Body 'Replace full_name with display_name in customer integrations.'
$inputData = @{comparison_id=$comparison.id; change_id=$comparison.result.changes[0].id; code_query='full_name'; knowledge_query='full_name'; provider='demo'}
$analysis = Invoke-RestMethod -Method Post -Uri "$base/analyses" -ContentType application/json -Body ($inputData | ConvertTo-Json)
$analysis.report | ConvertTo-Json -Depth 20
Invoke-RestMethod -Uri "$base/analyses/$($analysis.id)"
```

The default fake provider needs no API key and reports that no model analysis was performed. With no repository selected the report is explicitly partial (`code_repository_not_selected`), not a fabricated empty impact claim. Documentation is filtered to the candidate contract's saved version label (`v2` here), with optional exact provider filter. No remote repository/document URL is fetched.

## Add code evidence locally

Backend-only `COPILOT_REPOSITORIES` is a JSON object mapping project UUIDs to repository aliases and absolute paths. For example, in the host PowerShell process that starts the backend:

```powershell
$env:COPILOT_REPOSITORIES = (@{ "$($project.id)" = @{ consumer = 'C:/Projects/api-consumer-demo' } } | ConvertTo-Json -Compress)
```

Restart the backend in that environment and add `repository='consumer'` to the POST body. The file path is trusted server configuration, never an API field. Compose does not automatically forward this variable or mount repositories: configure an explicit read-only mount and container-local absolute path before using code search in Docker. Use only synthetic/sanitized stable local checkouts; existing [search limits](code-search.md) apply. The real PostgreSQL CI walkthrough supplies a temporary synthetic repository and verifies exact matches through the API.

## Report contract and persistence

POST `/api/projects/{project_id}/analyses` accepts comparison/change IDs, literal `code_query`, plain `knowledge_query`, optional repository alias and optional documentation provider. Queries are 1–200 nonblank single-line characters. Unknown fields/paths are rejected. Unknown repository aliases return 422; wrong-project or missing comparison/change returns 404. GET the collection returns paginated metadata; GET `/{analysis_id}` returns the saved request and report. All reads are project-scoped. This remains a local unauthenticated single-user preview.

`analysis_runs` stores a UUID, project/comparison/change references, original request, report snapshot and timestamp. A composite foreign key binds the comparison to the project. Stored evidence includes the selected change, full bounded search results with source IDs/paths/coordinates/hashes and document snippets. Later code edits do not rewrite prior reports. Creation commits before returning 201; failed commits roll back. Each successful POST creates a separate run; no automatic retries or deduplication. Retention, session orchestration and resumability are later work.

Status `partial` means a source/model gap was recorded; `evidence_ready` means this bounded gathering completed without a detected gap, not proof of complete impact coverage. No matches, unavailable sources and truncation remain distinct. Exact matches identify potential impact only; semantic/dynamic usages may be missed. Model failure preserves deterministic evidence in a partial report. Storage failure returns sanitized 503.

Model observations are validated twice: every citation must be in the supplied evidence, and each observation must be a verbatim substring of every cited excerpt. Unsupported paraphrases are omitted as `unsupported_model_claim_omitted`; unknown citations reject the model contribution. Quotation matching proves provenance, not truth or relevance. Quotes and retrieved instructions remain untrusted display data, never commands. Recommendations are generic review/test actions, not an inferred migration plan.

At most five code hits and five documentation chunks are gathered. The model sees at most the first 500 UTF-8 bytes of each source (the report keeps full source evidence); this is intentionally conservative. Existing model budgets and explicit live opt-in apply. The provider's arbitrary gap prose is summarized as a gap flag rather than promoted to application advice. The fake is identified as offline. No live provider is required or called in CI.

Creation is limited to two in-flight runs per process. Bodies are capped at 16 KiB before parsing, with the existing ten-second upload deadline. Code search, SQL and model calls retain their individual deadlines; there is no global ten-second end-to-end promise. Read connections are released before external model calls. Host filesystems must remain trusted/local; a stalled filesystem read is not forcibly interruptible. No writes to consumer code, task trackers or external tools are performed.

## Validation

CI exercises real PostgreSQL migration round trips/schema agreement, upload/comparison/report creation, project isolation, persistent snapshots, failed commits, empty/failed sources, unknown citations, unsupported claims and untrusted source instructions using synthetic fixtures and fake providers. The new local boundary tests are `backend/tests/test_analyses.py`; full integration cases are in `test_database_integration.py`.
