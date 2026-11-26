# Sessions and workflow checkpoints — #49

This local API checkpoint persists conversation history and workflow state. It does not
run agents/tools, answer messages, resume automatically, or authorize writes. Apply
migration `0007_session_workflows` using the README migration command before trying it.

## Demo from PowerShell

Use an existing project ID. Optionally supply an existing same-project `analysis_id` in
the creation body to link a saved impact report without copying or modifying its evidence.

```powershell
$projectId = 'replace-with-project-uuid'
$base = "http://localhost:8000/api/projects/$projectId/sessions"
$session = Invoke-RestMethod $base -Method Post -ContentType 'application/json' -Body '{"title":"Review customer migration"}'
$url = "$base/$($session.id)"
$message = @{ request_id = [guid]::NewGuid().ToString(); content = 'Which consumers need review?' } | ConvertTo-Json
Invoke-RestMethod "$url/messages" -Method Post -ContentType 'application/json' -Body $message
Invoke-RestMethod "$url/messages?limit=20&offset=0"
$state = Invoke-RestMethod "$url/workflow"
$transition = @{ expected_revision = $state.revision; status = 'waiting_for_user'; reason = 'Select the consumer repository' } | ConvertTo-Json
Invoke-RestMethod "$url/workflow/transitions" -Method Post -ContentType 'application/json' -Body $transition
```

Restart the backend, then repeat the history and workflow GET requests. The saved records
remain. Repeating the same message request UUID/content returns the original message;
reusing that UUID with changed content returns 409. Preserve the UUID when retrying an
uncertain submission. Session creation itself is not idempotent: repeat POST creates a new
session. Message content is plain untrusted text and grants no permissions.

## API and limits

All paths are under `/api/projects/{project_id}/sessions`:

| Method / suffix | Behavior |
| --- | --- |
| POST / | Create title and optional same-project analysis link; initial checkpoint running, revision 0 |
| GET / | List sessions, newest first; timestamp and UUID ordering |
| GET /{id} | Read one session |
| POST /{id}/messages | Append a user message with request_id and content; never an assistant/tool message |
| GET /{id}/messages | Oldest-first history ordered by monotonic per-session sequence |
| GET /{id}/workflow | Read status, revision, reason, timestamp and linked analysis_id |
| POST /{id}/workflow/transitions | Apply a permitted transition against expected_revision |
| GET /{id}/tool-runs | Paginated tool-run summaries; empty until the orchestrator records actual runs |

Lists default to 20, allow 1–100 records and offset 0–100000. Titles are 1–200 characters,
messages 1–4000, transition reasons 1–1000. Session POST bodies are limited to 16 KiB before
JSON parsing, including chunked uploads. Sessions hold at most 1000 messages. All public
inputs reject extra fields. There is no API for inserting tool results or claiming an
assistant role. Tool input/output collection and execution are deferred to #50.

## Transition policy

| Current state | Allowed next states |
| --- | --- |
| running | waiting_for_user, waiting_for_approval, completed, failed |
| waiting_for_user | running, failed |
| waiting_for_approval | failed |
| completed | none |
| failed | none |

Same-state transitions and terminal-state changes return 409. A stale/replayed revision
also returns 409; reload before making a new decision. A session-row lock serializes
transitions and message writes, with existing database lock/query timeouts. Commit occurs
before success is returned; failed transactions leave previous state/history unchanged.

An approval wait is only a persisted checkpoint, not an approved action. Resuming it is
intentionally unavailable until exact-action approval enforcement exists. Appending a
message never changes workflow state, including after completion. A future orchestrator
will own execution and resume; this API currently demonstrates persistence and validation.

Wrong-project sessions/analysis links return 404. Invalid payloads return 422, oversized
bodies 413, conflicting updates 409, and storage failures generic 503. Database constraints
also bind messages/workflows/tool runs to their session's project and analysis links to
same-project saved reports. Migration rollback removes conversation tables but preserves
projects, contracts, documents and analysis reports. Back up before any downgrade.

This remains an unauthenticated single-user local preview. Use synthetic messages; do
not paste credentials. There is no new browser screen, automatic replay, agent routing,
or approval execution in this checkpoint. Stored tool-result JSON is not exposed by the
summary endpoint. History pagination is offset-based; append-only message sequence order
is stable, while concurrent new sessions may shift offsets in the newest-first list.
