# Demo checkpoints

Work one demoable step at a time and pause for owner review after each step. A checkpoint is ready for review when its tests pass and its local demo is reproducible. This sequence narrows the existing backlog; it does not mark unfinished parent features complete.

| Step | What you can try | Existing work | Completion evidence |
| --- | --- | --- | --- |
| 1 — Project workspace | Create, list and select projects; reload and see saved projects | F01 database foundation; project portion of F02.1 (#29) and F03.1 (#31) | PostgreSQL integration tests, API validation/failure tests, UI checks and local walkthrough |
| 2 — Contract uploads | Add baseline and candidate OpenAPI versions to a selected project | Remaining F02/F03, including #30 and #32 | JSON/YAML validation, bounded parsing, duplicate versions, project isolation and browser upload flow |
| 3 — Contract comparison | Compare two saved versions and inspect breaking changes | V01 and initial V04 | Pinned oasdiff, deterministic scenario fixtures, timeout/error handling and UI change selection |
| 4 — Evidence-backed report | Select a change and see affected demo code, migration documentation and an impact report | V02, R01, V03 and remaining V04; relevant provider/consumer fixtures | Upload-to-report browser test with fake providers; exact file/line evidence and validated citations |

Step 4 is the first end-to-end MVP preview. Migration planning, persisted agent conversations, approval, MCP, richer RAG and observability follow the PRD implementation order after that preview is accepted.

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

Selection is temporary UI state; projects are persisted. Each list page contains up to 20 projects. Identical names are allowed; UUIDs identify projects. Contract upload and comparison are labelled as future steps rather than presented as working actions.

For development without rebuilding containers, run the backend as documented in the README, then `npm run dev` in `frontend`. Vite proxies `/api` to the local backend on port 8000. No browser credentials are required for this loopback-only, single-user preview. Do not expose these unauthenticated endpoints publicly.

## Step 1 API

- `POST /api/projects`: JSON `{ "name": "Customer API", "description": "Optional" }`; returns 201 with UUID and timestamp after the transaction commits.
- `GET /api/projects?offset=0&limit=20`: newest-first list, stable UUID tie-breaker, limit 1–100.
- `GET /api/projects/{id}`: project detail or 404.

Names are trimmed and limited to 1–200 characters; descriptions to 2,000 characters. Unknown fields are rejected. Project request bodies are limited to 16 KiB before JSON parsing, including chunked bodies. Database errors return a generic 503 without connection details. Authentication and multi-user authorization are outside this local checkpoint and are prerequisites for public hosting.
