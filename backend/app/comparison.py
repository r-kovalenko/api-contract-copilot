"""Deterministic, offline comparison of already validated contract specifications."""

import hashlib
import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.contract_validation import MAX_BYTES, InvalidContract, inspect_tree, unique_object
from app.oasdiff_pin import PINS, VERSION, binary_path, platform_key

TIMEOUT_SECONDS = 10
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_CHANGES = 2000
NORMALIZATION_VERSION = 1
_slots = threading.BoundedSemaphore(2)


class ComparisonError(RuntimeError):
    """Safe error code for a future API boundary; never includes stderr or document text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"Contract comparison failed: {code}.")


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    file: Literal["baseline.json", "candidate.json"]
    line: int = Field(default=0, ge=0)
    column: int = Field(default=0, ge=0)
    endLine: int = Field(default=0, ge=0)
    endColumn: int = Field(default=0, ge=0)


class SharedSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = ""
    properties: list[str] = Field(max_length=MAX_CHANGES)
    count: int = Field(default=0, ge=0)
    cyclic: bool = False


class EngineChange(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=16000)
    level: int = Field(ge=1, le=3, strict=True)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{12}$")
    operation: str = Field(default="", max_length=30)
    operationId: str = Field(default="", max_length=2000)
    path: str = Field(default="", max_length=4000)
    section: str = Field(default="", max_length=100)
    comment: str = Field(default="", max_length=16000)
    disclaimers: list[str] = Field(default_factory=list, max_length=100)
    sharedSchema: SharedSchema | None = None
    baseSource: Source | None = None
    revisionSource: Source | None = None


class ContractChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    rule_id: str
    severity: Literal["breaking", "potentially_breaking", "non_breaking"]
    summary: str
    operation: str
    path: str
    section: str
    evidence: EngineChange


class ComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    engine: Literal["oasdiff"] = "oasdiff"
    engine_version: str = VERSION
    normalization_version: int = NORMALIZATION_VERSION
    baseline_sha256: str
    candidate_sha256: str
    changes: list[ContractChange]


def encode_spec(spec: dict) -> bytes:
    try:
        if not isinstance(spec, dict):
            raise ValueError
        inspect_tree(spec)  # Reject remote/file refs, rebasing, cycles and excessive complexity.
        if spec.get("openapi", "").split(".")[:2] not in [["3", "0"], ["3", "1"], ["3", "2"]]:
            raise ValueError
        output = bytearray()
        for chunk in json.JSONEncoder(sort_keys=True, indent=2, ensure_ascii=False).iterencode(
            spec
        ):
            output.extend(chunk.encode("utf-8"))
            if len(output) > MAX_BYTES:
                raise ValueError
        return bytes(output)
    except (InvalidContract, ValueError, TypeError, AttributeError, RecursionError):
        raise ComparisonError("invalid_input") from None


def verified_binary() -> Path:
    try:
        executable = binary_path()
        if executable.is_symlink() or not executable.is_file():
            raise ComparisonError("engine_unavailable")
        with executable.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != PINS[platform_key()][1]:
            raise ComparisonError("engine_checksum_mismatch")
        return executable
    except (OSError, RuntimeError) as exc:
        if isinstance(exc, ComparisonError):
            raise
        raise ComparisonError("engine_unavailable") from None


def run_engine(executable: Path, directory: Path) -> bytes:
    """Drain both pipes concurrently with a combined cap, kill/reap on timeout or overflow."""
    env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    env.update({"GOMEMLIMIT": "128MiB", "GOMAXPROCS": "2"})
    args = [
        str(executable),
        "changelog",
        "baseline.json",
        "candidate.json",
        "--format",
        "json",
        "--level",
        "INFO",
        "--lang",
        "en",
        "--allow-external-refs=false",
        "--config",
        "config.json",
    ]
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
        raise ComparisonError("engine_unavailable") from None
    overflow = threading.Event()
    lock = threading.Lock()
    total = 0
    stdout = bytearray()

    def drain(pipe, keep: bool) -> None:
        nonlocal total
        with pipe:
            while chunk := pipe.read(8192):
                with lock:
                    total += len(chunk)
                    if total > MAX_OUTPUT_BYTES:
                        overflow.set()
                        return
                    if keep:
                        stdout.extend(chunk)

    threads = [
        threading.Thread(target=drain, args=(pipe, keep), daemon=True)
        for pipe, keep in [(process.stdout, True), (process.stderr, False)]
    ]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + TIMEOUT_SECONDS
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
        raise ComparisonError("output_limit")
    if failure:
        raise ComparisonError(failure)
    if process.returncode != 0:
        raise ComparisonError("engine_failed")
    return bytes(stdout)


def normalize(raw: bytes) -> list[ContractChange]:
    try:
        if len(raw) > MAX_OUTPUT_BYTES:
            raise ValueError
        records = json.loads(raw, object_pairs_hook=unique_object)
        if not isinstance(records, list) or len(records) > MAX_CHANGES:
            raise ValueError
        changes: dict[str, ContractChange] = {}
        for record in records:
            item = EngineChange.model_validate(record)
            if (item.baseSource and item.baseSource.file != "baseline.json") or (
                item.revisionSource and item.revisionSource.file != "candidate.json"
            ):
                raise ValueError
            # Ignore temporary locations/order; retain the engine's field-specific fingerprint.
            identity = json.dumps(
                [
                    VERSION,
                    NORMALIZATION_VERSION,
                    item.id,
                    item.operation,
                    item.path,
                    item.section,
                    item.fingerprint,
                ],
                ensure_ascii=False,
            )
            change_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            change = ContractChange(
                id=change_id,
                rule_id=item.id,
                severity={1: "non_breaking", 2: "potentially_breaking", 3: "breaking"}[item.level],
                summary=item.text,
                operation=item.operation,
                path=item.path,
                section=item.section,
                evidence=item,
            )
            if change_id in changes and changes[change_id] != change:
                raise ValueError
            changes[change_id] = change
        return sorted(changes.values(), key=lambda change: change.id)
    except (ValueError, TypeError, UnicodeError, RecursionError, ValidationError):
        raise ComparisonError("invalid_output") from None


def compare_contracts(baseline: dict, candidate: dict) -> ComparisonResult:
    if not _slots.acquire(blocking=False):
        raise ComparisonError("busy")
    try:
        base, revision = encode_spec(baseline), encode_spec(candidate)
        executable = verified_binary()
        with tempfile.TemporaryDirectory(prefix="copilot-diff-") as temporary:
            directory = Path(temporary)
            (directory / "baseline.json").write_bytes(base)
            (directory / "candidate.json").write_bytes(revision)
            (directory / "config.json").write_text("{}", encoding="utf-8")
            changes = normalize(run_engine(executable, directory))
        return ComparisonResult(
            baseline_sha256=hashlib.sha256(base).hexdigest(),
            candidate_sha256=hashlib.sha256(revision).hexdigest(),
            changes=changes,
        )
    finally:
        _slots.release()
