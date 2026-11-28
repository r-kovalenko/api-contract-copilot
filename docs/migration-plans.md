# Migration plan checkpoint

Create an immutable advisory plan from a saved impact analysis:

```powershell
$base = "http://localhost:8000/api/projects/$projectId/migration-plans"
$body = @{ analysis_id = $analysisId } | ConvertTo-Json
$plan = Invoke-RestMethod $base -Method Post -ContentType application/json -Body $body
$plan.plan.steps | Format-Table order, instruction, source_ids
$plan.plan.test_checklist
$plan.plan.open_questions
Invoke-RestMethod "$base/$($plan.id)"
```

Use a project and saved analysis from the [impact-analysis walkthrough](impact-analysis.md).
Apply `python -m alembic upgrade head` before using these endpoints.
`GET` on the collection lists metadata with `offset` and `limit` (1–100).
Each POST creates a new snapshot; retries may create another plan. Saved snapshots
cannot be edited or deleted through this API. Reloading reads the same persisted data.

The offline migration agent selects fixed review templates for the deterministic
change, exact code matches, and document citations already captured by the analysis.
It returns ordered steps, a candidate-contract test checklist, open questions, inherited
evidence gaps, and proposed task data. All plans remain `needs_review`; these are
review scaffolds, not code patches or a claim that a migration is safe or complete.
Exact matches do not prove impact. Conflicting sources require human resolution.
Missing code/document evidence adds questions. Existing evidence gaps are preserved.

The provider boundary accepts only source IDs and types. Output is limited to 16 KiB,
20 steps, allowlisted advisory actions, complete source coverage and unique known
citations of the appropriate type. Extra instructions, writes, invented sources and
unsupported output are rejected before persistence. Retrieved text never becomes an
instruction or executable command. The API uses the offline provider regardless of
LLM environment settings and makes no external calls. It does not create GitHub tasks,
change source files, approve actions, or execute the checklist.

POST requests are limited to 16 KiB. Unknown/cross-project analyses or plans return404;
invalid requests return422; database or generation validation failures return a generic
503 without underlying exception details. No partial plan is committed on failure.

Migration `0009_migration_plans` adds `MigrationPlanRecord` / `migration_plans` with
UUID ID, project ID, analysis ID, JSONB plan and timestamp. A composite foreign key
requires the analysis to belong to the same project. Downgrade removes plan snapshots
and preserves analyses. Back up data before downgrading.

This API-only step is #51. Answer persistence/resume (#52), approval, task creation,
UI rendering, and live model planning remain separate work. The local single-user
preview does not yet provide authentication.
