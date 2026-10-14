# API Contract Copilot

Analyze how OpenAPI contract changes affect consumer integrations, then produce evidence-backed impact reports and migration plans.

**Status:** tested starter infrastructure. The FastAPI health endpoint and React landing page run; comparison, RAG, agents, approvals, and MCP are tracked implementation work, not completed features.

## Repositories

| Repository | Responsibility |
| --- | --- |
| [api-contract-copilot](https://github.com/r-kovalenko/api-contract-copilot) | React UI, FastAPI modular monolith, application data, orchestration, RAG, approvals, and Copilot MCP |
| [api-provider-demo](https://github.com/r-kovalenko/api-provider-demo) | Synthetic versioned customer API, OpenAPI contracts, changelog, migration docs, and planned provider MCP |
| [api-consumer-demo](https://github.com/r-kovalenko/api-consumer-demo) | Example v1 integration, compatibility tests, and planned consumer MCP |

Keep the frontend and backend together so cross-layer changes can be tested and reviewed in one pull request. The two demo repositories provide independent codebases for MCP integration.

## Local development

Requires Python 3.12, Node.js 24, and Docker with Compose for containers.

```sh
cd backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m uvicorn app.main:app --reload
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Backend liveness: http://localhost:8000/api/health. API docs: http://localhost:8000/docs. Vite prints the frontend development URL. The starter UI does not yet call application APIs.

For the container stack, copy `.env.example` to `.env`, then:

```sh
docker compose up --build
# Optional database for the persistence milestone:
docker compose --profile data up --build
```

Container UI: http://localhost:8080. PostgreSQL is optional at this stage; database models and migrations are pending. Local database credentials are development-only.

## Tests and CI

```sh
cd backend
python -m ruff check .
python -m ruff format --check .
python -m pytest --cov=app
cd ../frontend
npm ci
npm run typecheck
npm test
npm run build
```

Pull requests run Python lint/format checks, pytest, frontend type checks/tests/build, and container build/smoke tests. The `CI` check summarizes all jobs. Test reports are uploaded as artifacts. Main-branch pushes also publish tested container images to GHCR tagged by the full Git commit SHA. No paid model calls or deployment credentials are required for CI.

See [delivery details](docs/ci-cd.md), [contribution guidance](CONTRIBUTING.md), and the [implementation backlog](docs/backlog.json). Dependency versions are locked in `requirements-dev.txt`, `requirements-runtime.txt`, and `package-lock.json`. GitHub Actions are pinned to reviewed release commits; Dependabot proposes weekly updates.

## Requirements and architecture

[Product requirements](docs/Product_Requirements.docx) and [system design](docs/System_Design.docx) describe the target MVP. Deterministic tools supply contract facts and exact code evidence; RAG supplies contextual sources; LLMs interpret those inputs. The orchestrator owns persisted state and approval decisions.

Public repository visibility is not an open-source license. License selection is tracked as an owner decision.
