# atomic-gates

**Turn project rules into verifiable artifacts.** A plugin for Claude Code that
replaces declarative rules ("always run tests before committing", "always
update the metadata") with **blocking gates** — hooks that inspect concrete
artifacts and refuse to let the agent move forward unless those artifacts
exist and pass validation.

> *Rules are fragile because LLMs rationalize their way around them.
> Gates are robust because the next action literally cannot happen until
> the gate condition is met.*
> — Jesse Vincent, [**Rules and Gates**](https://blog.fsck.com/2026/04/07/rules-and-gates/)

This plugin is a full implementation of that thesis.

---

## The problem

You write in `CLAUDE.md`:

> Always run the tests before saying a task is done.
> Always update `.metadata/` when you touch a directory.
> Always validate that a PR covers all the issue's requirements.

And the agent, most of the time, does. Until it doesn't. It "remembered"
the tests probably pass. It "checked" the metadata was still accurate. It
"reviewed" the coverage and everything "looked good."

That's not discipline failing. That's the **architecture** failing — the
rule has a rationalization escape hatch, and every rule eventually gets
used.

Gates close the escape hatch by making the next step **mechanically
impossible** without producing a concrete artifact that proves the rule
was followed.

---

## The idea

Two kinds of gates, composed:

### 1. Atomic gates — single-shot blocking hooks

A hook inspects one condition and blocks one action.

**Example: `gate-metadata`**

Configured in `.gates/config.yaml`:

```yaml
version: 1
project:
  name: my-app
indexed_directories:
  - path: components/NavBar
    specialist: frontend
  - path: app/api/users/[id]
    specialist: backend
```

Now `git commit` that touches `components/NavBar/` **fails with exit 2**
if there is no `.metadata/summary.yaml` in that directory, or if the
summary isn't staged, or if it has `status: stub` (still has TODOs), or
if it fails schema validation. A stub is auto-created on the first
failure so the agent knows what to fill in.

No prompt asks the agent to remember. The commit just doesn't happen.

### 2. Composed gates — skills as state machines

A skill is declared as a YAML state machine. Each state has:

- An `agent_prompt` (the task for this turn)
- An `output_schema` (the shape the output must match)
- Optional `gate` scripts that run before transitioning
- `transitions` with `when` conditions

A `PreToolUse: Skill` hook intercepts skill invocations, loads the
machine, injects the current state's task as a `<system-reminder>`, and
refuses to advance until the agent produces a valid output. Runs
persist in `.gates/runs/<run_id>.yaml`, so crashes and resumes are free.

**Example: `validate-issue`**

```yaml
id: validate-issue
initial_state: fetch
states:
  fetch:
    agent_prompt: |
      Fetch issue #{{inputs.issue_number}} and PR #{{inputs.pr_number}}.
      Emit YAML at {{output_path}}: { issue: {...}, pr: {...} }
    output_schema: skills/validate-issue/schemas/fetch.output.schema.json
    transitions:
      - to: extract_requirements
  extract_requirements:
    agent_prompt: |
      Read {{output.issue}}. Extract every discrete requirement.
      Emit YAML at {{output_path}}: { requirements: [...] }
    transitions:
      - to: check_coverage
  check_coverage:
    # ... etc
  emit_verdict:
    agent_prompt: |
      Emit final verdict: COMPLETE | INCOMPLETE | NEEDS_DISCUSSION
    transitions:
      - to: done
  done:
    terminal: true
```

The agent cannot emit `COMPLETE` without first producing a
`check_coverage.output.yaml` with concrete `file:line` evidence for every
requirement. The state machine enforces that at the runtime level, not
the prompt level.

---

## What ships today

**Atomic gates:**

- `gate-metadata` — blocks `git commit` without updated `.metadata/summary.yaml`

**State-machine skills:**

- `validate-issue` — five-state machine that verifies PR coverage against issue

**Substrate:**

- State-machine runner (`PreToolUse: Skill` hook)
- JSON Schema subset validator, self-contained (only depends on `pyyaml`)
- Schemas for config, skill machines, run state, metadata summaries
- Stub templates for lazy bootstrap

---

## Install

```bash
claude plugin marketplace add lucianfialho/atomic-gates
claude plugin install atomic-gates
```

---

## Adopt it in a project

### 1. Declare what's indexed

Create `.gates/config.yaml` in your project root:

```yaml
version: 1
project:
  name: my-app
indexed_directories:
  - path: components/NavBar
    specialist: frontend
```

### 2. Commit something touching an indexed directory

The commit will fail. A stub summary will appear at
`components/NavBar/.metadata/summary.yaml`. Fill it in, stage it, commit
again.

### 3. (Optional) Use state-machine skills

```
Skill(atomic-gates:validate-issue, { issue_number: 42, pr_number: 17 })
```

The runner takes over. Each turn is a state. Follow the system-reminder
instructions until the machine reaches `done`.

---

## Architecture

```
atomic-gates/
├── hooks/hooks.json          PreToolUse: Bash → gate-metadata
│                             PreToolUse: Skill → state-machine runner
├── lib/
│   ├── runner.py             the arbiter for state-machine skills
│   ├── gate_metadata.py      the commit gate
│   └── schema_validate.py    self-contained JSON Schema subset
├── schemas/                  JSON Schemas for config, machines, runs, metadata
├── templates/                stub files for lazy bootstrap
└── skills/<name>/
    ├── skill.yaml            the state machine
    ├── SKILL.md              minimal agent-facing notes
    └── schemas/              output schemas for each state
```

Full technical reference: [`docs/atomic-gates.md`](./docs/atomic-gates.md).

---

## Why "atomic"?

Every gate is **indivisible**: passes as a whole or fails as a whole.
State machines compose multiple atomic gates in sequence, but composition
doesn't weaken any individual gate — each transition is still
all-or-nothing. The name is accurate, not decorative.

---

## Development

Python 3 + `pyyaml` (standard on macOS). Zero runtime dependencies beyond
that. Schemas are validated by a minimal self-contained subset validator
in `lib/schema_validate.py` — no `jsonschema` / `ajv` needed.

Smoke tests:

```bash
# Atomic gate standalone
CLAUDE_PLUGIN_ROOT=$PWD CLAUDE_PROJECT_DIR=/tmp/gates-smoke \
  python3 lib/gate_metadata.py <<<'{"tool_name":"Bash","tool_input":{"command":"git commit -m x"}}'

# State-machine runner standalone
CLAUDE_PLUGIN_ROOT=$PWD CLAUDE_PROJECT_DIR=/tmp/gates-smoke \
  python3 lib/runner.py <<<'{"tool_name":"Skill","tool_input":{"skill":"validate-issue","args":"issue_number=42 pr_number=17"}}'
```

During dev, the plugin is loaded from
`~/.claude/plugins/cache/atomic-gates/atomic-gates/<version>/`, not from
the checkout. Sync changes with:

```bash
./scripts/dev-sync.sh          # mirror checkout into install paths
./scripts/dev-sync.sh --dry    # preview without writing
```

The script mirrors `.claude-plugin/`, `hooks/`, `lib/`, `schemas/`,
`templates/`, `docs/`, and `skills/validate-issue/` into both the cache
and marketplace install paths. Idempotent.

---

## Reference

- [**Rules and Gates**](https://blog.fsck.com/2026/04/07/rules-and-gates/) — Jesse Vincent, April 2026
