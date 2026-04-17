#!/usr/bin/env python3
"""
stop_enforce.py — block the Stop hook when a top-level state-machine run
is still in flight.

Without this, the agent can:
  - start a skill (runner creates `.gates/runs/<id>.yaml` with status=running)
  - not finish it (no transition to terminal)
  - emit a final "done" message to the user
  - the pipeline is bypassed, trail is orphaned

Rules:
  - If project has no `.gates/runs/` dir → allow (not an atomic-gates project).
  - Only top-level runs matter (no `parent_run_id`). Sub-runs block via parent.
  - Runs stale > 24h are skipped (they're gc_runs.py's territory, not Stop's).
  - Any remaining `status: running` top-level run → exit 2 with resume hint.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("[stop_enforce] pyyaml missing, allowing stop\n")
    sys.exit(0)


_STALE_HOURS = 24.0


def _parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def find_unfinished_runs(project_dir: Path) -> list[dict]:
    runs_dir = project_dir / ".gates" / "runs"
    if not runs_dir.is_dir():
        return []
    now = datetime.now(timezone.utc)
    out: list[dict] = []
    for yml in sorted(runs_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("status") != "running":
            continue
        if data.get("parent_run_id"):
            continue  # sub-runs don't block stop; their parent does
        ts = data.get("updated_at") or data.get("created_at")
        when = _parse_iso(ts) if ts else None
        if when is None:
            continue
        if (now - when) > timedelta(hours=_STALE_HOURS):
            continue  # gc_runs.py territory, not stop enforcement
        out.append(
            {
                "run_id": data.get("run_id"),
                "skill_id": data.get("skill_id"),
                "current_state": data.get("current_state"),
            }
        )
    return out


def main() -> int:
    # Drain stdin so Claude Code's pipe doesn't block.
    try:
        sys.stdin.read()
    except Exception:
        pass

    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    unfinished = find_unfinished_runs(project)
    if not unfinished:
        return 0

    lines = [
        "gates: stop blocked — state-machine runs still in flight.",
        "",
        "Advance each run below to its terminal state before ending the",
        "session. To abandon explicitly, run:",
        "  python3 lib/gc_runs.py . --ttl 0s",
        "",
    ]
    for r in unfinished:
        lines.append(
            f"  - {r['skill_id']} (run_id {r['run_id']}) at state "
            f"'{r['current_state']}'"
        )
        lines.append(
            f"    resume: Skill({r['skill_id']}, "
            f"{{ run_id: '{r['run_id']}' }})"
        )
    lines.append("")
    lines.append(
        "Why: the pipeline must reach a terminal state so validate-issue "
        "or equivalent QA runs. Orphaned runs break the audit trail."
    )
    sys.stderr.write("\n".join(lines) + "\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
