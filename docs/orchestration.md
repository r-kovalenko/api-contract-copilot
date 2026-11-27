# Resumable read-only orchestration — #50

Apply migration `0008_workflow_execution`, then follow [session setup](sessions.md).
The orchestrator owns an immutable plan of 1–5 typed `search_code` / `search_knowledge`
steps. Each step returns at most five hits. Repository aliases come only from the server's
project-specific `COPILOT_REPOSITORIES`; tool arguments cannot choose project roots,
other projects, agents, providers or write operations. The final evidence specialist is
a pure typed function with no registry or agent handles. It preserves source IDs and
explicit missing/truncated/unavailable evidence; it does not invent an impact report.

## Try it

After creating a session, use `$url` from the session walkthrough:

```powershell
$execution = "$url/execution"
$plan = @{ steps = @(
  @{ operation = 'search_knowledge'; query = 'customer'; api_version = 'v2'; limit = 5 },
  @{ operation = 'search_knowledge'; query = 'migration'; api_version = 'v2'; limit = 5 }
) } | ConvertTo-Json -Depth 5
$run = Invoke-RestMethod $execution -Method Post -ContentType 'application/json' -Body $plan
$body = @{ expected_revision = $run.workflow.revision } | ConvertTo-Json
$run = Invoke-RestMethod "$execution/resume" -Method Post -ContentType 'application/json' -Body $body
$body = @{ expected_revision = $run.workflow.revision } | ConvertTo-Json
$run = Invoke-RestMethod "$execution/pause" -Method Post -ContentType 'application/json' -Body $body
```

Restart the backend and GET `$execution`. Its workflow is `waiting_for_user`, and
`next_step` remains 1. POST `/resume` with the current revision runs only step 2, then
returns a `completed` workflow with a citation summary. Empty documentation yields
explicit `no_matches` gaps. Read every response/GET for the next revision rather than
assuming how many revisions elapsed. Messages are stored but do not implicitly resume.

## Endpoints and checkpoints

All paths are `/api/projects/{project}/sessions/{session}/execution`:

- POST the plan to create it. Repeating the identical plan returns the saved execution;
  changed plans return 409. A session must initially be running.
- GET returns plan, next-step cursor, current attempt count, lease expiry, saved typed
  attempt responses and final summary. Tool evidence is stored as untrusted data.
- POST `/resume` with `expected_revision` claims and executes at most one step. A recovery
  call may finalize an exhausted interrupted step without invoking a tool.
- POST `/pause` moves between-step running state to `waiting_for_user`.
- POST `/cancel` marks a nonterminal workflow failed, records a cancellation gap and
  clears the claim. Prior committed evidence remains available. It does not kill an
  in-flight read: that worker's result is discarded when it returns.

The earlier manual transition endpoint rejects managed executions. Approval waits cannot
resume here; this API provides no approval decision or write capability. Completed/failed
executions are terminal; begin a new session for new work. Plans are immutable, including
queries during clarification waits. Rich clarification and migration planning come later.

## Recovery and concurrency guarantees

A transaction locks the project-scoped session and saves a claim UUID, attempt counter,
120-second lease and workflow revision before invoking a tool. Tool calls run outside
that transaction. The result/cursor/summary checkpoint is committed atomically only if
the claim is still current, unexpired, and running. Concurrent or stale resumes return
409. Cancelled, expired or superseded workers cannot save results.

Each step has at most **two attempts**, including interrupted claims. An unavailable
response saves its safe failure code and permits one explicit retry. Rejections are not
retried. Exhausted failures advance with an evidence gap, allowing other steps to proceed.
Expired claims are recorded as timeouts on the next explicit resume. Unknown crashes leave
the claim recoverable after expiry. There is no polling daemon or automatic retry loop.

Committed steps are never replayed. A read completed immediately before a process/storage
failure may be retried if its result was not committed. This is bounded at-least-once read
execution with fenced persistence, not exactly-once external effects. Existing tools have
bounded concurrency, query/subprocess/provider timeouts and output limits; lease expiry
itself does not terminate arbitrary work. No write tools or live LLM calls are added.

`workflow_executions` stores project/session, plan JSON, cursor, attempts, lease and summary.
`tool_runs` adds nullable step index/attempt for legacy rows and a unique per-session
step/attempt constraint. At most ten attempt responses exist per execution. Summary gaps
reflect each step's final response; earlier transient failures remain in attempt history.
Rollback of the migration removes execution state and attempt indexing, preserving session
history and tool results. Back up before downgrading.

## Validation and limits

PostgreSQL tests cover restart-style reload without replaying committed steps, duplicate
plans, concurrent resumes, cancellation fencing, expired claims, retry exhaustion, result
rollback, project isolation and approval bypass attempts. Unit tests cover typed read-only
plans and the evidence specialist's citation/gap behavior. This is still an unauthenticated
local single-user API checkpoint, not a public deployment or new React conversation screen.
