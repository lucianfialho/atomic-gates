#!/usr/bin/env python3
"""
gates: metadata commit gate.

Invoked as a PreToolUse hook on `Bash(git commit *)` calls. Reads the
target project's `.gates/config.yaml`, determines which indexed directories
have staged changes, and verifies that each of them has a valid
`.metadata/summary.yaml` staged alongside.

Blocking rules (any triggers exit 2):
  - indexed directory has staged file changes but no `.metadata/` folder
    → creates a stub, tells the agent to fill it in
  - `.metadata/summary.yaml` exists but is not staged in this commit
    → tells the agent to update and stage it
  - `summary.yaml` fails schema validation
    → reports the error
  - `summary.yaml` has `status: stub`
    → tells the agent to finish filling it in

If the project has no `.gates/config.yaml`, the gate exits 0 silently —
projects that haven't opted in are unaffected.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

_LIB_DIR = Path(__file__).resolve().parent
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))


def _noop(reason: str) -> None:
    print(f"[gate-metadata] noop: {reason}", file=sys.stderr)
    sys.exit(0)


def _block(message: str) -> None:
    sys.stderr.write(message.rstrip() + "\n")
    sys.exit(2)


try:
    import yaml  # type: ignore
except ImportError:
    _noop("pyyaml not available")

from schema_validate import validate, ValidationError  # noqa: E402


def read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def is_git_commit(tool_input: dict) -> bool:
    command = (tool_input.get("command") or "").strip()
    if not command:
        return False
    # Accept: git commit, git commit -m ..., git commit --amend, etc.
    # Reject: git commit-tree, git commit-graph, etc.
    return command.startswith("git commit") and (
        len(command) == len("git commit") or command[len("git commit")] in " \t\n"
    )


def staged_files(project_dir: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def load_config(project_dir: Path) -> dict | None:
    config_path = project_dir / ".gates" / "config.yaml"
    if not config_path.exists():
        return None
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def affected_directories(
    config: dict, staged: list[str]
) -> list[dict]:
    """Return the indexed directories that have at least one staged file."""
    result = []
    for entry in config.get("indexed_directories") or []:
        path = entry["path"].rstrip("/")
        for staged_file in staged:
            if staged_file == path or staged_file.startswith(path + "/"):
                result.append(entry)
                break
    return result


def ensure_metadata_stub(
    project_dir: Path,
    plugin_root: Path,
    entry: dict,
) -> bool:
    """Create a stub summary.yaml if missing. Returns True if it created one."""
    metadata_dir = project_dir / entry["path"] / ".metadata"
    summary_path = metadata_dir / "summary.yaml"
    if summary_path.exists():
        return False
    metadata_dir.mkdir(parents=True, exist_ok=True)
    stub_template = plugin_root / "templates" / "metadata-summary.stub.yaml"
    if stub_template.exists():
        shutil.copyfile(stub_template, summary_path)
    else:
        summary_path.write_text(
            "id: TODO-id\ntitle: TODO-title\ncovers:\n  - TODO\n"
            "specialist: TODO\nlast_updated: TODO\nstatus: stub\n",
            encoding="utf-8",
        )
    return True


def validate_summary(
    summary_path: Path, plugin_root: Path
) -> list[str]:
    schema_path = plugin_root / "schemas" / "metadata-summary.schema.json"
    if not schema_path.exists():
        return []
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"metadata-summary schema is invalid JSON: {e}"]
    try:
        with summary_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:  # noqa: BLE001
        return [f"{summary_path} is not valid YAML: {e}"]
    try:
        validate(data, schema)
    except ValidationError as e:
        return [f"{summary_path}: {e}"]
    return []


def main() -> None:
    hook = read_stdin_json()
    if hook.get("tool_name") != "Bash":
        _noop("not a Bash call")
    if not is_git_commit(hook.get("tool_input") or {}):
        _noop("not a git commit")

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or _LIB_DIR.parent)

    config = load_config(project_dir)
    if config is None:
        _noop("no .gates/config.yaml")

    staged = staged_files(project_dir)
    if not staged:
        _noop("nothing staged")

    affected = affected_directories(config, staged)
    if not affected:
        _noop("no indexed directory affected")

    problems: list[str] = []
    stubs_created: list[str] = []

    for entry in affected:
        dir_path = entry["path"]
        metadata_rel = f"{dir_path}/.metadata/summary.yaml"
        summary_path = project_dir / dir_path / ".metadata" / "summary.yaml"

        if ensure_metadata_stub(project_dir, plugin_root, entry):
            stubs_created.append(metadata_rel)
            continue  # stub just created, can't be staged yet

        if metadata_rel not in staged:
            problems.append(
                f"{metadata_rel}: exists but is not staged in this commit. "
                f"Update it and `git add` it, or confirm it still reflects reality."
            )
            continue

        schema_errors = validate_summary(summary_path, plugin_root)
        if schema_errors:
            problems.extend(schema_errors)
            continue

        with summary_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data.get("status") != "filled":
            problems.append(
                f"{metadata_rel}: status is `{data.get('status')}`, must be `filled` before commit."
            )

    if not stubs_created and not problems:
        _noop("all metadata valid and staged")

    lines = ["gates: commit blocked — metadata problems found"]
    if stubs_created:
        lines.append("")
        lines.append("Stub files created — fill these in and `git add` them:")
        for s in stubs_created:
            lines.append(f"  - {s}")
    if problems:
        lines.append("")
        lines.append("Problems:")
        for p in problems:
            lines.append(f"  - {p}")
    lines.append("")
    lines.append(
        "Why: directories indexed in .gates/config.yaml must keep their "
        ".metadata/summary.yaml up to date on every commit that touches them."
    )
    _block("\n".join(lines))


if __name__ == "__main__":
    main()
