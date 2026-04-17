#!/usr/bin/env python3
"""
gate_log.py — append-only JSONL log of atomic-gate decisions.

Each entry is one line on `<project>/.gates/hook-log.jsonl`:
  {"ts": iso8601, "gate": "metadata", "tool": "Bash",
   "decision": "allow" | "block", "reason": "..."}

Kept intentionally minimal — no schema validation on write (hooks must
stay fast), no buffering, no external deps. validation/analyze_hooks.py
handles aggregation.

Fails silently on any IO error: a gate must NEVER block its own tool
call because telemetry failed.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


_MAX_REASON_LEN = 500


def _project_dir() -> Path | None:
    raw = os.environ.get("CLAUDE_PROJECT_DIR")
    if not raw:
        return None
    try:
        return Path(raw)
    except Exception:
        return None


def log_decision(
    gate: str, tool: str, decision: str, reason: str = ""
) -> None:
    """Append one decision record to <project>/.gates/hook-log.jsonl.

    Does nothing if CLAUDE_PROJECT_DIR is unset or the log cannot be
    written — telemetry must never interfere with hook execution.
    """
    project = _project_dir()
    if project is None:
        return
    gates_dir = project / ".gates"
    try:
        gates_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        return
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "gate": gate,
        "tool": tool,
        "decision": decision,
        "reason": (reason or "")[:_MAX_REASON_LEN],
    }
    try:
        with (gates_dir / "hook-log.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        return
