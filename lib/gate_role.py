#!/usr/bin/env python3
"""
gates: role enforcement gate.

Invoked as a PreToolUse hook on `Edit` and `Write` tool calls. Reads
the target project's `.gates/config.yaml` and the current active
specialist from the `CLAUDE_ACTIVE_SPECIALIST` environment variable.
If the file being edited lives inside an indexed directory whose
`specialist` does not match the active specialist, the edit is
refused with exit 2.

Environment contract:

  CLAUDE_ACTIVE_SPECIALIST
      Optional. Set by an orchestrator (e.g. a solve-issue workflow)
      before delegating work to a specialist. If unset, the gate is
      permissive — every edit is allowed. This preserves normal
      interactive use outside of role-scoped workflows.

Blocking rules (any triggers exit 2):
  - CLAUDE_ACTIVE_SPECIALIST is set AND
  - The edited file lives inside a directory listed in
    .gates/config.yaml → indexed_directories AND
  - That directory's `specialist` is not equal to
    CLAUDE_ACTIVE_SPECIALIST

Files outside any indexed directory are always allowed. Files inside
an indexed directory whose specialist matches the active one are
always allowed. Files outside the project (absolute path under a
different root) are always allowed.

If there is no `.gates/config.yaml`, the gate exits 0 silently.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_LIB_DIR = Path(__file__).resolve().parent
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from gate_log import log_decision  # noqa: E402

_GATE_NAME = "role"
_TOOL_NAME = ""


def _noop(reason: str) -> None:
    log_decision(_GATE_NAME, _TOOL_NAME, "allow", reason)
    print(f"[gate-role] noop: {reason}", file=sys.stderr)
    sys.exit(0)


def _block(message: str) -> None:
    log_decision(_GATE_NAME, _TOOL_NAME, "block", message.splitlines()[0] if message else "")
    sys.stderr.write(message.rstrip() + "\n")
    sys.exit(2)


try:
    import yaml  # type: ignore
except ImportError:
    _noop("pyyaml not available")


def read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def extract_target_path(tool_name: str, tool_input: dict) -> str | None:
    """Get the filesystem path this tool call wants to write."""
    # Claude Code tools Write/Edit expose the target path as file_path.
    return tool_input.get("file_path") or tool_input.get("path")


def load_config(project_dir: Path) -> dict | None:
    config_path = project_dir / ".gates" / "config.yaml"
    if not config_path.exists():
        return None
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_relative(project_dir: Path, file_path: str) -> str | None:
    """Return the path of file_path relative to project_dir, or None
    if it's outside the project root.
    """
    try:
        target = Path(file_path).resolve()
    except (OSError, RuntimeError):
        return None
    try:
        rel = target.relative_to(project_dir.resolve())
    except ValueError:
        return None
    return str(rel)


def find_owning_directory(
    config: dict, relative_path: str
) -> dict | None:
    """Return the indexed_directories entry that owns this file, or None."""
    for entry in config.get("indexed_directories") or []:
        dir_path = entry["path"].rstrip("/")
        if relative_path == dir_path or relative_path.startswith(dir_path + "/"):
            return entry
    return None


def main() -> None:
    global _TOOL_NAME
    hook = read_stdin_json()
    tool_name = hook.get("tool_name") or ""
    _TOOL_NAME = tool_name
    if tool_name not in ("Edit", "Write"):
        _noop(f"not Edit/Write (got {tool_name})")

    active = os.environ.get("CLAUDE_ACTIVE_SPECIALIST", "").strip()
    if not active:
        _noop("CLAUDE_ACTIVE_SPECIALIST not set — permissive mode")

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    config = load_config(project_dir)
    if config is None:
        _noop("no .gates/config.yaml")

    tool_input = hook.get("tool_input") or {}
    target = extract_target_path(tool_name, tool_input)
    if not target:
        _noop("no file_path in tool_input")

    rel = resolve_relative(project_dir, target)
    if rel is None:
        _noop(f"path {target} is outside project root")

    owner = find_owning_directory(config, rel)
    if owner is None:
        _noop(f"{rel} is not inside any indexed directory")

    owning_specialist = owner.get("specialist") or ""
    if owning_specialist == active:
        _noop(
            f"{rel} owned by {owning_specialist}, matches active specialist"
        )

    # Block.
    lines = [
        "gates: edit blocked — role enforcement",
        "",
        f"Active specialist: {active}",
        f"Target file:      {rel}",
        f"Directory owner:  {owner['path']} (specialist: {owning_specialist})",
        "",
        f"Why: {rel} lives inside an indexed directory owned by "
        f"'{owning_specialist}', but the current workflow is running as "
        f"'{active}'. Role-scoped workflows are not permitted to edit "
        "files outside their declared specialist.",
        "",
        "Fix: either switch the active specialist to "
        f"'{owning_specialist}' for this edit, or update "
        ".gates/config.yaml if the ownership has genuinely changed.",
    ]
    _block("\n".join(lines))


if __name__ == "__main__":
    main()
