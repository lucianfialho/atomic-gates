"""
Regression test for the Stop hook — agent cannot end a session while a
top-level state-machine run is still in flight.

Run:
    python3 -m unittest tests.test_stop_enforce
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

from lib.stop_enforce import find_unfinished_runs  # noqa: E402


def _write_run(project: Path, run_id: str, status: str, age_hours: float,
               parent: str | None = None) -> Path:
    d = project / ".gates" / "runs"
    d.mkdir(parents=True, exist_ok=True)
    when = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    data: dict = {
        "run_id": run_id,
        "skill_id": "fake:skill",
        "status": status,
        "current_state": "probe",
        "inputs": {},
        "created_at": when.isoformat(),
        "updated_at": when.isoformat(),
        "history": [{"state": "probe", "entered_at": when.isoformat()}],
    }
    if parent:
        data["parent_run_id"] = parent
        data["parent_skill_id"] = "fake:parent"
        data["parent_state"] = "delegate"
    yml = d / f"{run_id}.yaml"
    yml.write_text(yaml.safe_dump(data, sort_keys=False))
    return yml


class TestStopEnforce(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_no_gates_dir_allows_stop(self) -> None:
        self.assertEqual(find_unfinished_runs(self.tmp), [])

    def test_no_runs_allows_stop(self) -> None:
        (self.tmp / ".gates" / "runs").mkdir(parents=True)
        self.assertEqual(find_unfinished_runs(self.tmp), [])

    def test_terminal_run_does_not_block(self) -> None:
        _write_run(self.tmp, "done01", "terminal", age_hours=0.1)
        self.assertEqual(find_unfinished_runs(self.tmp), [])

    def test_fresh_running_toplevel_blocks(self) -> None:
        _write_run(self.tmp, "live01", "running", age_hours=0.2)
        unfinished = find_unfinished_runs(self.tmp)
        self.assertEqual(len(unfinished), 1)
        self.assertEqual(unfinished[0]["run_id"], "live01")

    def test_running_subrun_does_not_block(self) -> None:
        # Sub-runs are the parent's responsibility, not Stop's.
        _write_run(self.tmp, "sub01", "running", age_hours=0.1, parent="parent01")
        self.assertEqual(find_unfinished_runs(self.tmp), [])

    def test_stale_running_does_not_block(self) -> None:
        # >24h stale: gc_runs.py territory, not Stop.
        _write_run(self.tmp, "stale01", "running", age_hours=48)
        self.assertEqual(find_unfinished_runs(self.tmp), [])

    def test_abandoned_does_not_block(self) -> None:
        _write_run(self.tmp, "abn01", "abandoned", age_hours=0.5)
        self.assertEqual(find_unfinished_runs(self.tmp), [])


if __name__ == "__main__":
    unittest.main()
