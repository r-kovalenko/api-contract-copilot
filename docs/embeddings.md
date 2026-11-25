# Document embedding lifecycle

Task #45 adds explicit, atomic document indexing. Hybrid/vector ranking remains #46;
existing keyword retrieval and saved impact reports are unchanged.

Apply `python -m alembic upgrade head` from `backend` (or the README Compose command).
Migration `0006_chunk_embeddings` stores one vector per immutable document chunk:
`chunk_id` (primary key and cascading FK), `model`, `dimensions`, pgvector `embedding`,
and `created_at`. SQL checks enforce dimensions 1–2000 and vector length agreement.
Project ownership is inherited through chunk → document; all operations first verify
that the document belongs to the requested project. Downgrade removes only embeddings.

## Try the offline checkpoint

After creating a project and ingesting a text/Markdown document using
[document ingestion](document-ingestion.md), use its returned IDs:

```powershell
$projectId = 'replace-with-project-uuid'
$documentId = 'replace-with-document-uuid'
$url = "http://localhost:8000/api/projects/$projectId/documents/$documentId/embeddings"
Invoke-RestMethod $url
Invoke-RestMethod $url -Method Post
Invoke-RestMethod $url
```

Before indexing, `ready` is false and `embedded_chunks` is zero. After indexing,
`ready` is true and all chunks have vectors with `model: fake-sha256-v1`, `dimensions: 32`.
The fake is deterministic test data, **not semantic embeddings**. There are no paid calls,
keys, remote URLs, or live adapters in this checkpoint. Ingestion itself never indexes.

## Replacement and recovery

The typed asynchronous provider interface declares a versioned model identifier and
its dimensions. A model identifier must change whenever its embedding behavior changes.
Repeated indexing with the same model/dimensions reuses a complete snapshot. A different
model or dimension returns HTTP 409 until the caller explicitly uses `?reindex=true`.
The API uses the server-selected fake; clients cannot select arbitrary models/endpoints.

The service locks the project-scoped document row, computes bounded batches, validates
all vectors, and replaces them in one transaction. Previous vectors remain visible until
commit. Failures roll back; retry the same request after recovery. A process crash leaves
no partial committed generation. Concurrent indexing serializes on the document lock;
a lock/database timeout returns a retryable 503. No background jobs or automatic retries.

Limits: at most 132 chunks, 2000 characters per chunk, 16 chunks per batch, 5 seconds per
provider batch, and 30 seconds total provider time. Async provider implementations must
honor cancellation and avoid blocking I/O. The database pool and query/lock timeout also
bound requests. Output count, dimensions, finite numeric values, magnitude, and nonzero
vectors are validated before writes. Provider errors return generic 503 messages without
provider text or document content. API responses include metadata/counts, never vectors.

The SQL binding uses pgvector's [text vector format](https://github.com/pgvector/pgvector#storing)
with bound parameters; no new Python dependency is needed. Retrieval indexes and ranking,
semantic model quality, background reindex jobs, and authenticated multi-user access are
outside this checkpoint. Keep this single-user preview local with synthetic data.

## Validation

Unit tests cover deterministic batches, vector/input validation, and cancellation on timeout.
PostgreSQL CI covers migration/schema parity, stored vectors, duplicate ingestion/indexing,
model/dimension replacement, wrong-project access, concurrent indexing, failed later batches,
commit rollback, retry, and loading saved state through a new client.
