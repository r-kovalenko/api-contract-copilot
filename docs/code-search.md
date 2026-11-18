# Exact code search checkpoint — #35

The backend `RepositorySearch` service searches for case-sensitive, literal text in configured local source repositories. It returns repository-relative paths, one-based line numbers, bounded snippets, file SHA-256 hashes, and stable evidence IDs. It does not infer semantic dependencies or call an LLM. API/tool-registry integration is the next task (#36); the UI's Analyze impact action remains unavailable.

## Run the synthetic demo

With the Docker application already running, rebuild the backend for this change, then run:

```sh
docker compose up -d --build backend
docker compose exec backend python demo_code_search.py
```

The demo creates temporary synthetic consumer code and searches for `full_name`. Expect one match in `customer_client.py`, line 2, with snippet `    return customer["full_name"]`. It needs no database access, API credentials, or mounted repositories. Temporary data is removed afterward.

For a host Python environment, install backend dependencies and ripgrep using the [upstream installation instructions](https://github.com/BurntSushi/ripgrep#installation). Verify `rg --version`, then from the repository root run:

```sh
python backend/demo_code_search.py
python -m pytest backend/tests/test_code_search.py
```

Docker and CI install ripgrep from the OS package repository. The executable path is resolved from the trusted process PATH when the service is constructed; callers cannot select executables or flags. This checkpoint does not pin a cross-platform binary checksum or promise engine-version-independent behavior.

## Configure a repository

From a backend Python process, application-owned configuration maps a repository ID to an absolute path:

```python
from pathlib import Path
from app.code_search import RepositorySearch, SearchRequest

service = RepositorySearch({"consumer": Path("C:/Projects/api-consumer-demo")})
result = service.search(SearchRequest(
    repository="consumer", query="full_name", scope="", limit=50,
))
print(result.model_dump_json(indent=2))
```

Use the actual absolute checkout path on your platform. In containers, paths refer to the container filesystem; this step does not mount or clone repositories automatically. Repository mappings and the optional executable override are trusted application configuration, never model/user request fields. Future API integration must authorize the repository ID against the selected project/principal.

`scope` optionally narrows the search to a forward-slash relative file or directory, for example `src` or `customer_client.py`. Absolute paths, drive letters, backslashes, empty path components, `.` and `..` are rejected. Unknown IDs are rejected. Symlink/reparse-point scopes are rejected; encountered symlinks, junctions and hard-linked files are excluded.

## Evidence and limits

- Query: 1–200 characters, a nonblank single-line literal. Flag-like strings, shell syntax and regex characters are data. No shell, external preprocessors, repository executables, or ripgrep configuration is invoked.
- Eligible files: UTF-8 text with source extensions `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.go`, `.java`, `.cs`, `.php`, `.rb`, `.rs`, `.kt`, `.swift`, `.c`, `.cpp`, `.h`, `.hpp`, `.sql`. NUL-containing binary and invalid UTF-8 files are skipped.
- Excluded: dotfiles/directories (including `.env`, `.git`, `.aws`), `node_modules`, `vendor`, `dist`, `build`, `__pycache__`, `venv`, `coverage`, and names containing `secret`, `credential`, `private_key`, `id_rsa`, or `id_ed25519` (case insensitive). Extensions outside the allowlist, including credential JSON/PEM files, are not copied. This is an explicit application policy, not `.gitignore` interpretation. A custom gitignored `.py` file can still be eligible. Name-based exclusions cannot detect credentials hardcoded in otherwise eligible source; configure only synthetic/sanitized repositories for this preview.
- Source files are copied to a private temporary search tree before ripgrep runs. Files over 256 KiB are skipped; a corpus exceeding 8 MiB, 1,000 eligible files, or 5,000 traversed/queued entries fails with `corpus_limit`, without partial evidence. `searched_files` and `skipped_entries` describe the restricted corpus, not the entire repository.
- At most two concurrent searches per process. Snapshot creation and subprocess execution share a 10-second deadline, checked between filesystem operations. Use local, trusted, stable checkouts; a blocked filesystem read is not forcibly interruptible. Do not configure network filesystems or repositories concurrently modified by untrusted processes. This is not a sandbox against another process racing filesystem mutations; detected file replacement/modification fails with `repository_changed`.
- Combined stdout/stderr is bounded to 2 MiB. Timeout or overflow kills and reaps the subprocess, and temporary files are cleaned up. Environment variables, raw stderr and absolute repository paths are not included in error messages.
- Results are sorted by relative path and line. Default limit is 50, maximum 100; `truncated` explicitly indicates more matching lines. Each snippet is at most 1,000 characters, centered near the first literal match. `snippet_start_column` is its one-based Unicode-character column; `snippet_truncated` indicates omitted line content. Evidence IDs bind repository ID, relative path, file hash and line number. File content changes invalidate prior IDs. Results represent a per-file snapshot, not an atomic Git commit snapshot.

No matches is a successful empty result. It is not proof that a change has no consumer impact: excluded files, dynamic usages and semantic relationships are outside this exact-search scope.

Safe failure codes include `unknown_repository`, `invalid_repository`, `unsafe_scope`, `repository_unavailable`, `repository_changed`, `corpus_limit`, `busy`, `timeout`, `engine_unavailable`, `engine_failed`, `output_limit`, and `invalid_output`. Invalid typed request fields raise validation errors before search execution. Failures do not return partial hits.
