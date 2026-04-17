#!/usr/bin/env python3
"""
gc_runs.py — mark stale `.gates/runs/` entries as abandoned.

Without GC, runs whose agent session was killed mid-flight sit in
`status: running` forever, polluting retrospective analytics. This
tool walks a project's runs directory, detects stale runs, and
rewrites `status: abandoned` on them. It never deletes yaml files —
audit trail is preserved.

Usage:
    python3 lib/gc_runs.py <project_dir> [--ttl 24h] [--dry-run]

Examples:
    python3 lib/gc_runs.py ~/Code/analytics-copilot
    python3 lib/gc_runs.py ~/Code/analytics-copilot --ttl 12h --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.stderr.write("pyyaml is required: pip install pyyaml\n")
    sys.exit(1)


_TTL_RE = re.compile(r"^(\d+)\s*([smhd])$")


def parse_ttl(spec: str) -> int:
    """Parse '24h', '30m', '2d', '3600s' -> seconds."""
    m = _TTL_RE.match(spec.strip().lower())
    if not m:
        raise ValueError(f"bad ttl spec: {spec!r} (expected e.g. '24h', '30m')")
    n = int(m.group(1))
    unit = m.group(2)
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def _parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def gc_stale_runs(
    project_dir: Path, ttl_seconds: int, dry_run: bool = False
) -> list[dict]:
    """Walk .gates/runs/*.yaml, mark stale runs as abandoned. Returns list of
    abandoned entries with {run_id, skill_id, age_hours}."""
    runs_dir = project_dir / ".gates" / "runs"
    if not runs_dir.is_dir():
        return []
    now = datetime.now(timezone.utc)
    out: list[dict] = []
    for yml in sorted(runs_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yml.read_text(encoding="utf-8"))
        except Exception as exc:
            sys.stderr.write(f"warn: cannot parse {yml}: {exc}\n")
            continue
        if not isinstance(data, dict):
            continue
        if data.get("status") != "running":
            continue
        ts = data.get("updated_at") or data.get("created_at")
        when = _parse_iso(ts) if ts else None
        if when is None:
            continue
        age = (now - when).total_seconds()
        if age < ttl_seconds:
            continue
        entry = {
            "run_id": data.get("run_id"),
            "skill_id": data.get("skill_id"),
            "current_state": data.get("current_state"),
            "age_hours": round(age / 3600, 1),
            "path": str(yml),
        }
        out.append(entry)
        if not dry_run:
            data["status"] = "abandoned"
            data["updated_at"] = now.isoformat()
            with yml.open("w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("project_dir", type=Path, help="Project root containing .gates/")
    ap.add_argument("--ttl", default="24h", help="Stale threshold (e.g. 24h, 30m, 2d)")
    ap.add_argument("--dry-run", action="store_true", help="Print without rewriting")
    args = ap.parse_args()

    ttl_seconds = parse_ttl(args.ttl)
    stale = gc_stale_runs(args.project_dir, ttl_seconds, args.dry_run)

    if not stale:
        print(f"no stale runs (ttl={args.ttl}) under {args.project_dir}")
        return 0

    verb = "would mark" if args.dry_run else "marked"
    print(f"{verb} {len(stale)} runs as abandoned (ttl={args.ttl}):")
    for e in stale:
        print(
            f"  - {e['run_id']} ({e['skill_id']}) "
            f"stuck {e['age_hours']}h on {e['current_state']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
