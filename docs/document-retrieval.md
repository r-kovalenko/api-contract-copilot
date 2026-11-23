# Filtered document retrieval — #42

After [ingesting documentation](document-ingestion.md), apply migration `0004_document_search` with `docker compose exec backend python -m alembic upgrade head`. It adds a stored PostgreSQL `tsvector` and GIN index to every existing and future chunk. Downgrading removes the index/vector without changing source text or citation IDs.

## Try it

Using the `$project` from the ingestion walkthrough:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/projects/$($project.id)/knowledge/search?query=full_name&api_version=v2&provider=customer-demo&document_type=migration&limit=5"
```

GET `/api/projects/{project_id}/knowledge/search` requires `query` and `api_version`. Optional `provider` and `document_type` filters are exact metadata matches. The query is 1–200 characters; limit defaults to 5 and is bounded to 1–20. Invalid fields return 422, missing projects return 404, and storage failures return a sanitized 503 rather than empty evidence.

## Retrieval semantics

Project and API-version predicates always apply before the final ordering and limit. Optional filters apply in the same parameterized query. PostgreSQL `plainto_tsquery` with the `simple` dictionary tokenizes text case-insensitively and requires all query tokens; punctuation is not an executable query language. It performs no stemming, embeddings, fuzzy match or semantic inference. Queries with no searchable tokens return no hits. Snake-case identifiers follow PostgreSQL tokenization, not exact code-search semantics.

Rank is `ts_rank_cd`, descending, with chunk UUID as deterministic tie-breaker. Scores are lexical ranking values, not probabilities or evidence of impact. Fetching one extra row sets `truncated` when additional matching chunks exist. No-match is an explicit successful empty result, not proof that documentation supports a conclusion. SQL execution uses a transaction-local three-second statement timeout; database pool/connection limits still apply separately.

Each hit returns its persisted chunk `source_id`, document ID, provider/version/type/source metadata, original character offsets and full stored chunk as `snippet` (at most 2,000 characters). No HTML highlighting is generated. Source text, links and instructions remain untrusted evidence. At most 20 hits are returned; references must be validated against these supplied IDs in future report generation. Results do not synthesize facts or citations.

## Tool integration

Trusted host code constructs `KnowledgeSearch(engine, authorized_project_id)` and passes it as the optional second argument to `ToolRegistry(repository_search, knowledge_search)`. Call:

```json
{"operation":"search_knowledge","query":"customer","api_version":"v2","limit":5}
```

The project is bound by the host, never chosen by tool arguments; supplying `project_id` is rejected. The registry returns `ok` with operation `search_knowledge` and typed results, `rejected` for invalid calls/unknown projects, or `unavailable` for missing configuration or storage failures. Request/response JSON schemas are available through the registry's `call_adapter` and `response_adapter`. Existing `search_code` behavior remains supported.

The HTTP API is still a local single-user preview, not an authorization system. A deployment must bind projects to authenticated principals before exposing it. Hybrid retrieval, embeddings and impact analysis remain later tasks. Ordinary CI uses synthetic documents and real disposable PostgreSQL, with no model calls or credentials.
