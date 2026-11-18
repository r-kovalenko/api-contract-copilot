"""Literal search over a bounded snapshot of configured, locally trusted repositories."""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import threading
import time
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_FILE_BYTES = 256 * 1024
MAX_CORPUS_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 5000
MAX_FILES = 1000
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
TIMEOUT_SECONDS = 10
EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".java",
    ".cs",
    ".php",
    ".rb",
    ".rs",
    ".kt",
    ".swift",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".sql",
}
EXCLUDED_DIRS = {"node_modules", "vendor", "dist", "build", "__pycache__", "venv", "coverage"}
_slots = threading.BoundedSemaphore(2)


class SearchError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Code search failed: {code}.")


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    repository: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    query: str = Field(min_length=1, max_length=200)
    scope: str = Field(default="", max_length=500)
    limit: int = Field(default=50, ge=1, le=100, strict=True)

    @field_validator("query")
    @classmethod
    def single_line(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Search must be a nonempty single-line literal")
        return value

    @field_validator("scope")
    @classmethod
    def relative_scope(cls, value: str) -> str:
        if value and (
            value.startswith("/")
            or "\\" in value
            or ":" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or any(ord(char) < 32 for char in value)
        ):
            raise ValueError("Scope must be a repository-relative path")
        return value


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    repository: str
    path: str
    line: int = Field(ge=1)
    snippet: str
    snippet_truncated: bool
    snippet_start_column: int = Field(ge=1)
    file_sha256: str


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    repository: str
    query: str
    scope: str
    hits: list[SearchHit]
    truncated: bool
    searched_files: int
    skipped_entries: int


def linked(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def excluded(path: Path) -> bool:
    name = path.name.lower()
    return (
        name.startswith(".")
        or name in EXCLUDED_DIRS
        or any(
            token in name
            for token in ("secret", "credential", "private_key", "id_rsa", "id_ed25519")
        )
    )


def snapshot(root: Path, scope: str, destination: Path, deadline: float):
    target = root
    for part in PurePosixPath(scope).parts:
        target /= part
        if linked(target) or excluded(target):
            raise SearchError("unsafe_scope")
    if not target.resolve().is_relative_to(root):
        raise SearchError("unsafe_scope")
    pending = [target]
    manifest: dict[str, str] = {}
    entries = total = skipped = 0
    while pending:
        if time.monotonic() >= deadline:
            raise SearchError("timeout")
        path = pending.pop()
        entries += 1
        if entries > MAX_ENTRIES:
            raise SearchError("corpus_limit")
        if excluded(path) or linked(path):
            skipped += 1
            continue
        if not path.resolve().is_relative_to(root):
            raise SearchError("unsafe_scope")
        info = path.stat()
        if stat.S_ISDIR(info.st_mode):
            with os.scandir(path) as children:
                for child in children:
                    if len(pending) + entries >= MAX_ENTRIES:
                        raise SearchError("corpus_limit")
                    pending.append(Path(child.path))
            continue
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or path.suffix.lower() not in EXTENSIONS
            or info.st_size > MAX_FILE_BYTES
        ):
            skipped += 1
            continue
        # O_NOFOLLOW protects the leaf where supported. Configured checkouts must not
        # be concurrently modified by untrusted processes; parent paths are checked too.
        descriptor = os.open(
            path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        )
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                raise SearchError("repository_changed")
            data = stream.read(MAX_FILE_BYTES + 1)
        if (
            len(data) > MAX_FILE_BYTES
            or linked(path)
            or path.stat().st_mtime_ns != info.st_mtime_ns
        ):
            raise SearchError("repository_changed")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            skipped += 1
            continue
        if b"\0" in data:
            skipped += 1
            continue
        total += len(data)
        if total > MAX_CORPUS_BYTES or len(manifest) >= MAX_FILES:
            raise SearchError("corpus_limit")
        relative = path.relative_to(root).as_posix()
        copied = destination / relative
        copied.parent.mkdir(parents=True, exist_ok=True)
        copied.write_bytes(data)
        manifest[relative] = hashlib.sha256(data).hexdigest()
    return manifest, skipped


def run_rg(executable: Path, directory: Path, query: str, deadline: float) -> bytes:
    args = [
        str(executable),
        "--json",
        "--fixed-strings",
        "--case-sensitive",
        "--no-config",
        "--no-ignore",
        "--hidden",
        "--sort",
        "path",
        "--threads",
        "1",
        "--",
        query,
        ".",
    ]
    env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    try:
        process = subprocess.Popen(
            args,
            cwd=directory,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except OSError:
        raise SearchError("engine_unavailable") from None
    overflow = threading.Event()
    lock = threading.Lock()
    total = 0
    output = bytearray()

    def drain(pipe, keep):
        nonlocal total
        with pipe:
            while chunk := pipe.read(8192):
                with lock:
                    total += len(chunk)
                    if total > MAX_OUTPUT_BYTES:
                        overflow.set()
                        return
                    if keep:
                        output.extend(chunk)

    threads = [
        threading.Thread(target=drain, args=(pipe, keep), daemon=True)
        for pipe, keep in [(process.stdout, True), (process.stderr, False)]
    ]
    for thread in threads:
        thread.start()
    failure = None
    try:
        while process.poll() is None:
            if overflow.is_set():
                failure = "output_limit"
                break
            if time.monotonic() >= deadline:
                failure = "timeout"
                break
            time.sleep(0.01)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        for thread in threads:
            thread.join()
    if overflow.is_set():
        raise SearchError("output_limit")
    if failure:
        raise SearchError(failure)
    if process.returncode not in (0, 1):
        raise SearchError("engine_failed")
    return bytes(output)


def normalize(
    raw: bytes, request: SearchRequest, manifest: dict[str, str], skipped: int
) -> SearchResult:
    hits = []
    if len(raw) > MAX_OUTPUT_BYTES:
        raise SearchError("output_limit")
    try:
        for line in raw.splitlines():
            record = json.loads(line)
            if record["type"] != "match":
                if record["type"] not in {"begin", "end", "summary"}:
                    raise ValueError
                continue
            data = record["data"]
            path = data["path"]["text"].replace("\\", "/")
            if path.startswith("./"):
                path = path[2:]
            if path not in manifest:
                raise ValueError
            number = data["line_number"]
            snippet = data["lines"]["text"].rstrip("\r\n")
            if type(number) is not int or number < 1 or request.query not in snippet:
                raise ValueError
            identity = json.dumps(
                [request.repository, path, manifest[path], number], ensure_ascii=False
            )
            start = max(0, snippet.index(request.query) - 200)
            hits.append(
                SearchHit(
                    id=hashlib.sha256(identity.encode()).hexdigest(),
                    repository=request.repository,
                    path=path,
                    line=number,
                    snippet=snippet[start : start + 1000],
                    snippet_truncated=start > 0 or len(snippet) > start + 1000,
                    snippet_start_column=start + 1,
                    file_sha256=manifest[path],
                )
            )
    except (ValueError, KeyError, TypeError, UnicodeError, AttributeError):
        raise SearchError("invalid_output") from None
    hits.sort(key=lambda hit: (hit.path, hit.line))
    return SearchResult(
        repository=request.repository,
        query=request.query,
        scope=request.scope,
        hits=hits[: request.limit],
        truncated=len(hits) > request.limit,
        searched_files=len(manifest),
        skipped_entries=skipped,
    )


class RepositorySearch:
    """Mappings and executable are trusted application configuration, never tool arguments."""

    def __init__(self, repositories: dict[str, Path], executable: Path | None = None):
        self.repositories = dict(repositories)
        found = executable or shutil.which("rg")
        self.executable = Path(found).resolve() if found else None

    def search(self, request: SearchRequest) -> SearchResult:
        if request.repository not in self.repositories:
            raise SearchError("unknown_repository")
        if not _slots.acquire(blocking=False):
            raise SearchError("busy")
        try:
            root = self.repositories[request.repository]
            if not root.is_absolute() or linked(root) or not root.is_dir():
                raise SearchError("invalid_repository")
            root = root.resolve()
            if not self.executable or not self.executable.is_file():
                raise SearchError("engine_unavailable")
            deadline = time.monotonic() + TIMEOUT_SECONDS
            with tempfile.TemporaryDirectory(prefix="copilot-search-") as temporary:
                directory = Path(temporary)
                manifest, skipped = snapshot(root, request.scope, directory, deadline)
                raw = (
                    run_rg(self.executable, directory, request.query, deadline) if manifest else b""
                )
                return normalize(raw, request, manifest, skipped)
        except OSError:
            raise SearchError("repository_unavailable") from None
        finally:
            _slots.release()
