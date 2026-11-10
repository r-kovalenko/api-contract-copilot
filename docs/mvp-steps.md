# Demo checkpoints

Work one demoable step at a time and pause for owner review after each step. A checkpoint is ready for review when its tests pass and its local demo is reproducible. This sequence narrows the existing backlog; it does not mark unfinished parent features complete.

| Step | What you can try | Existing work | Completion evidence |
| --- | --- | --- | --- |
| 1 — Project workspace | Create, list and select projects; reload and see saved projects | F01 database foundation; project portion of F02.1 (#29) and F03.1 (#31) | PostgreSQL integration tests, API validation/failure tests, UI checks and local walkthrough |
| 2 — Contract uploads | Add baseline and candidate OpenAPI versions to a selected project | Remaining F02/F03, including #30 and #32 | JSON/YAML validation, bounded parsing, duplicate versions, project isolation and browser upload flow |
| 3 — Contract comparison | Compare two saved versions and inspect breaking changes | V01 and initial V04 | Pinned oasdiff, deterministic scenario fixtures, timeout/error handling and UI change selection |
| 4 — Evidence-backed report | Select a change and see affected demo code, migration documentation and an impact report | V02, R01, V03 and remaining V04; relevant provider/consumer fixtures | Upload-to-report browser test with fake providers; exact file/line evidence and validated citations |

Step 4 is the first end-to-end MVP preview. Migration planning, persisted agent conversations, approval, MCP, richer RAG and observability follow the PRD implementation order after that preview is accepted.

Step 2 backend checkpoint: project-scoped JSON/YAML uploads, schema validation and immutable contract APIs are implemented in feature #2. Use the [API walkthrough](contract-uploads.md) to review them. The React upload and old/new version-selection flow is implemented in #32. Comparison execution remains the next checkpoint.

AWS deployment is a later checkpoint after the local flow works. It will add cloud learning without making credentials or paid infrastructure a prerequisite for the first preview.

## Step 1 walkthrough

Prerequisites: the database foundation from PR #77 and the project-workspace branch, Docker Compose, and an ignored `.env` copied from `.env.example` with a unique local database password.

```sh
docker compose up -d --build
docker compose exec backend python -m alembic upgrade head
```

1. Open <http://localhost:8080>.
2. Enter `Customer API migration` and a synthetic description; select **Create project**.
3. Confirm the saved message, project list entry and selected-project panel.
4. Reload the page. Select the saved project again; it remains in PostgreSQL.
5. An empty name cannot be submitted. If the backend is unavailable, the UI shows an error and a retry action for loading projects. A failed save retains your form input; check the list before retrying if a connection was lost.

Selection is temporary UI state; projects are persisted. Each list page contains up to 20 projects. Identical names are allowed; UUIDs identify projects. Contract upload is available through Manage contracts; comparison execution remains a future step.

CI runs a Chromium walkthrough against the real backend and a fresh PostgreSQL database, including create/reload/select, escaped markup, load retry and failed-save input retention. It uploads a screenshot and failure traces as `browser-test-results`. To run it locally, start a backend on port 8000 with a disposable empty migrated database, then run `npx playwright install chromium` and `npm run test:e2e` from `frontend`. Playwright starts Vite on port 5173; stop any existing server on that port first. The walkthrough creates synthetic projects and expects an empty database on its first run.

For development without rebuilding containers, run the backend as documented in the README, then `npm run dev` in `frontend`. Vite proxies `/api` to the local backend on port 8000. No browser credentials are required for this loopback-only, single-user preview. Do not expose these unauthenticated endpoints publicly.

## Step 1 API

The project workspace also has React component tests in `frontend/src/App.component.test.tsx`, run by `npm test` and the existing PR CI job. They use synthetic HTTP responses with the real API client to verify creation and selection, loading/empty states, rejected saves with retained input, list retry, keyboard selection, escaped markup, and duplicate-submit prevention. These tests require no backend or credentials; the browser walkthrough remains the check against real persistence. This completes the component-test prerequisite in #31; the live contract upload and version-selection walkthrough for #32 follows below.

- `POST /api/projects`: JSON `{ "name": "Customer API", "description": "Optional" }`; returns 201 with UUID and timestamp after the transaction commits.
- `GET /api/projects?offset=0&limit=20`: newest-first list, stable UUID tie-breaker, limit 1–100.
- `GET /api/projects/{id}`: project detail or 404.

Names are trimmed and limited to 1–200 characters; descriptions to 2,000 characters. Unknown fields are rejected. Project request bodies are limited to 16 KiB before JSON parsing, including chunked bodies. Database errors return a generic 503 without connection details. Authentication and multi-user authorization are outside this local checkpoint and are prerequisites for public hosting.

## Step 2 browser walkthrough

1. Create or select a project, then choose **Manage contracts** (or **Contracts** in the sidebar).
2. Upload `docs/examples/customer-v1.json` with label `v1`, then `customer-v2.yaml` with label `v2`.
3. Confirm the saved filename, OpenAPI version and timestamp. Select distinct baseline/candidate versions; the screen reports the pair ready. Compare stays disabled and labelled coming soon until the comparison API is implemented.
4. Try uploading `v1` again: duplicates show an error and retain your input. Invalid documents show validation guidance. Files must be nonempty, at most 1 MiB, and have a plain ASCII `.json`, `.yaml` or `.yml` filename. The backend remains authoritative for schema and resource validation.
5. Reload and reselect the project to see persisted versions. Project switching clears upload drafts and version selections and cancels pending client requests. Navigation within the same project preserves the draft and pair; refresh/upload success clears the pair. Selections are not persisted across reloads.

Saved metadata is loaded 20 versions at a time; **Load more versions** makes older entries selectable. Failed list requests offer retry. A timeout/network failure can occur after a server save: use **Refresh versions** before retrying. Cancelling a browser request does not roll back a server transaction. No automatic upload retries are performed.

Component and client tests use fake HTTP responses. The real-backend browser walkthrough uploads both fixture formats, verifies duplicate/invalid rejection, reloads persisted versions, checks project isolation, and captures desktop/mobile screenshots. Existing PR CI runs all these tests. This remains a local single-user preview without authentication.
