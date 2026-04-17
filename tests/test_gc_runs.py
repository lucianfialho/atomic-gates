"""
Regression test for issue #26 — garbage-collect runs abandoned mid-flight.

Without GC, runs in `status: running` whose agent was killed sit in the
.gates/runs/ dir forever. 4/31 such runs observed in analytics-copilot
+ gmp-cli, stuck 64–91h.

Run:
    python3 -m unittest tests.test_gc_runs
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from lib.gc_runs import gc_stale_runs, parse_ttl  # noqa: E402


def _write_run(project: Path, run_id: str, updated_at: datetime, status: str = "running") -> Path:
    runs_dir = project / ".gates" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    yml = runs_dir / f"{run_id}.yaml"
    data = {
        "run_id": run_id,
        "skill_id": "fake:skill",
        "status": status,
        "current_state": "probe",
        "inputs": {},
        "created_at": updated_at.isoformat(),
        "updated_at": updated_at.isoformat(),
        "history": [{"state": "probe", "entered_at": updated_at.isoformat()}],
    }
    yml.write_text(yaml.safe_dump(data, sort_keys=False))
    return yml


class TestGcRuns(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_stale_running_run_marked_abandoned(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(hours=48)
        yml = _write_run(self.tmp, "stale01", past)

        marked = gc_stale_runs(self.tmp, parse_ttl("24h"))

        self.assertEqual(len(marked), 1)
        self.assertEqual(marked[0]["run_id"], "stale01")
        self.assertGreater(marked[0]["age_hours"], 24)

        saved = yaml.safe_load(yml.read_text())
        self.assertEqual(
            saved["status"], "abandoned",
            "stale running run must be rewritten as abandoned",
        )

    def test_fresh_running_run_untouched(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(minutes=30)
        yml = _write_run(self.tmp, "fresh01", recent)

        marked = gc_stale_runs(self.tmp, parse_ttl("24h"))

        self.assertEqual(marked, [], "fresh run must not be touched")
        saved = yaml.safe_load(yml.read_text())
        self.assertEqual(saved["status"], "running")

    def test_terminal_run_never_marked(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(days=30)
        yml = _write_run(self.tmp, "done01", past, status="terminal")

        marked = gc_stale_runs(self.tmp, parse_ttl("24h"))

        self.assertEqual(marked, [], "terminal runs are not gc targets")
        saved = yaml.safe_load(yml.read_text())
        self.assertEqual(saved["status"], "terminal")

    def test_dry_run_does_not_rewrite(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(hours=48)
        yml = _write_run(self.tmp, "stale02", past)

        marked = gc_stale_runs(self.tmp, parse_ttl("24h"), dry_run=True)

        self.assertEqual(len(marked), 1)
        saved = yaml.safe_load(yml.read_text())
        self.assertEqual(
            saved["status"], "running",
            "dry-run must not modify the file",
        )

    def test_parse_ttl(self) -> None:
        self.assertEqual(parse_ttl("30s"), 30)
        self.assertEqual(parse_ttl("15m"), 900)
        self.assertEqual(parse_ttl("2h"), 7200)
        self.assertEqual(parse_ttl("1d"), 86400)
        with self.assertRaises(ValueError):
            parse_ttl("garbage")


if __name__ == "__main__":
    unittest.main()
