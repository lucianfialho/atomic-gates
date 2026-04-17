# atomic-gates — developer context

This file is loaded by Claude Code whenever you open this checkout for
development. It's a condensed orientation to the codebase. For the user-
facing pitch, see [`README.md`](./README.md). For the technical reference,
see [`docs/atomic-gates.md`](./docs/atomic-gates.md).

## What this plugin actually is (30-second pitch, grounded in data)

A runtime for **replayable multi-agent workflows on Claude Code**.
Declare the pipeline as a YAML state machine; every state output,
delegation and sub-run persists to `.gates/runs/<uuid>.yaml`, months-later
auditable with stdlib Python. Validated in practice: 31 real runs
across 2 projects, 87% terminate cleanly, cross-plugin delegation
works.

atomic-gates is inspired by Jesse Vincent's *Rules and Gates* thesis
(https://blog.fsck.com/2026/04/07/rules-and-gates/). The enforcement
side (three `PreToolUse` gates: commit metadata / PR body / role
scope) is now telemetered via `.gates/hook-log.jsonl` so we can ask
the honest question — "do they fire?" — with evidence instead of
vibes. See [`validation/`](./validation/) for the pre-registered
hypothesis ledger.

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
│   ├── import_skill.py     SKILL.md → skill.yaml converter
│   └── schema_validate.py  self-contained JSON Schema subset
├── schemas/                JSON Schemas (config, machine, run-state, metadata)
├── templates/              stub files for lazy bootstrap
└── scripts/
    ├── dev-sync.sh         mirror checkout → Claude Code install paths
    ├── check-tests.sh      legacy Stop hook (tests before stop)
    └── check-build.sh      legacy TaskCompleted hook (build before done)
```

**No skills/ directory.** atomic-gates is a pure runtime plugin. For
an actual skill corpus consumed by this runtime via cross-plugin
discovery, see
[`lucianfialho/claude-dev-pipeline`](https://github.com/lucianfialho/claude-dev-pipeline).

## Dev workflow

The Claude Code runtime loads plugins from
`~/.claude/plugins/cache/atomic-gates/atomic-gates/<version>/`, NOT from
this checkout. Edits here do not reach the runtime until you run:

```bash
./scripts/dev-sync.sh
```

Idempotent. Mirrors `.claude-plugin/`, `hooks/`, `lib/`, `schemas/`,
`templates/`, and `docs/` into both the cache and marketplace install
paths.

For a smoke test without restarting Claude Code, invoke the runners
standalone:

```bash
# Atomic commit gate
CLAUDE_PLUGIN_ROOT=$PWD CLAUDE_PROJECT_DIR=/tmp/test \
  python3 lib/gate_metadata.py <<<'{"tool_name":"Bash","tool_input":{"command":"git commit -m x"}}'

# State-machine runner (requires claude-dev-pipeline installed for a skill to find)
CLAUDE_PLUGIN_ROOT=$PWD CLAUDE_PROJECT_DIR=/tmp/test \
  python3 lib/runner.py <<<'{"tool_name":"Skill","tool_input":{"skill":"claude-dev-pipeline:validate-issue","args":"issue_number=42 pr_number=17"}}'
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

State-machine skills don't live in this repo — they belong in a
separate plugin (like `claude-dev-pipeline`) which the runner
discovers via cross-plugin search. To author a new skill:

1. In your own plugin repo, create `skills/<name>/skill.yaml` matching
   the schema at [`schemas/skill-machine.schema.json`](./schemas/skill-machine.schema.json).
2. Optionally add `skills/<name>/schemas/<state>.output.schema.json`
   per state to enforce output shape.
3. Create `skills/<name>/SKILL.md` with the standard minimal stub that
   points the agent at the `<system-reminder>` the runner will inject
   each turn. See [`authoring-state-machines.md`](./docs/guides/authoring-state-machines.md)
   for the template.
4. Publish/install your plugin normally. The atomic-gates runner will
   discover it via cross-plugin search (see v0.3.0 changelog).

If you already have a prose `SKILL.md` from another plugin and want a
state-machine skeleton, run the converter:

```bash
python3 lib/import_skill.py /path/to/SKILL.md -o /path/to/skill.yaml
```

Then refine per [`refining-skeletons.md`](./docs/guides/refining-skeletons.md).

## Reference

- [Rules and Gates](https://blog.fsck.com/2026/04/07/rules-and-gates/)
- [`obra/superpowers`](https://github.com/obra/superpowers) — the skill corpus atomic-gates complements
