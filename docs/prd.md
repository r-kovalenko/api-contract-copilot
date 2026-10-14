# API Contract Copilot Product Requirements

Markdown transcription of [Product_Requirements.docx](Product_Requirements.docx). Requirements describe the target MVP, not current implementation status. Subsequent repository security conventions are documented separately in [security.md](security.md).

AI ENGINEERING LEARNING PROJECT

API CONTRACT<br>
COPILOT

Product Requirements Document — MVP

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AI-powered API change impact analysis and migration planning

Version 1.0  •  September 2026

| Primary user | Backend and integration engineers |
| --- | --- |
| Core value | Understand what an API change breaks, where, and how to migrate |
| MVP focus | One complete learning workflow, not an enterprise API-management platform |

## 1. Product Overview

API Contract Copilot helps engineering teams understand how changes in an API contract affect an existing integration. It combines deterministic contract comparison, code search, retrieval-augmented generation (RAG), and LLM reasoning into one guided workflow.

> Product principle<br>Use deterministic tools for facts that can be computed reliably. Use RAG for contextual knowledge. Use the LLM for interpretation, explanation, and planning.

## 2. Problem Statement

When an external or internal API changes, engineers typically move between specifications, changelogs, migration guides, code search, and issue tracking. The hard part is not only detecting that a contract changed, but understanding which parts of the application may be affected and what work is required to migrate safely.

- Contract diffs identify technical changes but usually do not explain application-specific impact.

- API documentation and migration notes are often separate from the code that consumes the API.

- Engineers repeat the same context gathering each time an API version changes.

- Follow-up work is manually converted into migration steps and tasks.

## 3. Goals & Non-Goals

| Type | Definition |
| --- | --- |
| Goal | Detect breaking OpenAPI changes and present them as structured facts. |
| Goal | Find potentially affected code and retrieve relevant migration knowledge. |
| Goal | Generate a source-backed impact report and practical migration plan. |
| Goal | Demonstrate RAG, agents, tools, MCP, planning, approval, tracing, and dynamic UI in one coherent workflow. |
| Non-goal | Replace a full API management, observability, or CI/CD platform. |
| Non-goal | Automatically modify or deploy production code in the MVP. |

## 4. Target Users & User Stories

| User | Need |
| --- | --- |
| Backend / integration engineer | Compare API versions and quickly see breaking changes. |
| Backend / integration engineer | See where a changed endpoint, field, or schema is used and what may be affected. |
| Backend / integration engineer | Get relevant migration knowledge with sources and a practical migration plan. |
| Technical lead | Review impact and keep control of follow-up actions through approval. |

## 5. Core User Flow

1. Create a project and add two OpenAPI contract versions.

1. Compare versions and show breaking and non-breaking changes.

1. Select a change or ask the assistant to analyze relevant changes.

1. Search connected code and retrieve relevant API or migration knowledge.

1. Generate an impact report, migration plan, and test checklist.

1. Require approval before creating a follow-up migration task.

> First vertical slice<br>Upload OpenAPI v1/v2 → Compare contracts → Select breaking change → Retrieve knowledge → Search affected code → Generate impact report.

## 6. MVP Functional Scope

### Project management

Create a project, associate contracts, documentation, and a demo codebase, and view previous analysis sessions.

### Contract comparison

Upload or select two OpenAPI 3.x contracts; detect and display structured breaking and non-breaking changes using deterministic comparison.

### Impact analysis

Search the connected codebase, retrieve relevant documentation and migration context, produce an impact summary, and list potentially affected files.

### RAG knowledge

Ingest API documentation, changelogs, migration guides, internal integration notes, and architecture notes. Retrieve context with metadata and provide source references.

### Migration planning

Generate migration steps and a test checklist. Ask clarification questions when important context is missing.

### Sessions & history

Store conversations, prior analyses, and workflow state so an analysis can be resumed later.

### Human approval

Require explicit approval before creating a migration task or any other write action.

### Dynamic UI

Return typed UI events for changes, affected files, sources, plans, tool activity, and approvals rather than only plain chat text.

## 7. AI & Agent Requirements

### Central Orchestrator

A single orchestrator owns workflow state and controls intent detection, planning, agent selection, tool execution, clarification, and approval. Agents do not call each other directly.

### Specialist Agents

| Component | Responsibility |
| --- | --- |
| Contract Analysis Agent | Combines structured contract changes, code-search results, and retrieved knowledge into an impact report with affected files and source-backed recommendations. |
| Migration Agent | Creates migration steps, a test checklist, identifies missing information, and proposes follow-up work. |
| Planner (lightweight) | Creates a short plan for broad requests and asks clarification questions only when information required to continue is missing. |

### Custom Tools

