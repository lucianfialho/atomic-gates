"""
Regression test for issue #25 — skeleton skills produced by
lib/import_skill.py (meta headings like "Usage", "Overview") must not
trap the runner forever waiting for an output file the state has no
reason to produce.

Observed in the wild: run 3d0b0ca5b143 (claude-dev-pipeline:check-security)
stuck 64h in state `usage` in analytics-copilot/.gates/runs/.

Run:
    python3 -m unittest tests.test_skeleton_no_trap
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
    create_run,
    handle_existing_run,
    load_run,
)

FIXTURE = Path(__file__).parent / "fixtures" / "skeleton-skill"


class TestSkeletonNoTrap(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        self.project = self.tmpdir
        self.plugin_root = REPO
        self.machine = _load_and_validate_skill_yaml(
            FIXTURE / "skill.yaml", self.plugin_root
        )
        self.machine["_origin_plugin_root"] = str(FIXTURE)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_state_without_schema_or_gate_auto_advances(self) -> None:
        run = create_run(self.project, self.machine, arguments={})
        # Deliberately DO NOT write <run_id>/usage.output.yaml.

        handle_existing_run(run, self.machine, self.plugin_root, self.project)

        saved = load_run(self.project, run["run_id"])
        self.assertIsNotNone(saved)
        self.assertEqual(
            saved["current_state"], "done",
            "issue #25: skeleton state with no output_schema + no gate "
            "must advance — nothing to validate, nothing to wait for.",
        )
        self.assertEqual(saved["status"], "terminal")


if __name__ == "__main__":
    unittest.main()
