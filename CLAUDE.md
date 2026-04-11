# atomic-gates — developer context

This file is loaded by Claude Code whenever you open this checkout for
development. It's a condensed orientation to the codebase. For the user-
facing pitch, see [`README.md`](./README.md). For the technical reference,
see [`docs/atomic-gates.md`](./docs/atomic-gates.md).

## What this plugin is

`atomic-gates` turns declarative rules ("always run tests", "always update
.metadata/", "always validate PR coverage") into **blocking gates** —
hooks that refuse to let the agent advance unless a concrete artifact
exists and passes schema validation.

Implementation of Jesse Vincent's *Rules and Gates* thesis
(https://blog.fsck.com/2026/04/07/rules-and-gates/) at the Claude Code
plugin runtime level.

## Two layers of gates

1. **Atomic gates** — single-shot `PreToolUse` hooks that block one
   action (e.g. `gate-metadata` blocks `git commit` when
   `.metadata/summary.yaml` is stale).
2. **State-machine skills** — YAML machines where each state has an
   `output_schema`; a runner intercepts `Skill()` invocations, validates
   output at every transition, and persists runs in `.gates/runs/`.

## Layout

```
atomic-gates/
├── hooks/hooks.json        PreToolUse hooks for Bash, Edit|Write, Skill
├── lib/
│   ├── runner.py           state-machine arbiter
│   ├── gate_metadata.py    commit gate
│   ├── gate_pr_structure.py PR body structure gate
│   ├── gate_role.py        role enforcement gate
│   └── schema_validate.py  self-contained JSON Schema subset
├── schemas/                JSON Schemas (config, machine, run-state, metadata)
├── templates/              stub files for lazy bootstrap
├── scripts/
│   ├── dev-sync.sh         mirror checkout → Claude Code install paths
│   ├── check-tests.sh      legacy Stop hook (tests before stop)
│   └── check-build.sh      legacy TaskCompleted hook (build before done)
└── skills/
    ├── validate-issue/     4-state PR-covers-issue verification machine
    └── review-pr/          3-state PR review with categorized findings
```

## Dev workflow

The Claude Code runtime loads plugins from
`~/.claude/plugins/cache/atomic-gates/atomic-gates/<version>/`, NOT from
this checkout. Edits here do not reach the runtime until you run:

```bash
./scripts/dev-sync.sh
```

Idempotent. Mirrors `.claude-plugin/`, `hooks/`, `lib/`, `schemas/`,
`templates/`, `docs/`, and `skills/validate-issue/` + `skills/review-pr/`
into both the cache and marketplace install paths.

For a smoke test without restarting Claude Code, invoke the runners
standalone:

```bash
# Atomic commit gate
CLAUDE_PLUGIN_ROOT=$PWD CLAUDE_PROJECT_DIR=/tmp/test \
  python3 lib/gate_metadata.py <<<'{"tool_name":"Bash","tool_input":{"command":"git commit -m x"}}'

# State-machine runner
CLAUDE_PLUGIN_ROOT=$PWD CLAUDE_PROJECT_DIR=/tmp/test \
  python3 lib/runner.py <<<'{"tool_name":"Skill","tool_input":{"skill":"atomic-gates:validate-issue","args":"issue_number=42 pr_number=17"}}'
```

## Writing a new gate

An atomic gate is a Python script in `lib/` that:
1. Reads a JSON hook payload from stdin
2. Checks the relevant condition
3. Exits `0` (allow), `2` (block with stderr message), or any other code
   (non-blocking error — action proceeds, error is logged)

The hook must be registered in `hooks/hooks.json` under the appropriate
`PreToolUse` matcher. Always filter internally first — the matcher only
selects by tool name, not arguments.

Follow the structure of `lib/gate_metadata.py` as a template. Prefer
`_noop(reason)` for early returns that should NOT block, and `_block(msg)`
when the gate fires.

## Writing a new state-machine skill

Create `skills/<name>/skill.yaml` matching `schemas/skill-machine.schema.json`.
Optionally add `skills/<name>/schemas/<state>.output.schema.json` per
state to enforce output shape.

Also create `skills/<name>/SKILL.md` with the standard minimal stub that
points the agent at the `<system-reminder>` the runner will inject each
turn. Copy from `skills/validate-issue/SKILL.md` as a template.

Add the new skill to `SYNC_DIRS` in `scripts/dev-sync.sh` so the runtime
picks it up.

## Reference

- [Rules and Gates](https://blog.fsck.com/2026/04/07/rules-and-gates/)
- [`obra/superpowers`](https://github.com/obra/superpowers) — the skill corpus atomic-gates complements