- compare_contracts — deterministic comparison of two OpenAPI contracts.

- search_code — exact or repository-backed search for affected usages.

- search_knowledge — RAG retrieval across API and migration knowledge.

- Optional: run_contract_tests — validate selected contract scenarios.

### MCP Requirements

The Copilot exposes at least five useful operations through its own MCP server and connects to two small demo projects.

| Integration | Minimum operations |
| --- | --- |
| Copilot MCP server | get_contract, list_contract_versions, compare_contracts, search_api_docs, get_change_details |
| Consumer demo project | search_code, get_file, list_dependencies |
| Provider demo project | get_openapi_spec, get_api_version, get_changelog |

### Human-in-the-Loop

The MVP includes one write action: create migration task. The system must show the proposed task, explain the action, wait for explicit approval or rejection, and resume the persisted workflow after the decision.

## 8. Technology & Implementation Direction

The technology choices are intentionally simple and selected to maximize hands-on AI engineering learning while keeping the project realistic to finish.

| Layer | Technology / Approach | Why for this MVP |
| --- | --- | --- |
| Frontend | React + TypeScript | Keep the UI familiar while focusing learning effort on the AI backend. |
| Backend API | Python + FastAPI | Learn production-style async Python in an AI-oriented project. |
| Validation / schemas | Pydantic v2 | Typed request, tool, agent, and structured-output models. |
| Persistence | PostgreSQL + SQLAlchemy 2 + Alembic | Application data, sessions, workflows, and migrations. |
| RAG retrieval | PostgreSQL FTS + pgvector | Hybrid keyword + semantic retrieval without a separate vector database. |
| LLM integration | OpenAI or Claude behind a provider interface | Avoid coupling the architecture to one model vendor. |
| Contract comparison | oasdiff | Deterministic OpenAPI change detection rather than asking the LLM to infer contract facts. |
| Code search | ripgrep initially; MCP search for demo integration | Simple exact search first; deeper analysis is deferred. |
| MCP | Python MCP SDK | Expose Copilot capabilities and connect the two demo projects. |
| Observability | OpenTelemetry + Jaeger | Trace LLM, RAG, tools, agents, MCP, and approvals. |
| Testing | pytest | Unit and integration tests for Python components. |
| Local environment | Docker Compose | Reproducible local setup. |

### Intentionally Not Required for MVP

LangChain, LangGraph, Celery, Kafka, Kubernetes, a separate vector database, multiple backend microservices, and advanced AST dependency analysis are not required initially. They should only be introduced if the working MVP creates a concrete need.

## 9. Quality, Safety & Observability

- Every analysis run has a trace ID and is traceable across orchestration, LLM calls, retrieval, tools, agents, MCP calls, and approvals.

- Unavailable sources and failed tools are surfaced clearly; the system must not fabricate missing results.

- Impact reports include source references when retrieved knowledge is used.

- Write actions never execute without explicit approval, and workflow state remains persisted while waiting.

## 10. Success Metrics

| Metric | Target |
| --- | --- |
| Contract accuracy | Known breaking changes in the evaluation scenarios are detected correctly by deterministic tooling. |
| RAG quality | Relevant knowledge appears in the top five retrieval results for at least 80% of evaluation questions. |
| Approval safety | 100% of write actions require explicit approval. |
| Traceability | 100% of agent and tool executions have a trace identifier. |
| Demo latency | A complete demo analysis finishes in under 10 seconds under normal demo conditions. |
| Resilience | Failed tools or unavailable sources are handled without crashing the workflow. |

## 11. Assumptions & Constraints

| Assumptions | OpenAPI 3.x contracts; small demo repositories; mostly text-based documentation; synthetic and public sample data are acceptable; consumer and provider demo projects are controlled by the team. |
| --- | --- |
| Constraints | Single-user learning MVP; no production credentials or production changes; no enterprise-scale indexing; no multi-tenant authorization. |

## 12. Out of Scope

- Runtime production traffic analysis or autonomous remediation.

- Automatic source-code modification, pull-request creation, or production deployment actions.

- Enterprise authentication, billing, multi-tenant organizations, and large-scale distributed indexing.

- Advanced dependency graphs, model fine-tuning, and full API governance.

## 13. Release Criteria

- Two contract versions can be added, compared, and breaking changes displayed.

- A selected change can be analyzed against related code and relevant knowledge.

- An impact report, migration plan, and clarification flow work end to end.

- Migration-task approval/rejection and session persistence work.

- AI, retrieval, tools, agents, MCP, and approval steps are traceable.

- The MCP server exposes at least five operations and both demo projects can be queried.

> Implementation order<br>First make the vertical slice work end to end. Then add migration planning → planning/Q&A → approval → MCP integrations → deeper tracing → evaluation.
