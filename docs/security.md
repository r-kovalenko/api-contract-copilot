# Security baseline

This is the project control baseline, not a certification. The current application is a learning scaffold. Controls for future upload, RAG, MCP, approval, and authentication features must be implemented and tested with those features; automated scans do not establish that they already exist.

Use [OWASP ASVS 5.0](https://owasp.org/projects/asvs) to define verifiable application requirements, [API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) for API abuse cases, and [LLM Top 10 2025](https://genai.owasp.org/llm-top-10/) for model and retrieval risks. These references guide the project-specific controls below.

## Trust boundaries and required evidence

| Surface | Required control | Verification when implemented |
| --- | --- | --- |
| API/project data | Authorize every object and function; bind queries to project and principal; reject mass assignment | Wrong-project and unauthorized-operation tests |
| Contracts and uploads | Size/type/schema limits, safe parsing, no external references fetched implicitly | Malformed, oversized, nested, and external-reference cases |
| Code search and MCP files | Allowlisted operations, resolved path containment including symlinks, bounded output | Traversal, symlink escape, unknown operation, timeout tests |
| Remote fetches | Explicit destination policy, redirect revalidation, no untrusted access to metadata/private networks | Loopback, private address, DNS/redirect SSRF tests |
| SQL and subprocesses | Parameterized queries and argument arrays; no shell interpolation; timeouts | Injection payloads remain data; timeout cleanup |
| RAG and models | Untrusted context cannot grant tool permission; validate output and source IDs; retain provenance | Prompt injection, poisoned context, unknown citation tests |
| Approval and workflow | Bind approval to exact payload and principal; reject stale/replayed requests; transactional idempotency | Restart, concurrent approve, changed payload, reject tests |
| Browser output | Trusted React components; escaped data; CSP; no credentials in frontend | Stored/reflected markup payloads and event validation |
| Resources | Limit upload/search/retrieval/model budgets and concurrent operations | Rate/size/timeout failure tests with explicit errors |
| Credentials and telemetry | Least privilege, server-only injection, redaction, rotation | No values in logs/errors/traces/artifacts; missing credentials fail closed |

The synthetic demos intentionally demonstrate incompatible API versions; this is not permission to add exploitable endpoints. No public deployment of real data is ready until access control, TLS, limits, and operational secrets are implemented.

## Automated checks

- Gitleaks scans Git history with redacted output and a checksum-pinned binary. Findings block CI.
- Bandit scans Python application code for medium/high-severity findings. Findings block CI; tests are not scanned as application code.
- pip-audit checks locked Python runtime and development dependencies. Known advisories block CI; scanner/network failures do not silently pass.
- The main frontend runs `npm audit --audit-level=high` against its lockfile.
- CodeQL runs extended security analysis for Python and, in the main repository, JavaScript/TypeScript. Analysis failures block CI; findings appear in GitHub code scanning and require triage. Successful analysis alone does not mean zero alerts.
- Security workflows run inside required CI before container publication, and separately on a weekly schedule to catch new advisories. Dependency changes remain covered by Dependabot.

Review medium/low findings as appropriate to exposure. Do not add blanket allowlists or `continue-on-error` to security gates. Document any justified, narrowly scoped exception with an owner and expiry in the PR. Container OS vulnerability scanning and deployment-specific controls must be added with the deployment host; application dependency scanning is not an OS-image scan.

## Repository and environment controls

`main` requires a PR, passing CI, and resolved review conversations. GitHub secret scanning and push protection are enabled where supported. Private vulnerability reporting is the preferred channel. Deployment environments accept `main` only and require the owner to approve access to their secrets. The solo-owner setup permits the owner to approve their own run; add another reviewer and disable self-review when the team grows.

See [credential handling](secrets.md), [security reporting](../SECURITY.md), and the project skills in `.agents/skills/`.
