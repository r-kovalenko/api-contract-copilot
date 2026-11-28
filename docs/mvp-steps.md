# Demo checkpoints

Work one demoable step at a time and pause for owner review after each step. A checkpoint is ready for review when its tests pass and its local demo is reproducible. This sequence narrows the existing backlog; it does not mark unfinished parent features complete.

| Step | What you can try | Existing work | Completion evidence |
| --- | --- | --- | --- |
| 1 — Project workspace | Create, list and select projects; reload and see saved projects | F01 database foundation; project portion of F02.1 (#29) and F03.1 (#31) | PostgreSQL integration tests, API validation/failure tests, UI checks and local walkthrough |
| 2 — Contract uploads | Add baseline and candidate OpenAPI versions to a selected project | Remaining F02/F03, including #30 and #32 | JSON/YAML validation, bounded parsing, duplicate versions, project isolation and browser upload flow |
| 3 — Contract comparison | Compare two saved versions and inspect breaking changes | V01 and initial V04 | Pinned oasdiff, deterministic scenario fixtures, timeout/error handling and UI change selection |
| 4 — Evidence-backed report | Select a change and see affected demo code, migration documentation and an impact report | V02, R01, V03 and remaining V04; relevant provider/consumer fixtures | Upload-to-report browser test with fake providers; exact file/line evidence and validated citations |

Step 4 is the first end-to-end MVP preview. Migration planning, persisted agent conversations, approval, MCP, richer RAG and observability follow the PRD implementation order after that preview is accepted.

Step 2 backend checkpoint: project-scoped JSON/YAML uploads, schema validation and immutable contract APIs are implemented in feature #2. Use the [API walkthrough](contract-uploads.md) to review them. The React upload and old/new version-selection flow is implemented in #32. Comparison execution is available in Step 3 below.

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

Selection is temporary UI state; projects are persisted. Each list page contains up to 20 projects. Identical names are allowed; UUIDs identify projects. Contract upload is available through Manage contracts; comparison execution is available in Step 3 below.

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
3. Confirm the saved filename, OpenAPI version and timestamp. Select distinct baseline/candidate versions; the screen reports the pair ready. Compare contracts runs the selected pair and opens its saved evidence.
4. Try uploading `v1` again: duplicates show an error and retain your input. Invalid documents show validation guidance. Files must be nonempty, at most 1 MiB, and have a plain ASCII `.json`, `.yaml` or `.yml` filename. The backend remains authoritative for schema and resource validation.
5. Reload and reselect the project to see persisted versions. Project switching clears upload drafts and version selections and cancels pending client requests. Navigation within the same project preserves the draft and pair; refresh/upload success clears the pair. Selections are not persisted across reloads.

Saved metadata is loaded 20 versions at a time; **Load more versions** makes older entries selectable. Failed list requests offer retry. A timeout/network failure can occur after a server save: use **Refresh versions** before retrying. Cancelling a browser request does not roll back a server transaction. No automatic upload retries are performed.

Component and client tests use fake HTTP responses. The real-backend browser walkthrough uploads both fixture formats, verifies duplicate/invalid rejection, reloads persisted versions, checks project isolation, and captures desktop/mobile screenshots. Existing PR CI runs all these tests. This remains a local single-user preview without authentication.

## Step 3 runner checkpoint

The [oasdiff runner demo](contract-comparison.md) implements #33 with pinned real-engine fixtures and bounded subprocess execution. Run `python backend/demo_comparison.py` after installing the binary to inspect deterministic changes in the synthetic contracts. This is a backend checkpoint; project-scoped comparison persistence/API (#34) is now available for review through the walkthrough below. The live comparison screen is available in the following checkpoint.

## Step 3 saved comparison API checkpoint

Apply `alembic upgrade head`, upload two synthetic versions, and use the [saved comparison API walkthrough](contract-comparison.md#saved-comparison-api). Verify repeat POST returns the same result, reverse the pair to see directional changes, then retrieve a saved change by ID. This checkpoint uses PostgreSQL and the real pinned engine without an LLM or credentials. Use the live screen checkpoint below to review the browser integration.

## Step 3 live comparison walkthrough

1. Upload the synthetic customer v1/v2 fixtures, choose their baseline/candidate order, and click **Compare contracts**. Selection and uploads are disabled while the request is pending.
2. The Comparison screen shows saved version IDs, engine version, normalized changes, and canonical document hashes. Filter by breaking, potentially breaking, or nonbreaking; select a change to fetch its stable ID's saved evidence.
3. Reload, reselect the project, open **Comparison**, and choose its saved comparison. History is paginated 20 at a time. A repeat pair reuses the saved result; reversed order is a distinct comparison.
4. Empty results and filters have explicit messages. Failed loads offer retry; failed comparison creation preserves the chosen pair. After an unconfirmed network request, refresh saved history before retrying. Cancelling a request does not undo server work.
5. Switching projects cancels in-flight requests and clears comparison state. Source locations refer to canonical JSON, not original YAML lines. Text is escaped, with no HTML execution. **Analyze impact** remains disabled because the analysis service is a later checkpoint. Task #39's analysis-start acceptance criterion remains open.

Component tests cover filtering, empty states, errors, version changes, stale responses, and exact selected-change requests. The real-backend browser walkthrough creates a comparison and reopens it after reload, with desktop/mobile screenshots.

## Step 4 exact-search backend checkpoint

Task #35 adds [bounded exact code search](code-search.md). Run `docker compose exec backend python demo_code_search.py` after rebuilding the backend to inspect synthetic consumer evidence for `full_name`. This is the next deterministic building block for an impact report. Tool-registry/API integration (#36), documentation retrieval and model-based report generation remain separate steps. The Analyze impact button remains disabled until those dependencies exist.

## Saved impact report checkpoint (#40)

Select a comparison change, enter evidence search terms, and run **Analyze impact**. Choose **View impact report** to review facts, potential files, recommendations, source citations and explicit gaps. Use the **Impact report** sidebar to reopen saved runs after reselecting the project. The default provider remains offline; no model credentials are needed. See [the complete walkthrough](impact-analysis.md).

## Embedding lifecycle checkpoint (#45)

Follow [the offline embedding walkthrough](embeddings.md) after ingesting a document.
Check unindexed status, index it, and repeat the request to verify an unchanged saved
snapshot. This API checkpoint prepares hybrid retrieval (#46); it introduces no live
model calls or browser screen. Pause for review before implementing ranking.

## Hybrid retrieval checkpoint (#46)

Use `mode=hybrid` on the knowledge search API or tool after indexing documents.
Follow [the ranking and failure-policy walkthrough](document-retrieval.md#hybrid-retrieval-checkpoint-46).
This combines filtered keyword and compatible vector candidates with deterministic RRF.
The default fake provider demonstrates mechanics only; keyword remains the default.
Pause for review before the evaluation dataset task (#47).

## Ground-truth checkpoint (#47)

Follow [the evaluation fixture guide](evaluation.md) to validate and inspect 10 documents,
8 retrieval cases and 6 contract scenarios. Review rationales and held-out membership.
This checkpoint defines labels; metrics and evaluation reports follow in #48.

## Offline scoring checkpoint (#48)

Run the [evaluation command](evaluation.md#run-evaluation-and-inspect-reports-48) against
an empty disposable test database. Inspect split/mode recall, negative-case diagnostics,
and missing/unexpected contract evidence in the JSON artifact. Required CI runs this
same gate without paid model calls. Pause for review before stateful workflow work.

## Session persistence checkpoint (#49)

Use [the session API walkthrough](sessions.md) to save messages, link an analysis report,
move into a waiting state and reload after restarting the backend. Verify duplicate-message
retries and stale transition rejection. This is a persistence checkpoint; execution/resume
and a browser conversation interface remain later work.

## Orchestrator recovery checkpoint (#50)

Follow [the resumable execution walkthrough](orchestration.md): start a two-step read plan,
run one step, pause, restart and resume without replaying the saved result. Inspect attempt
history and evidence gaps. Cancellation and exhausted retries are explicit; write approvals
and migration-agent planning remain separate checkpoints.

## Step 51: Advisory migration plans

Generate a plan from a saved analysis, inspect ordered evidence references, test checklist,
open questions and proposed task data, then reload the saved snapshot. See the
[migration-plan walkthrough](migration-plans.md). Validate missing evidence and project
isolation. No write tools or live providers execute; clarification resume follows in #52.
