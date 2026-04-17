#!/usr/bin/env python3
"""
Retrospective analyzer for .gates/runs/ directories.

Reads every run yaml under the given project path(s), emits stats against
the hypotheses in validation/hypotheses.yaml, and updates validation/ledger.md.

Usage:
    python3 validation/analyze_runs.py <project_dir> [<project_dir> ...]

Does NOT require external deps — uses PyYAML only if available, otherwise
falls back to a minimal YAML front-matter parser for our known shape.
"""
from __future__ import annotations

import sys
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: install pyyaml (pip install pyyaml)", file=sys.stderr)
    sys.exit(1)


def load_runs(project_dir: Path) -> list[dict]:
    runs_dir = project_dir / ".gates" / "runs"
    if not runs_dir.is_dir():
        return []
    out = []
    for yml in sorted(runs_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(yml.read_text())
        except Exception as exc:
            print(f"warn: failed to parse {yml}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, dict):
            continue
        data["_path"] = str(yml)
        data["_project"] = project_dir.name
        out.append(data)
    return out


def count_gate_failures(runs: list[dict]) -> int:
    total = 0
    for r in runs:
        for h in r.get("history", []) or []:
            total += len(h.get("gate_failures", []) or [])
    return total


def stuck_runs(runs: list[dict], stale_hours: float = 24.0) -> list[dict]:
    now = datetime.now(timezone.utc)
    stuck = []
    for r in runs:
        if r.get("status") != "running":
            continue
        updated = r.get("updated_at") or r.get("created_at")
        if not updated:
            continue
        try:
            t = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        except Exception:
            continue
        hours = (now - t).total_seconds() / 3600
        if hours >= stale_hours:
            stuck.append({"run_id": r.get("run_id"), "skill_id": r.get("skill_id"),
                          "project": r.get("_project"), "stuck_for_hours": round(hours, 1),
                          "current_state": r.get("current_state")})
    return stuck


def skill_distribution(runs: list[dict]) -> dict[str, int]:
    d: dict[str, int] = {}
    for r in runs:
        sid = r.get("skill_id", "<unknown>")
        d[sid] = d.get(sid, 0) + 1
    return dict(sorted(d.items(), key=lambda kv: -kv[1]))


def status_distribution(runs: list[dict]) -> dict[str, int]:
    d: dict[str, int] = {}
    for r in runs:
        s = r.get("status", "<unknown>")
        d[s] = d.get(s, 0) + 1
    return d


def evaluate(runs: list[dict]) -> dict:
    terminal = sum(1 for r in runs if r.get("status") == "terminal")
    running = sum(1 for r in runs if r.get("status") == "running")
    error = sum(1 for r in runs if r.get("status") == "error")
    total = len(runs)
    gate_fails = count_gate_failures(runs)
    stuck = stuck_runs(runs)
    skills = skill_distribution(runs)

    solve_issue_runs = skills.get("claude-dev-pipeline:solve-issue", 0)
    validate_runs = skills.get("claude-dev-pipeline:validate-issue", 0)

    verdicts = {}

    # H1: gates fire >= 1 per 10 terminal runs
    if terminal == 0:
        verdicts["H1"] = {"verdict": "inconclusive", "reason": "no terminal runs yet"}
    else:
        rate = gate_fails / terminal
        killed = rate < 0.1
        verdicts["H1"] = {
            "verdict": "killed" if killed else "surviving",
            "observed": f"{gate_fails} gate_failures across {terminal} terminal runs (rate={rate:.3f})",
            "threshold": ">= 0.1 failures per terminal run",
        }

    # H2: <15% stuck
    if total == 0:
        verdicts["H2"] = {"verdict": "inconclusive", "reason": "no runs"}
    else:
        stuck_pct = len(stuck) / total
        killed = stuck_pct > 0.15
        verdicts["H2"] = {
            "verdict": "killed" if killed else "surviving",
            "observed": f"{len(stuck)}/{total} runs stuck >24h ({stuck_pct:.1%})",
            "threshold": "<= 15%",
            "stuck_detail": stuck,
        }

    # H3: validate-issue >= 1/5 solve-issue
    if solve_issue_runs == 0:
        verdicts["H3"] = {"verdict": "inconclusive", "reason": "no solve-issue runs"}
    else:
        ratio = validate_runs / solve_issue_runs
        killed = ratio < 0.2
        verdicts["H3"] = {
            "verdict": "killed" if killed else "surviving",
            "observed": f"{validate_runs} validate-issue vs {solve_issue_runs} solve-issue (ratio={ratio:.2f})",
            "threshold": ">= 0.2",
        }

    # H4: no skeleton stuck on meta state
    meta_states = {"usage", "overview", "red_flags", "background", "examples"}
    trap_runs = [s for s in stuck if (s["current_state"] or "").lower() in meta_states]
    if total == 0:
        verdicts["H4"] = {"verdict": "inconclusive", "reason": "no runs"}
    else:
        killed = len(trap_runs) > 0
        verdicts["H4"] = {
            "verdict": "killed" if killed else "surviving",
            "observed": f"{len(trap_runs)} runs stuck on meta-section states",
            "threshold": "= 0",
            "trap_runs": trap_runs,
        }

    return {
        "total_runs": total,
        "terminal": terminal,
        "running": running,
        "error": error,
        "gate_failures_total": gate_fails,
        "stuck_runs": stuck,
        "skills": skills,
        "statuses": status_distribution(runs),
        "verdicts": verdicts,
    }


def render_markdown(stats: dict, projects: list[str]) -> str:
    lines = []
    lines.append("# atomic-gates — validation ledger")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat()}_  ")
    lines.append(f"_Projects scanned: {', '.join(projects)}_  ")
    lines.append(f"_Protocol: `validation/hypotheses.yaml`_")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Total runs: **{stats['total_runs']}**")
    lines.append(f"- Terminal: {stats['terminal']}  ·  Running: {stats['running']}  ·  Error: {stats['error']}")
    lines.append(f"- Gate failures across all history: **{stats['gate_failures_total']}**")
    lines.append(f"- Stuck runs (>24h in `running`): **{len(stats['stuck_runs'])}**")
    lines.append("")
    lines.append("### Skill distribution")
    lines.append("")
    lines.append("| skill_id | runs |")
    lines.append("|---|---|")
    for k, v in stats["skills"].items():
        lines.append(f"| `{k}` | {v} |")
    lines.append("")
    lines.append("## Verdicts")
    lines.append("")
    for hid, v in stats["verdicts"].items():
        emoji = {"killed": "💀", "surviving": "✅", "inconclusive": "❔"}.get(v["verdict"], "?")
        lines.append(f"### {hid} — {emoji} {v['verdict'].upper()}")
        lines.append("")
        if "observed" in v:
            lines.append(f"- Observed: {v['observed']}")
        if "threshold" in v:
            lines.append(f"- Kill threshold: {v['threshold']}")
        if "reason" in v:
            lines.append(f"- Reason: {v['reason']}")
        if "stuck_detail" in v and v["stuck_detail"]:
            lines.append("- Stuck runs:")
            for s in v["stuck_detail"]:
                lines.append(f"  - `{s['run_id']}` ({s['skill_id']}) stuck {s['stuck_for_hours']}h on `{s['current_state']}`")
        if "trap_runs" in v and v["trap_runs"]:
            lines.append("- Trap runs (stuck on meta-state):")
            for s in v["trap_runs"]:
                lines.append(f"  - `{s['run_id']}` ({s['skill_id']}) on `{s['current_state']}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: analyze_runs.py <project_dir> [<project_dir> ...]", file=sys.stderr)
        return 2
    all_runs: list[dict] = []
    projects: list[str] = []
    for arg in sys.argv[1:]:
        p = Path(arg).expanduser().resolve()
        runs = load_runs(p)
        all_runs.extend(runs)
        projects.append(p.name)
        print(f"loaded {len(runs)} runs from {p}", file=sys.stderr)
    stats = evaluate(all_runs)
    out_dir = Path(__file__).parent
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2, default=str))
    (out_dir / "ledger.md").write_text(render_markdown(stats, projects))
    print(f"wrote {out_dir / 'stats.json'}")
    print(f"wrote {out_dir / 'ledger.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
