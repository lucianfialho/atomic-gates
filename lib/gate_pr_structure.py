#!/usr/bin/env python3
"""
gates: PR structure gate.

Invoked as a PreToolUse hook on `Bash(gh pr create *)` calls. Reads the
target project's `.gates/config.yaml`, looks at the `pr_structure`
section, and refuses to let `gh pr create` run unless the PR body has
every required section declared in the config.

Blocking rules (any triggers exit 2):
  - The Bash command is `gh pr create ...` AND the project has
    `pr_structure: { required_sections: [...] }` declared
  - The body provided on the command line (via --body, --body-file,
    or -F/-b) is missing one or more of those sections
  - The body is shorter than `min_body_length` if that is set

If the project has no `.gates/config.yaml`, or the config has no
`pr_structure` section, the gate exits 0 silently — the commit/PR
proceeds as normal.

Parsing notes:
  - We support --body "<text>", --body=<text>, -b "<text>"
  - We support --body-file <path>, --body-file=<path>, -F <path>
  - If neither is present, the body is empty and the gate fails if
    any required sections are declared.
  - We do NOT interpret here-documents, process substitution, or
    arbitrary shell. The gate is a heuristic on the command string.
    The cost of a false negative is small (a sloppy PR slips through);
    the cost of a false positive is annoying but recoverable.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

_LIB_DIR = Path(__file__).resolve().parent
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))


def _noop(reason: str) -> None:
    print(f"[gate-pr-structure] noop: {reason}", file=sys.stderr)
    sys.exit(0)


def _block(message: str) -> None:
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


def is_gh_pr_create(tool_input: dict) -> bool:
    command = (tool_input.get("command") or "").strip()
    if not command:
        return False
    # Match "gh pr create" as a prefix, allowing anything after.
    # Reject "gh pr create-something" (not a real subcommand but defensive).
    # Also accept it anywhere in a simple `cd X && gh pr create ...` pipeline.
    return bool(re.search(r"(^|[\s;&|])gh\s+pr\s+create(\s|$)", command))


def load_config(project_dir: Path) -> dict | None:
    config_path = project_dir / ".gates" / "config.yaml"
    if not config_path.exists():
        return None
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_gh_pr_create_command(command_string: str) -> list[str] | None:
    """Pick out just the `gh pr create ...` tokens from a shell line.

    Handles simple cases like:
      - "gh pr create --body 'x'"
      - "cd /tmp/foo && gh pr create --body 'x'"
      - "gh pr create --body 'x' && echo done"

    Returns the tokens of the gh subcommand or None if parsing fails.
    """
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return None

    # Find the position of "gh" followed by "pr" followed by "create"
    for i in range(len(tokens) - 2):
        if (
            tokens[i] == "gh"
            and tokens[i + 1] == "pr"
            and tokens[i + 2] == "create"
        ):
            # Collect until a shell separator that shlex didn't eat (it won't
            # eat && or ||; those become distinct tokens '&&' / '||').
            result = [tokens[i], tokens[i + 1], tokens[i + 2]]
            j = i + 3
            while j < len(tokens):
                if tokens[j] in ("&&", "||", ";", "|"):
                    break
                result.append(tokens[j])
                j += 1
            return result
    return None


def extract_body(gh_tokens: list[str], project_dir: Path) -> str:
    """Walk the gh pr create tokens looking for --body/--body-file."""
    body = ""
    i = 0
    while i < len(gh_tokens):
        token = gh_tokens[i]

        # --body text forms
        if token == "--body" or token == "-b":
            if i + 1 < len(gh_tokens):
                body = gh_tokens[i + 1]
                i += 2
                continue
        if token.startswith("--body="):
            body = token[len("--body="):]
            i += 1
            continue

        # --body-file path forms
        if token == "--body-file" or token == "-F":
            if i + 1 < len(gh_tokens):
                path = Path(gh_tokens[i + 1])
                if not path.is_absolute():
                    path = project_dir / path
                if path.exists():
                    body = path.read_text(encoding="utf-8", errors="replace")
                i += 2
                continue
        if token.startswith("--body-file="):
            raw = token[len("--body-file="):]
            path = Path(raw)
            if not path.is_absolute():
                path = project_dir / path
            if path.exists():
                body = path.read_text(encoding="utf-8", errors="replace")
            i += 1
            continue

        i += 1
    return body


def find_missing_sections(body: str, required: list[str]) -> list[str]:
    missing = []
    for section in required:
        # Each required section is expected to appear on its own line.
        # We accept the section verbatim (e.g. "## Summary") or with
        # trailing whitespace.
        pattern = re.compile(
            r"^" + re.escape(section.rstrip()) + r"\s*$",
            re.MULTILINE,
        )
        if not pattern.search(body):
            missing.append(section)
    return missing


def main() -> None:
    hook = read_stdin_json()
    if hook.get("tool_name") != "Bash":
        _noop("not a Bash call")
    if not is_gh_pr_create(hook.get("tool_input") or {}):
        _noop("not a gh pr create")

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    config = load_config(project_dir)
    if config is None:
        _noop("no .gates/config.yaml")

    pr_spec = config.get("pr_structure")
    if not pr_spec:
        _noop("no pr_structure in .gates/config.yaml")

    required_sections = pr_spec.get("required_sections") or []
    min_body_length = int(pr_spec.get("min_body_length") or 0)
    if not required_sections and min_body_length == 0:
        _noop("pr_structure is empty")

    command_string = (hook.get("tool_input") or {}).get("command", "")
    gh_tokens = extract_gh_pr_create_command(command_string)
    if gh_tokens is None:
        _noop("could not parse gh pr create tokens")

    body = extract_body(gh_tokens, project_dir)

    problems: list[str] = []
    if min_body_length and len(body) < min_body_length:
        problems.append(
            f"PR body is {len(body)} chars, minimum required is {min_body_length}."
        )

    missing = find_missing_sections(body, required_sections)
    if missing:
        problems.append("Missing required sections in PR body:")
        for s in missing:
            problems.append(f"  - {s}")

    if not problems:
        _noop("PR body passes structure check")

    lines = ["gates: PR blocked — body does not meet required structure"]
    lines.append("")
    lines.extend(problems)
    lines.append("")
    lines.append(
        "Why: .gates/config.yaml declares pr_structure.required_sections. "
        "Rewrite the PR body to include every required section (each on its "
        "own line) and try again."
    )
    _block("\n".join(lines))


if __name__ == "__main__":
    main()
