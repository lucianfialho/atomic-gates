# Authoring atomic gates

This guide walks you through writing a new atomic gate — a single-shot
`PreToolUse` hook that inspects one condition and blocks one action.
If you haven't read [Getting started](./getting-started.md), do that
first — this assumes you understand the basic install and config flow.

The three gates shipped with `atomic-gates` (`gate_metadata`,
`gate_pr_structure`, `gate_role`) are the reference implementations.
This guide explains how they're built so you can build your own.

---

## What a gate is (and isn't)

A **gate** is a Python script that:

1. Reads a JSON hook payload from stdin (the tool call about to happen)
2. Checks one condition (is this action safe? does the artifact exist? does the format match?)
3. Exits with a code:
   - `0` → allow the action to proceed (no message shown)
   - `2` → block the action and print a message via stderr (shown to the agent)
   - Anything else → non-blocking error (action proceeds, error logged)

A gate is **not** a place to do complex orchestration. Keep each gate
to one condition. If you need multiple checks, write multiple gates
and register them all — the runner runs them in order, and any exit-2
cancels the tool call.

---

## The two files you need

```
lib/gate_<name>.py         # the script
hooks/hooks.json           # registration (add to existing file)
```

That's it. No schemas, no templates, no SKILL.md. Atomic gates are
minimal by design — they're closer to a git pre-commit hook than a
state machine.

---

## The anatomy of a gate script

Use `lib/gate_metadata.py` as the template. Every gate follows this
skeleton:

```python
#!/usr/bin/env python3
"""
gates: <what this gate does>.

Brief one-paragraph summary of when it fires and what it checks.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_LIB_DIR = Path(__file__).resolve().parent
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))


def _noop(reason: str) -> None:
    """Exit 0 without output. Normal passthrough."""
    print(f"[gate-<name>] noop: {reason}", file=sys.stderr)
    sys.exit(0)


def _block(message: str) -> None:
    """Exit 2 with a message. The agent sees this as a hook error."""
    sys.stderr.write(message.rstrip() + "\n")
    sys.exit(2)


# Optional: if the gate needs YAML parsing
try:
    import yaml  # type: ignore
except ImportError:
    _noop("pyyaml not available")


def read_stdin_json() -> dict:
    """Parse the hook payload from stdin."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def main() -> None:
    hook = read_stdin_json()

    # 1. Filter: is this a call we care about?
    if hook.get("tool_name") != "Bash":  # or Edit, Write, etc.
        _noop("not a Bash call")

    tool_input = hook.get("tool_input") or {}
    command = tool_input.get("command", "").strip()
    if not command.startswith("git commit"):  # whatever filter fits
        _noop("not a git commit")

    # 2. Gather context
    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    # Read config, query git state, etc.

    # 3. Check the condition
    problem = check_the_thing(project_dir, command)

    if problem is None:
        _noop("all good")

    # 4. Block
    _block(f"gates: <name> — {problem}\n\nWhy: ...")


if __name__ == "__main__":
    main()
```

---

## The hook input format

The JSON payload on stdin looks like this (for `PreToolUse: Bash`):

```json
{
  "session_id": "976de8fc-...",
  "transcript_path": "/Users/you/.claude/projects/.../<id>.jsonl",
  "cwd": "/private/tmp/your-project",
  "permission_mode": "default",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {
    "command": "git commit -m 'add navbar'",
    "description": "Commit the staged files"
  },
  "tool_use_id": "toolu_01VTgrkQan..."
}
```

Fields your gate will use most:

- `tool_name` — filter by which tool is being called (`Bash`, `Edit`, `Write`, etc.)
- `tool_input` — the tool-specific args. For `Bash`, `command` is the shell string. For `Edit|Write`, `file_path` is the target
- `cwd` — the working directory Claude Code is in. Also available as `$CLAUDE_PROJECT_DIR` env var

**Always filter by `tool_name` first, then by the tool-specific shape.**
The matcher in `hooks.json` only filters by tool name, not by arguments —
the argument-level filter must happen inside the script.

---

## Filtering patterns

### By command prefix (Bash)

```python
def is_git_commit(tool_input: dict) -> bool:
    command = (tool_input.get("command") or "").strip()
    if not command:
        return False
    return command.startswith("git commit") and (
        len(command) == len("git commit")
        or command[len("git commit")] in " \t\n"
    )
```

The trailing check prevents false positives like `git commit-tree` or
`git commit-graph`.

### By regex on compound commands

```python
import re

def is_gh_pr_create(tool_input: dict) -> bool:
    command = (tool_input.get("command") or "").strip()
    return bool(re.search(r"(^|[\s;&|])gh\s+pr\s+create(\s|$)", command))
```

This matches `gh pr create ...` even when embedded in
`cd X && gh pr create ...`.

### By file path (Edit|Write)

```python
def extract_target_path(tool_name: str, tool_input: dict) -> str | None:
    return tool_input.get("file_path") or tool_input.get("path")
```

### By environment variable

```python
active = os.environ.get("CLAUDE_ACTIVE_SPECIALIST", "").strip()
if not active:
    _noop("CLAUDE_ACTIVE_SPECIALIST not set — permissive mode")
```

Use env vars for role-scoped behavior that only matters inside a
specific workflow. See `lib/gate_role.py` for the full pattern.

---

## Registering the hook

