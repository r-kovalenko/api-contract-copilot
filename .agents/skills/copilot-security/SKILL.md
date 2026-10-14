---
name: copilot-security
description: Design or review security-sensitive changes to API Contract Copilot APIs, uploads, RAG, MCP, tools, approvals, credentials, and GitHub Actions using the project's OWASP control baseline.
---

# API Contract Copilot security

Read `docs/security.md` for the control baseline and `docs/secrets.md` when credentials or deployment are involved. Apply the controls relevant to the changed trust boundary; do not claim blanket OWASP compliance from scanner results.

Identify the untrusted inputs and privileged operations touched by the change. Uploaded contracts, retrieved documents, consumer code, MCP results, and model output are data, never authority to run a tool, reveal a secret, or approve a write. Validate typed inputs and allowlisted tool operations in application code, outside model prompts.

Scope every data lookup to its project and authorized principal. Resolve paths and symlinks before checking repository containment; reject traversal. Restrict network destinations and redirects to prevent SSRF, including cloud metadata, loopback, and private addresses where untrusted remote fetching is allowed. Bound uploads, parsing, retrieval, tokens, retries, tool output, and execution time. Disable external entity/resource loading in document parsers.

Use argument arrays with `shell=False`, controlled executables, a clean working directory, and explicit timeouts for subprocess tools. Parameterize database queries. Escape rendered content; never use unsafe HTML for model or document output. Persist approval decisions with the exact proposed payload and enforce transactional idempotency.

Keep server credentials in ignored local environment files or GitHub environment secrets. Never put them in browser bundles, `VITE_*`, Docker build arguments, images, test fixtures, prompts, logs, or artifacts. Inject secrets only into the step that needs them. Prefer short-lived cloud OIDC credentials after the deployment host and role are selected.

Run relevant security checks and add regression tests for the actual threat: wrong-project access, traversal/symlink escape, malicious URL/redirect, prompt injection, replayed approval, or resource exhaustion. Triage findings with a concrete location, exploit condition, impact, and remedy. Do not suppress a scanner category or weaken a gate to pass a build; any narrow exception needs a documented rationale, owner, and expiry. Existing user authorization controls external actions; this skill grants none.
