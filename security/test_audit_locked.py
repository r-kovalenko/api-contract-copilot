import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from audit_locked import audit


def response(code=0, vulnerabilities=None):
    return subprocess.CompletedProcess(
        [],
        code,
        json.dumps(
            {
                "dependencies": [
                    {
                        "name": "synthetic",
                        "version": "1",
                        "vulns": vulnerabilities or [],
                    }
                ]
            }
        ),
        "",
    )


class AuditTests(unittest.TestCase):
    def run_audit(self, events):
        runner = Mock(side_effect=events)
        with tempfile.TemporaryDirectory() as directory:
            result = audit("requirements.txt", Path(directory), runner, Mock())
            self.assertTrue(list(Path(directory).glob("*.log")))
        return result, runner.call_count

    def test_clean(self):
        self.assertEqual(self.run_audit([response()]), (0, 1))

    def test_findings_never_retry_even_with_zero_exit_code(self):
        for code in (0, 1):
            self.assertEqual(
                self.run_audit([response(code, [{"id": "TEST-1"}])]), (1, 1)
            )

    def test_temporary_failure_can_recover(self):
        broken = subprocess.CompletedProcess([], 1, "", "service unavailable")
        self.assertEqual(self.run_audit([broken, response()]), (0, 2))

    def test_permanent_failure_is_bounded(self):
        broken = subprocess.CompletedProcess([], 1, "", "service unavailable")
        self.assertEqual(self.run_audit([broken] * 3), (2, 3))

    def test_timeout_can_recover(self):
        self.assertEqual(
            self.run_audit([subprocess.TimeoutExpired("audit", 180), response()]),
            (0, 2),
        )

    def test_empty_malformed_skipped_or_failed_reports_never_pass(self):
        for raw in (
            "{}",
            "null",
            '{"dependencies": []}',
            '{"dependencies": [null]}',
            '{"dependencies": [{"name": "x", "skip_reason": "unavailable"}]}',
        ):
            broken = subprocess.CompletedProcess([], 0, raw, "")
            self.assertEqual(self.run_audit([broken] * 3), (2, 3))
        self.assertEqual(self.run_audit([response(1)] * 3), (2, 3))


if __name__ == "__main__":
    unittest.main()
