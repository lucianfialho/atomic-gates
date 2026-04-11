# atomic-gates — technical reference

Technical reference for the `atomic-gates` plugin: architecture, file
layout, schemas, and development notes. For the conceptual pitch and
quick-start, see the [README](../README.md).

The thesis is Jesse Vincent's [*Rules and Gates*](https://blog.fsck.com/2026/04/07/rules-and-gates/):
declarative rules in prompts are fragile because agents rationalize their
way around them. Gates are robust because the next step literally cannot
happen without the artifact.

## What "atomic" means here

Every gate in this subsystem is indivisible: it either passes as a whole
or fails as a whole, with no intermediate state. State machines compose
multiple atomic gates in sequence — the composition does not make any
individual gate "soft." Each transition is still all-or-nothing.

## Two layers of gates

### Layer 1 — Atomic gates (single-shot hooks)

Self-contained hooks that inspect one condition and block one action.

**Currently shipped:**

- **`gate-metadata`** — `PreToolUse: Bash` hook that blocks `git commit`
  when an indexed directory has staged changes but its `.metadata/summary.yaml`
  is missing, outdated, or invalid. Creates a stub on first run so the
  agent knows what to fill.

**Planned:**

- `gate-pr-structure` — blocks `gh pr create` when the PR body is missing
  required sections (Summary, Changes, Issue coverage).
- `gate-role-enforcement` — blocks `Edit|Write` on files outside the
  specialist's declared scope.

### Layer 2 — State machines (composed gates)

Skills declared as YAML state machines where each state is itself a gate:
output must match a schema, gate scripts must pass, and transitions are
decided by the runner — not the agent.

The runner is a `PreToolUse: Skill` hook that intercepts skill invocations,
loads the state machine, creates a run, and injects the current state's
task as a system-reminder. The agent executes one state per turn, writes
a YAML output, and re-invokes `Skill(<name>, { run_id })` to advance.

**Currently shipped:**

- **`validate-issue`** — four-state machine (`fetch → extract_requirements
  → check_coverage → emit_verdict → done`) that verifies a PR covers its
  linked issue's requirements. Output is a structured verdict with
  `COMPLETE | INCOMPLETE | NEEDS_DISCUSSION`.

## Repo layout

```
atomic-gates/
├── hooks/hooks.json                  PreToolUse: Bash (gate-metadata)
│                                     PreToolUse: Skill (state-machine runner)
├── lib/
│   ├── runner.py                     state machine runner (the arbiter)
│   ├── gate_metadata.py              gate-metadata commit hook
│   └── schema_validate.py            self-contained JSON Schema subset
├── schemas/
│   ├── gates-config.schema.json      target project's .gates/config.yaml
│   ├── metadata-summary.schema.json  directory .metadata/summary.yaml
│   ├── skill-machine.schema.json     skills/<name>/skill.yaml
│   └── run-state.schema.json         .gates/runs/<id>.yaml
├── templates/
│   └── metadata-summary.stub.yaml    stub written by lazy bootstrap
└── skills/validate-issue/
    ├── skill.yaml                    the state machine
    ├── SKILL.md                      minimal agent-facing instructions
    └── schemas/
        └── fetch.output.schema.json  example state output schema
```

## How a target project adopts it

### 1. Create `.gates/config.yaml`

```yaml
version: 1
project:
  name: my-app
indexed_directories:
  - path: components/NavBar
    specialist: frontend
    tags: [layout, navigation]
  - path: app/api/users/[id]
    specialist: backend
    tags: [api, rest]
```

### 2. Commit something in an indexed directory

The first `git commit` that touches `components/NavBar/` will be blocked
by `gate-metadata`. A stub is created at `components/NavBar/.metadata/summary.yaml`
with `status: stub` and every field marked `TODO`.

### 3. Fill the stub

Replace the TODO fields with real content, set `status: filled`, `git add`
the summary, and commit again. The gate validates the filled summary
against its schema and lets the commit through.

From then on, every commit that touches an indexed directory must also
touch its `summary.yaml`. There is no honor-system path.

### 4. (Optional) Use state-machine skills

Invoke `validate-issue` to check PR coverage:

```
Skill(atomic-gates:validate-issue, { issue_number: 42, pr_number: 17 })
```

The runner creates a run in `.gates/runs/<id>.yaml`, injects the first
state's task, and you execute one state per turn until the machine reaches
`done`. The final verdict lives in `.gates/runs/<id>/emit_verdict.output.yaml`.

## Why this is different from "just writing rules in CLAUDE.md"

| Approach | What goes wrong |
|---|---|
| "Always document your changes in .metadata/" (rule in CLAUDE.md) | Agent rationalizes: "the metadata is probably still accurate," skips the update, commits |
| `gate-metadata` blocks `git commit` with exit 2 | Commit literally does not happen. No rationalization possible |
| "Always validate PR coverage before merging" (rule in SKILL.md) | Agent vaguely summarizes coverage, emits "COMPLETE" without evidence |
| `validate-issue` state machine forces structured output at each step, validates against schema, enforces enum verdict | Agent cannot emit `COMPLETE` without `file:line` evidence for every requirement |

The difference is not rhetorical. The machine enforces at the level of
the runtime, not the prompt. Agents cannot argue with `exit 2`.

## Development notes

- During development, changes in the checkout do not automatically reach
  the Claude Code runtime because the plugin is loaded from
  `~/.claude/plugins/cache/atomic-gates/atomic-gates/<version>/`. Sync
  changes with `rsync` or (preferably) set up a dev-sync script.
- The runner uses only Python 3 standard library + `pyyaml`. The schema
  validator is intentionally self-contained so the plugin has no
  runtime dependency beyond pyyaml.

## Reference

- [Rules and Gates](https://blog.fsck.com/2026/04/07/rules-and-gates/) — Jesse Vincent, April 2026