Edit `hooks/hooks.json` and add your gate under the right matcher.
Multiple gates can share a matcher — they run in order.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/lib/gate_metadata.py",
            "timeout": 30,
            "statusMessage": "Checking .metadata/ before commit..."
          },
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/lib/gate_<your_gate>.py",
            "timeout": 30,
            "statusMessage": "Your message to the user..."
          }
        ]
      }
    ]
  }
}
```

The `${CLAUDE_PLUGIN_ROOT}` variable is expanded by Claude Code at hook
invocation time to the installed plugin path.

`timeout` is in seconds. Keep it low — hooks block tool execution.
30 is reasonable for scripts that read small files. Longer than 60
means the hook will visibly slow down the agent.

**If a hook has both a matcher-level filter and an internal filter,
the internal filter wins when they disagree.** The matcher is coarse
(tool name only); the internal logic is precise.

---

## Exit codes and what they mean

| Exit code | Effect |
|---|---|
| `0` | Allow the action. `stderr` is silently discarded |
| `2` | Block the action. `stderr` is shown to the agent as "hook error" |
| Other (`1`, `127`, etc.) | Non-blocking error. Action proceeds. First line of `stderr` is logged to the transcript as `<hook> hook error` |

**Always use exactly `0` or `2`.** Other codes create the worst UX: the
action proceeds but an error appears in the transcript, confusing
everyone. If the gate can't do its job, `_noop("reason")` and exit 0.

**`stderr` on exit 2 must be agent-readable.** The agent sees the text
verbatim and has to decide what to do. Write messages that:

- State the problem in one line
- List specific things to fix (bullet points)
- End with a "Why" sentence so the agent understands intent, not just rules

Compare:

```
BAD:  Error: validation failed
GOOD: gates: commit blocked — metadata problems found

Stub files created — fill these in and `git add` them:
  - components/NavBar/.metadata/summary.yaml

Why: directories indexed in .gates/config.yaml must keep their
.metadata/summary.yaml up to date on every commit that touches them.
```

The second one is actionable. The first one just tells Claude
"something went wrong, figure it out." Actionable messages reduce the
number of rationalization-driven retries.

---

## Developer workflow

### 1. Write the script

Drop a new `lib/gate_<name>.py` in the `lib/` directory following the
skeleton above.

### 2. Register the hook

Add the entry to `hooks/hooks.json` under the right matcher.

### 3. Sync to the install paths

```bash
./scripts/dev-sync.sh
```

### 4. Smoke test standalone

Feed a fake hook payload via stdin and check exit codes and stderr:

```bash
# Should noop (exit 0)
CLAUDE_PROJECT_DIR=/tmp/whatever python3 lib/gate_<name>.py <<'JSON'
{"tool_name":"Bash","tool_input":{"command":"ls -la"}}
JSON
echo "exit: $?"

# Should block (exit 2)
CLAUDE_PROJECT_DIR=/tmp/trigger-case python3 lib/gate_<name>.py <<'JSON'
{"tool_name":"Bash","tool_input":{"command":"git commit -m bad"}}
JSON
echo "exit: $?"
```

Run every branch at least once. Pay particular attention to:

- No `CLAUDE_PROJECT_DIR` set at all
- Project has no `.gates/config.yaml`
- File paths outside the project root
- Empty or malformed `tool_input`
- Commands that look similar but shouldn't match (e.g. `git commit-tree`)

### 5. Test in a live Claude Code session

Restart Claude Code (hooks only reload at session startup), then ask
the agent to trigger the gate condition. Verify the error message
appears in the chat output and that the agent understands it.

---

## Common pitfalls

**Matching on substring instead of prefix.** `"commit" in command`
matches `git commit-tree`, `ssh-commit`, anything. Always use
`startswith` with an explicit word boundary check.

**Using `exit 1` instead of `exit 2`.** Exit 1 is a non-blocking
error. The tool call proceeds, but the agent sees a confusing "hook
error" line in the transcript. Always use `exit 2` when you mean to
block.

**Writing to stdout instead of stderr on block.** stdout of a command
hook is only interpreted for specific JSON response formats. Plain
text messages must go to stderr. Use `sys.stderr.write(...)` or `>&2`
in shell.

**Forgetting that `CLAUDE_PLUGIN_ROOT` isn't a regular env var
outside hooks.** If you test the script without going through Claude
Code, you'll need to set it manually, or use `_LIB_DIR.parent` as the
default like the shipped gates do.

**Blocking too aggressively.** If your gate blocks on conditions that
don't have an obvious fix, the agent retries the same action and
fails again, wasting tokens. Always check: can the agent act on this
message? If the answer is "no, only a human can fix this," you
probably want to `_noop` and log somewhere else instead of blocking.

**Reading the project state with absolute assumptions.** `CLAUDE_PROJECT_DIR`
might not exist, might be different from `cwd`, might not be a git repo.
Always `.exists()` before reading, handle `subprocess.CalledProcessError`
on git commands, and default to permissive on any unknown state.

---

## When atomic is wrong — use a state machine instead

If your "gate" needs to:

- Run across multiple turns
- Pass data between steps
- Validate structured agent output (YAML, JSON)
- Loop back on invalid output
- Aggregate findings before deciding

Then you don't want an atomic gate — you want a **state-machine skill**.
See [Authoring state-machine skills](./authoring-state-machines.md).

Atomic gates are for single-shot, synchronous, binary checks. That's
their entire job description. If you're reaching for more, reach for a
different tool.

---

## See also

- [`lib/gate_metadata.py`](../../lib/gate_metadata.py) — commit gate, the canonical reference
- [`lib/gate_pr_structure.py`](../../lib/gate_pr_structure.py) — parses `gh pr create` body + schema check
- [`lib/gate_role.py`](../../lib/gate_role.py) — env-var-driven role enforcement
- [`hooks/hooks.json`](../../hooks/hooks.json) — how the gates are registered
- [`docs/atomic-gates.md`](../atomic-gates.md) — full technical reference
