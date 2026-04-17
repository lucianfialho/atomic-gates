"""
Regression test for issue #24 — gate_failures must be persisted to
run["history"][-1] when a state's schema validation rejects the output.

Without the fix, the retrospective analyzer (validation/analyze_runs.py)
is blind: every terminal run reports 0 failures, so H1 cannot be measured.

Run:
    python3 -m unittest tests.test_gate_failures_persisted
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from lib.runner import (  # noqa: E402
    _load_and_validate_skill_yaml,
    _write_yaml,
    create_run,
    handle_existing_run,
    load_run,
    run_output_path,
)

FIXTURE = Path(__file__).parent / "fixtures" / "strict-skill"


class TestGateFailuresPersisted(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        self.project = self.tmpdir
        # plugin_root is the atomic-gates checkout (has schemas/ + templates/)
        self.plugin_root = REPO
        self.machine = _load_and_validate_skill_yaml(
            FIXTURE / "skill.yaml", self.plugin_root
        )
        # Resolve output_schema relative paths against the fixture dir.
        self.machine["_origin_plugin_root"] = str(FIXTURE)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_schema_violation_persists_to_history(self) -> None:
        run = create_run(self.project, self.machine, arguments={})
        out = run_output_path(self.project, run["run_id"], "probe")
        out.parent.mkdir(parents=True, exist_ok=True)
        _write_yaml(out, {"verdict": "maybe"})  # outside enum

        handle_existing_run(run, self.machine, self.plugin_root, self.project)

        saved = load_run(self.project, run["run_id"])
        self.assertIsNotNone(saved, "run file should exist")
        self.assertEqual(
            saved["current_state"], "probe",
            "runner must NOT advance when schema fails",
        )
        last = saved["history"][-1]
        self.assertIn(
            "gate_failures", last,
            "issue #24: gate_failures must be persisted to history",
        )
        self.assertTrue(
            last["gate_failures"],
            "gate_failures must be non-empty when validation rejected output",
        )

    def test_valid_output_advances_without_failures(self) -> None:
        run = create_run(self.project, self.machine, arguments={})
        out = run_output_path(self.project, run["run_id"], "probe")
        out.parent.mkdir(parents=True, exist_ok=True)
        _write_yaml(out, {"verdict": "pass"})

        handle_existing_run(run, self.machine, self.plugin_root, self.project)

        saved = load_run(self.project, run["run_id"])
        self.assertEqual(
            saved["current_state"], "done",
            "runner must advance to done on valid output",
        )
        self.assertEqual(saved["status"], "terminal")


if __name__ == "__main__":
    unittest.main()
