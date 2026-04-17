"""
Regression test for issue #28 — atomic-gate decisions must be logged to
<project>/.gates/hook-log.jsonl so we can retrospectively ask:
  how often did any gate fire? block? on which tool?

Run:
    python3 -m unittest tests.test_gate_log
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "lib"))

from gate_log import log_decision  # noqa: E402


class TestGateLog(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self._prev = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.tmp)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)
        if self._prev is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = self._prev

    def _read_log(self) -> list[dict]:
        f = self.tmp / ".gates" / "hook-log.jsonl"
        if not f.exists():
            return []
        return [json.loads(line) for line in f.read_text().splitlines() if line.strip()]

    def test_log_decision_appends(self) -> None:
        log_decision("metadata", "Bash", "allow", "not a git commit")
        log_decision("metadata", "Bash", "block", "stale summary.yaml")

        entries = self._read_log()
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["gate"], "metadata")
        self.assertEqual(entries[0]["decision"], "allow")
        self.assertEqual(entries[1]["decision"], "block")
        self.assertIn("ts", entries[0])

    def test_log_decision_no_project_dir_silent(self) -> None:
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        # Must not raise, must not create any file anywhere.
        log_decision("metadata", "Bash", "allow", "whatever")
        self.assertFalse((self.tmp / ".gates" / "hook-log.jsonl").exists())

    def test_log_decision_truncates_long_reason(self) -> None:
        long_reason = "x" * 2000
        log_decision("role", "Edit", "block", long_reason)
        entries = self._read_log()
        self.assertLessEqual(len(entries[0]["reason"]), 500)


if __name__ == "__main__":
    unittest.main()
