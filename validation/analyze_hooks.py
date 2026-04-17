#!/usr/bin/env python3
"""
analyze_hooks.py — aggregate <project>/.gates/hook-log.jsonl across projects.

Answers the questions retrospective on H5:
  - How often did each atomic gate fire?
  - What was the block rate per gate?
  - Which tool calls are blocked most?
  - What are the most common block reasons?

Usage:
    python3 validation/analyze_hooks.py <project_dir> [<project_dir> ...]

Writes stats to validation/hooks_stats.json and prints a summary.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def load_entries(project_dir: Path) -> list[dict]:
    log = project_dir / ".gates" / "hook-log.jsonl"
    if not log.exists():
        return []
    out: list[dict] = []
    for line in log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def aggregate(entries: list[dict]) -> dict:
    by_gate: Counter[str] = Counter()
    by_gate_decision: Counter[tuple[str, str]] = Counter()
    blocked_tools: Counter[str] = Counter()
    block_reasons: Counter[str] = Counter()

    for e in entries:
        gate = e.get("gate", "<unknown>")
        tool = e.get("tool", "<unknown>")
        decision = e.get("decision", "<unknown>")
        reason = (e.get("reason") or "")[:80]
        by_gate[gate] += 1
        by_gate_decision[(gate, decision)] += 1
        if decision == "block":
            blocked_tools[tool] += 1
            block_reasons[reason] += 1

    block_rate: dict[str, float] = {}
    for gate in by_gate:
        fired = by_gate[gate]
        blocked = by_gate_decision.get((gate, "block"), 0)
        block_rate[gate] = round(blocked / fired, 3) if fired else 0.0

    return {
        "total": sum(by_gate.values()),
        "by_gate": dict(by_gate),
        "block_rate": block_rate,
        "by_gate_decision": {f"{g}:{d}": c for (g, d), c in by_gate_decision.items()},
        "top_blocked_tools": blocked_tools.most_common(10),
        "top_block_reasons": block_reasons.most_common(10),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: analyze_hooks.py <project_dir> [<project_dir> ...]", file=sys.stderr)
        return 2

    all_entries: list[dict] = []
    for arg in sys.argv[1:]:
        p = Path(arg).expanduser().resolve()
        entries = load_entries(p)
        all_entries.extend(entries)
        print(f"loaded {len(entries)} hook log entries from {p}", file=sys.stderr)

    stats = aggregate(all_entries)
    out = Path(__file__).parent / "hooks_stats.json"
    out.write_text(json.dumps(stats, indent=2, default=str))
    print(f"wrote {out}")

    print()
    print(f"total hook firings: {stats['total']}")
    print("by gate:")
    for g, c in stats["by_gate"].items():
        rate = stats["block_rate"].get(g, 0.0)
        print(f"  {g}: {c}  (block rate {rate:.1%})")
    if stats["top_blocked_tools"]:
        print("top blocked tools:")
        for tool, c in stats["top_blocked_tools"]:
            print(f"  {tool}: {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
