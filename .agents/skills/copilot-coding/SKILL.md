---
name: copilot-coding
description: Implement or review Python, React, API contracts, and tests in the API Contract Copilot repositories using their modular architecture and deterministic evidence boundaries.
---

# API Contract Copilot coding

Read the repository README and the relevant issue acceptance criteria before changing code. The main repository's `docs/prd.md` and `docs/system-design.md` describe the target, while its README records current implementation status. For demo repositories, use their versioned contracts and linked main-repository design. Do not build unrequested later milestones.

Keep the FastAPI backend a modular monolith. Routes validate and delegate; services own application behavior; repositories own database access. Introduce these boundaries when the feature needs them, not as empty directories. Use typed Pydantic models at API, tool, agent, and event boundaries; narrow exceptions to recoverable failures. Use SQLAlchemy parameter binding, explicit transactions, and Alembic migrations for schema changes.

Contract compatibility comes from oasdiff and affected usages from exact code search. Do not replace deterministic facts with model inference. Preserve source IDs and evidence gaps. The orchestrator owns agent routing and persisted workflow state; agent output is validated data. Approval must bind to the exact proposed action and execute at most once after resume.

In React, represent loading, empty, error, and success states explicitly. Render typed events through trusted components with accessible labels and keyboard behavior. Do not render model-supplied HTML or JavaScript. Keep API credentials and provider calls in the backend.

Write tests for observable behavior, failure paths, and meaningful boundaries. Use synthetic fixtures, injected HTTP clients, and fake model/embedding providers in ordinary CI. Add PostgreSQL integration tests when persistence changes; test migrations against an isolated database. Keep provider contracts and export tests in sync, and keep consumer incompatibility tests intentional.

Run the affected repository's documented lint, formatting, tests, type checks, and build. Update lockfiles with dependency changes. Use a feature branch and PR; keep CI and security gates enabled. Summarize behavior changed, checks performed, and remaining limitations. Changes affecting uploads, paths, outbound URLs, approvals, credentials, workflows, or deployment also call for the `copilot-security` skill.
