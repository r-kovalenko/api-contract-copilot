# Documentation ingestion — #41

The local single-user API accepts raw UTF-8 text or Markdown and stores immutable documentation with project, provider, API version, document type and source reference. No URLs are fetched, Markdown rendered, HTML executed, files opened by source reference, or model calls made. Links and instruction-like content remain untrusted data. [Filtered full-text retrieval](document-retrieval.md) is available in checkpoint #42; embeddings and the report UI remain future work.

## Try it from PowerShell

Start the application using the README, rebuild the backend, and apply the migration:

```powershell
docker compose up -d --build backend
docker compose exec backend python -m alembic upgrade head
$project = Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/projects -ContentType application/json -Body '{"name":"Documentation demo"}'
$uri = "http://localhost:8000/api/projects/$($project.id)/documents"
$doc = Invoke-RestMethod -Method Post -Uri "${uri}?provider=customer-demo&api_version=v2&document_type=migration&source_ref=migration-v2.md" -ContentType 'text/markdown; charset=utf-8' -Body '# Migration: replace full_name with display_name.'
Invoke-RestMethod -Uri "$uri/$($doc.id)/chunks"
```

Repeat the upload: it returns HTTP 200 and the existing document. First creation returns 201. Change the text under the same metadata: HTTP 409; use a new source reference or API version to preserve old citations. BOM and CRLF/CR are normalized to UTF-8 text with LF before hashing. Other whitespace and Unicode are retained. Media type changes under the same identity also return 409.

GET the collection or document ID for metadata; GET `/{document_id}/chunks` for ordered chunks. Lists use `offset` (default 0) and `limit` (default 20, maximum 100). All lookups require the document's project; wrong-project IDs return 404. This is data isolation, not authentication: the preview remains local and single-user.

## Bounds and citation contract

Uploads allow only `text/plain` and `text/markdown`, no compression or multipart. Bodies are capped at 256 KiB before parsing, including chunked requests, with a ten-second read deadline. Invalid UTF-8, empty/whitespace-only text and control characters except tab/newline return 422; unsupported media returns 415; oversized input returns 413. Metadata is bounded and rejects control characters. Types are `reference`, `migration`, `changelog`, or `guide`.

Chunking version 1 slices normalized text every 2,000 Unicode characters without overlap (at most 132 chunks). This deliberately simple policy can split paragraphs, code fences and words. Offsets are zero-based, start-inclusive/end-exclusive in normalized text, not bytes. Each chunk stores its text and a stable UUID citation ID derived from document identity, content hash, chunking version and start offset. Document identity binds project and all source metadata. Chunk metadata is inherited through its document foreign key; retrieval must join that document and filter the project/version before returning evidence.

The `documents` table stores provenance, normalized SHA-256 and chunking version. `document_chunks` stores ordered citation IDs, offsets and text. One transaction inserts metadata and all chunks; failed commits return no success and roll back. Concurrent identical uploads converge on one document and chunk set. Sources are immutable; no edit/delete API is exposed. Deployments still need authentication, quotas and retention before accepting real data.

## Validation

Run `python -m pytest backend/tests/test_documents.py` for parsing and upload bounds. PostgreSQL tests in `test_database_integration.py` cover persistence, concurrent retries, stable citations, isolation, rollback, migration round trips and ORM/schema agreement. Use only a disposable database as documented in README; CI supplies one automatically.
