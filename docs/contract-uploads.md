# Contract upload API checkpoint

Feature #2 completes the project and immutable contract-version API. The React Contracts screen connects to these endpoints; see the Step 2 browser walkthrough in [MVP checkpoints](mvp-steps.md). Comparison and analysis are not implemented by this checkpoint.

## Try it

Start the local Compose stack and apply migrations as described in the README. Use <http://localhost:8000/docs> to create a project, then expand `POST /api/projects/{project_id}/contracts` and provide the project UUID, a version label, and the raw OpenAPI document. For JSON, paste the object directly rather than wrapping it in another object. The API accepts a raw request body, not multipart form data.

From the repository root (use `curl.exe` on Windows):

```sh
curl -X POST http://localhost:8000/api/projects \
  -H 'Content-Type: application/json' -d '{"name":"Customer migration"}'

# Replace PROJECT_ID with the returned UUID.
curl -X POST 'http://localhost:8000/api/projects/PROJECT_ID/contracts?version=v1&source_name=customer-v1.json' \
  -H 'Content-Type: application/json' --data-binary @docs/examples/customer-v1.json
curl -X POST 'http://localhost:8000/api/projects/PROJECT_ID/contracts?version=v2&source_name=customer-v2.yaml' \
  -H 'Content-Type: application/yaml' --data-binary @docs/examples/customer-v2.yaml

curl 'http://localhost:8000/api/projects/PROJECT_ID/contracts?limit=20&offset=0'
curl 'http://localhost:8000/api/projects/PROJECT_ID/contracts/CONTRACT_ID'
```

Each upload returns **201** with UUID, project ID, version label, OpenAPI version, source name and creation timestamp. Listing returns metadata only, newest first with a UUID tie-breaker; details include the normalized specification. The uploaded document's `info.version` is independent of the project version label. List limits are 1–100, default 20; offset is 0–100,000.

Upload the same label twice in the same project to see **409**. The existing specification stays unchanged. The same label is allowed in another project. Reading a contract under a different project returns **404**. There are no update/delete contract endpoints in this checkpoint.

## Accepted input and limits

- One UTF-8 JSON or safe YAML object, at most **1 MiB**, received within **10 seconds**. Supported media types: `application/json`, `application/yaml`, `application/x-yaml`, `text/yaml`. Compression and multipart bodies are rejected.
- OpenAPI **3.0.x, 3.1.x and 3.2.x**, validated by the locked `openapi-spec-validator` dependency. A valid root must contain the fields required by the relevant OpenAPI specification.
- At most **40 levels** and **20,000 nodes** (object keys count as nodes). Duplicate keys, aliases, merge keys, multiple YAML documents, custom object tags, non-string keys, dates, non-finite numbers, null characters and invalid Unicode are rejected. Quote YAML response codes and dates intended as strings.
- Only existing local `#/` JSON Pointer references; `~0` and `~1` escapes are supported, percent-encoded pointers are not. Recursive local schema references are supported within validation limits. External references, schema `$id`, dynamic/recursive reference keywords and custom dialects are intentionally unsupported. Informational URLs in servers or external documentation are data and are never fetched.
- A required trimmed version label of 1–100 characters. Optional `source_name` is a plain ASCII filename ending in `.json`, `.yaml` or `.yml`, at most 255 characters; path separators, `..`, URL escapes and drive prefixes are rejected. The name is display metadata, never a storage path. Specifications are stored as JSONB in PostgreSQL; uploaded source files are not written to disk.

Validation runs in a child process with no inherited credentials or proxy settings, a **10-second wall-clock timeout**, and a maximum of two simultaneous validation jobs per API process. Linux additionally applies 256 MiB address-space and 5-second CPU limits. Other platforms use byte/tree/concurrency/wall-clock bounds. Exhausted capacity returns 503 rather than building an unbounded queue. The validator's URL/file resolver handlers are disabled.

## Failure behavior

| Status | Meaning |
| --- | --- |
| 404 | Project or project-scoped contract not found |
| 408 | Upload body read timed out |
| 409 | Version label already exists in the project |
| 413 | Body exceeds 1 MiB |
| 415 | Unsupported content type or compression |
| 422 | Invalid metadata/document/schema/reference or validation resource limit |
| 503 | Storage unavailable, validator unavailable, or validation capacity exhausted |

Document errors include a bounded code/message/path when available, without echoing the document. Invalid documents create no records. Database constraints enforce uniqueness even for concurrent submissions, and successful responses are sent only after commit. Connection details are not exposed in errors.

This remains a loopback-only, single-user learning application. Project-scoped lookup is data isolation, not authentication. Public hosting requires the separate authentication and deployment controls.

## Validation

The backend suite includes JSON/YAML and OpenAPI-version cases, duplicate keys, unsafe YAML, external/local references, depth/node/body limits, metadata/path validation, validator failures and concurrency bounds. PostgreSQL integration tests exercise JSON/YAML persistence, list/detail isolation, duplicate races and rollback. CI runs these against a disposable database and still runs the existing browser workflow and security checks.
