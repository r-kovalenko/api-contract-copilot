"""Fail closed on findings; retry operational failures without suppressing audit results."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def classify(result):
    try:
        report = json.loads(result.stdout)
        dependencies = report["dependencies"]
        if not isinstance(dependencies, list) or not dependencies:
            return "error"
        # Even partial output containing findings must fail immediately.
        if any(isinstance(d, dict) and d.get("vulns") for d in dependencies):
            return "vulnerable"
        if any(
            not isinstance(d, dict)
            or not isinstance(d.get("vulns"), list)
            or not d.get("name")
            or not d.get("version")
            or "skip_reason" in d
            for d in dependencies
        ):
            return "error"
        return "clean" if result.returncode == 0 else "error"
    except (ValueError, KeyError, TypeError):
        return "error"


def audit(requirements, reports, runner=subprocess.run, sleep=time.sleep):
    reports.mkdir(parents=True, exist_ok=True)
    name = str(requirements).replace("/", "_").replace("\\", "_")
    for attempt in range(1, 4):
        command = [
            sys.executable,
            "-m",
            "pip_audit",
            "--strict",
            "--disable-pip",
            "--no-deps",
            "--timeout",
            "30",
            "--progress-spinner",
            "off",
            "--format",
            "json",
            "-r",
            str(requirements),
        ]
        try:
            result = runner(
                command, capture_output=True, text=True, timeout=180, check=False
            )
            state = classify(result)
            (reports / f"{name}.{attempt}.json").write_text(
                result.stdout, encoding="utf-8"
            )
            (reports / f"{name}.{attempt}.log").write_text(
                result.stderr, encoding="utf-8"
            )
        except (subprocess.TimeoutExpired, OSError) as error:
            state = "error"
            (reports / f"{name}.{attempt}.log").write_text(str(error), encoding="utf-8")
        print(f"{requirements}: attempt {attempt}/3: {state}", flush=True)
        if state == "clean":
            return 0
        if state == "vulnerable":
            print(
                f"Vulnerabilities found. See {reports}; update affected locks.",
                file=sys.stderr,
            )
            return 1
        if attempt < 3:
            sleep(5 * attempt)
    print(
        f"Audit unavailable or incomplete for {requirements}; failing closed.",
        file=sys.stderr,
    )
    return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requirements", nargs="+")
    parser.add_argument("--reports", type=Path, default=Path("security-reports"))
    args = parser.parse_args()
    results = [audit(path, args.reports) for path in args.requirements]
    return max(results)


if __name__ == "__main__":
    raise SystemExit(main())
