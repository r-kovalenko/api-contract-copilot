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
- pip-audit checks locked Python runtime, development, and security-scanner dependencies. Known advisories block CI; scanner/network failures do not silently pass.
- The main frontend runs `npm audit --audit-level=high` against its lockfile.
- CodeQL runs extended security analysis for Python and, in the main repository, JavaScript/TypeScript. Analysis failures block CI; findings appear in GitHub code scanning and require triage. Successful analysis alone does not mean zero alerts.
- Security workflows run inside required CI before container publication, and separately on a weekly schedule to catch new advisories. Dependency changes remain covered by Dependabot.

Review medium/low findings as appropriate to exposure. Do not add blanket allowlists or `continue-on-error` to security gates. Document any justified, narrowly scoped exception with an owner and expiry in the PR. Container OS vulnerability scanning and deployment-specific controls must be added with the deployment host; application dependency scanning is not an OS-image scan.

## Repository and environment controls

`main` requires a PR, passing CI, and resolved review conversations. GitHub secret scanning and push protection are enabled where supported. Private vulnerability reporting is the preferred channel. Deployment environments accept `main` only and require the owner to approve access to their secrets. The solo-owner setup permits the owner to approve their own run; add another reviewer and disable self-review when the team grows.

See [credential handling](secrets.md), [security reporting](../SECURITY.md), and the project skills in `.agents/skills/`.

## Reliable audit operation

Python audits run on all three lockfiles, including scanner dependencies. Scanner installation requires hashes and has bounded network retries. The audit runner retains each attempt under `security-reports/` and uploads diagnostics for seven days, even on failure. A valid report containing vulnerabilities fails immediately without retry; only operational failures (including timeout or incomplete/malformed output) are retried up to three times with backoff. Exhausted retries fail closed. Reports with skipped dependencies, empty dependency lists, or nonzero exits never count as clean. All lockfiles are attempted even when an earlier audit fails.

Each audit subprocess is limited to 180 seconds and individual service requests to 30 seconds; the job's 20-minute limit is the final bound. Gitleaks downloads have bounded retries/timeouts and still require the exact checksum. The scan itself is not retried or suppressed. Frontend registry requests also have bounded retries; the high-severity audit threshold is unchanged. Unit tests exercise clean results, findings, temporary/permanent outages, malformed/skipped reports, and timeout recovery without network access.

Routine Dependabot version-update PRs are disabled for Python, npm and GitHub Actions (`open-pull-requests-limit: 0`). Security fixes are grouped per ecosystem/directory. High/critical-only automatic security PRs require a separate repository auto-triage rule: the YAML does not filter severity. Setup and verification are documented in [dependency maintenance](dependency-maintenance.md). These settings do not auto-merge updates. New advisories legitimately turn a previously green build red: inspect the JSON reports, patch affected lockfiles, and merge a green PR. Scheduled runs use main, so an unmerged fix cannot repair scheduled main-branch checks. Never bypass a finding or treat an unavailable advisory service as a clean scan.

## Temporary frontend development dependency exception

Owner: r-kovalenko. Authorized in the project chat on 2026-11-17 to relax the failing security check. Expires **2026-12-01 (UTC)**, when the finding automatically blocks again.

Only `GHSA-fc5q-39xc-vjpf` for picomatch and dependency findings caused exclusively by that advisory are temporarily nonblocking in the full frontend audit. Production dependencies are audited separately with no exception. Other high/critical advisories, unknown/malformed audit results, command failures and timeouts still block. Raw reports are retained as CI artifacts for seven days. Secret scanning, Python checks and CodeQL are unchanged.

Rationale: the latest picomatch release is affected with no published fix, blocking the local MVP's development toolchain. This accepts residual regular-expression denial-of-service risk in build/test tools; do not pass untrusted glob patterns to them or expose the development server publicly. This exception does not repair the vulnerable dependency. Remove it as soon as a patched release is available, update the lockfile, and rerun CI. Source: https://github.com/advisories/GHSA-fc5q-39xc-vjpf
