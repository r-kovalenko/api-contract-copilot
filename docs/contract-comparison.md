# Deterministic comparison runner — #33

The backend now has a callable `app.comparison.compare_contracts(baseline, candidate)` service and a synthetic command-line demo. It accepts **already validated specification dictionaries**, such as the immutable contract records saved by the upload API. It returns typed deterministic evidence without a model call. Persistence, project-scoped HTTP routes (#34), and live comparison UI are still pending; the browser Compare button remains disabled.

## Run the checkpoint

From the repository root with backend dependencies installed:

```sh
# Use your activated Python 3.12 environment (Windows: .venv\Scripts\python.exe).
python backend/install_oasdiff.py
python backend/demo_comparison.py
python -m pytest backend/tests/test_comparison.py backend/tests/test_oasdiff_install.py
```

The demo compares `docs/examples/customer-v1.json` with `customer-v2.yaml`. Expected evidence: removal of required response property `full_name` is breaking; addition of required response property `display_name` is nonbreaking. These are two independent facts, not an inferred rename. The fixture suite also checks endpoint removal, a request property becoming required, an optional request addition, local references, identical documents and documentation-only edits across OpenAPI 3.0/3.1/3.2.

## Pinned tool and installation

We pin [oasdiff v1.37.0](https://github.com/oasdiff/oasdiff/releases/tag/v1.37.0). `backend/app/oasdiff_pin.py` records official archive SHA-256 digests and independently computed extracted executable digests. Installation downloads a fixed HTTPS release asset, verifies both hashes, and copies only the fixed executable and LICENSE members (never arbitrary tar paths). The Apache-2.0 license is retained alongside the binary. Supported platforms: Linux amd64/arm64 and Windows amd64; other hosts can use the Linux backend container.

The executable lives at `backend/.tools/oasdiff/oasdiff[.exe]`, excluded from Git and the Docker build context. CI installs it before pytest; the Docker build installs it as root before switching to the unprivileged application user. Comparisons recheck the executable hash before launching it. There is no PATH lookup, user-supplied executable, automatic runtime download or version fallback. To upgrade, review upstream changes/security advisories, update both digests, inspect output schema changes and rerun fixtures and failure tests on supported platforms.

## Output and identity

`ComparisonResult` contains engine/version, normalization version `1`, SHA-256 hashes of canonical input documents, and sorted `ContractChange` records. Each record preserves the oasdiff rule, summary, operation, path, section and typed raw evidence, including disclaimers and shared-schema information when present.

| oasdiff level | Normalized severity |
| --- | --- |
| 3 / ERR | `breaking` |
| 2 / WARN | `potentially_breaking` |
| 1 / INFO | `non_breaking` |

IDs hash the pinned version, normalization version, rule, operation, path, section and engine fingerprint. They do not depend on record order, temporary directory names or source line numbers. IDs identify a finding; the input hashes identify the compared pair. Changing the engine or normalization version intentionally changes IDs. Conflicting records with the same identity fail closed.

Source locations refer to sorted, indented **canonical JSON**, not the original uploaded YAML/JSON layout. `baseline.json` and `candidate.json` are logical source names; temporary host paths are never returned. Full input hashes permit subsequent persistence/API work to associate evidence with the exact pair.

The [upstream changelog semantics](https://github.com/oasdiff/oasdiff/blob/v1.37.0/docs/BREAKING-CHANGES.md) cover consumer-relevant changes, not every textual difference. Documentation-only edits can yield an empty changelog. An empty result does not prove consumer compatibility, and the wrapper does not infer affected code or migration advice. Cross-version conversion and optional flattening are not enabled.

## Boundaries and errors

- Reapply the upload tree/reference policy before launching: only local JSON Pointer refs; no remote/file references, schema rebasing or dynamic references. Full OpenAPI schema validation remains the upload boundary's responsibility.
- At most 1 MiB of canonical JSON per input (formatting expansion can reject a previously accepted upload), 40 nesting levels and 20,000 nodes. No user-provided paths or URLs are passed to the CLI.
- Fresh temporary directory with fixed input filenames and an explicit empty config file. No inherited provider credentials, proxy variables, HOME or oasdiff configuration. No shell, fetch, browser-open or hosted-review options.
- Explicit `--allow-external-refs=false`, English JSON changelog at INFO level. Full structured output validation rejects unknown fields, invalid severities, missing fingerprints, wrong source names and malformed JSON.
- At most two simultaneous runs per application process, ten seconds per child, 2 MiB combined stdout/stderr, and 2,000 returned findings. Overflow and timeout kill/reap the child; both pipes are drained concurrently and temporary files are removed. Stderr never appears in errors.
- Go gets `GOMAXPROCS=2` and a 128 MiB soft memory target. This is **not a hard OS memory sandbox**; deployment must provide container memory/CPU limits before handling untrusted public traffic. The application remains local and single-user.

`ComparisonError.code` is one of `invalid_input`, `engine_unavailable`, `engine_checksum_mismatch`, `busy`, `timeout`, `output_limit`, `engine_failed`, or `invalid_output`. Failures never become an empty successful comparison. There is no automatic retry. CI includes real subprocess timeout/stdout/stderr overflow tests, modified-binary rejection, and installer checksum/archive tests using synthetic data.
