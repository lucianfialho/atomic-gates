# atomic-gates

**Turn project rules into verifiable artifacts.** A plugin for Claude Code
that replaces declarative rules ("always run the tests before committing",
"always update the metadata", "always validate PR coverage") with
**blocking gates** — hooks that inspect concrete artifacts and refuse to
let the agent advance unless those artifacts exist and pass schema
validation.

> *Rules are fragile because LLMs rationalize their way around them.
> Gates are robust because the next action literally cannot happen until
> the gate condition is met.*
> — Jesse Vincent, [**Rules and Gates**](https://blog.fsck.com/2026/04/07/rules-and-gates/)

`atomic-gates` is a direct implementation of that thesis at the plugin
runtime level.

> **New here?** → [Get started in 5 minutes](./docs/guides/getting-started.md)
> &nbsp;·&nbsp; [Using with `superpowers`](./docs/guides/using-with-superpowers.md)
> &nbsp;·&nbsp; [Author a gate](./docs/guides/authoring-atomic-gates.md)
> &nbsp;·&nbsp; [Author a state machine](./docs/guides/authoring-state-machines.md)

---

## The problem rules have

You write in `CLAUDE.md`:

> Always run the tests before saying a task is done.
> Always update `.metadata/` when you touch a directory.
> Always validate that a PR covers the linked issue's requirements.

And the agent, most of the time, does. Until it doesn't. It "remembered"
the tests probably pass. It "checked" that the metadata was still
accurate. It "reviewed" the coverage and everything "looked good."

That's not discipline failing. That's the **architecture** failing — the
rule has a rationalization escape hatch, and every rule eventually gets
used.

Gates close the escape hatch by making the next step **mechanically
impossible** without producing a concrete artifact that proves the rule
was followed.

---

## Two kinds of gates

### 1. Atomic gates — single-shot blocking hooks

A hook inspects one condition and blocks one action.

**Example: `gate-metadata`**

Configured in your project's `.gates/config.yaml`:

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
summary isn't staged, or if it still has `status: stub` (has TODOs), or
if it fails schema validation. A stub is auto-created on the first
failure so the agent knows exactly what to fill in.

No prompt asks the agent to remember. The commit just doesn't happen.

### 2. Composed gates — skills as state machines

A skill is declared as a YAML state machine. Each state has:

- An `agent_prompt` — the task for this turn
- An `output_schema` — the shape the output must match
- Optional `gate` scripts that run before transitioning
- `transitions` with optional `when` conditions

A `PreToolUse: Skill` hook intercepts skill invocations, loads the
machine, injects the current state's task as a `<system-reminder>`, and
refuses to advance until the agent produces a valid output. Runs persist
in `.gates/runs/<run_id>.yaml`, so crashes and resumes are free.

**Example shape:**

```yaml
id: validate-issue
initial_state: fetch
states:
  fetch:
    agent_prompt: |
      Fetch issue #{{inputs.issue_number}} and PR #{{inputs.pr_number}}.
      Emit YAML at {{output_path}} with this shape: {...}
    output_schema: skills/validate-issue/schemas/fetch.output.schema.json
    transitions:
      - to: extract_requirements
  extract_requirements:
    # ...
  emit_verdict:
    agent_prompt: |
      Emit final verdict: COMPLETE | INCOMPLETE | NEEDS_DISCUSSION
    transitions:
      - to: done
  done:
    terminal: true
```

The agent cannot emit `COMPLETE` without first producing valid structured
output for each prior state, including `check_coverage.output.yaml` with
`file:line` evidence for every requirement. The state machine enforces
that **at the runtime level**, not the prompt level.

---

## What ships today

**Atomic gates:**

- `gate-metadata` — blocks `git commit` without updated `.metadata/summary.yaml`

**State-machine skills:**

- `validate-issue` — 4 states: `fetch → extract_requirements → check_coverage → emit_verdict → done`
- `review-pr` — 3 states: `fetch → review → emit_verdict → done`, with findings tagged by domain + severity

**Substrate:**

- State-machine runner (`PreToolUse: Skill` hook, Python)
- Self-contained JSON Schema subset validator (only runtime dep is `pyyaml`)
- Schemas for config, skill machines, run state, metadata summaries
- Stub templates for lazy bootstrap
- `scripts/dev-sync.sh` for mirroring the checkout into Claude Code install paths

---

## How this fits with `superpowers`

[`obra/superpowers`](https://github.com/obra/superpowers) is the most
polished skill corpus in the Claude Code ecosystem — 14 skills covering
brainstorming, TDD, worktrees, planning, and code review, curated
aggressively by the same author who wrote *Rules and Gates*. It's
battle-tested, cross-harness (works in Claude Code, Cursor, Codex,
OpenCode, Copilot CLI, Gemini CLI), and shipped as a full methodology
package.

**`atomic-gates` is not an alternative to `superpowers`. It's the
enforcement layer for it.**

The two projects solve complementary problems:

| | `superpowers` | `atomic-gates` |
|---|---|---|
| Scope | Content — 14 polished skills | Infrastructure — hooks + runner + schemas |
| Skill format | Markdown prose with rationalization tables | YAML state machines with JSON Schema |
| Enforcement | Prompt injection + persuasion | `PreToolUse` hooks with `exit 2` and schema validation |
| Target | "Give me a disciplined dev workflow tomorrow" | "Make the rules in our workflow mechanically unbreakable" |

**You probably want both.** Install `superpowers` for the skill library;
install `atomic-gates` for the atomic commit/PR gates and for authoring
your own skills as verified state machines when the discipline of prose
isn't enough for a given domain.

For a detailed comparison and the roadmap for interop (adapter runtime so
`atomic-gates` can run `superpowers` skills with audit-trail), see
[`docs/compatibility-with-superpowers.md`](./docs/compatibility-with-superpowers.md).

---

## Install

```bash
claude plugin marketplace add lucianfialho/atomic-gates
claude plugin install atomic-gates
```

After installing, the fastest way to see a gate fire is the
**[Getting started](./docs/guides/getting-started.md)** guide — a
five-minute hello-world that installs the plugin, configures a scratch
project, watches a `git commit` get blocked, and unblocks it.

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

The commit fails. A stub appears at
`components/NavBar/.metadata/summary.yaml`. Fill it in, stage it, commit
again. From then on, every commit that touches an indexed directory has
to come with a fresh summary.

### 3. (Optional) Use state-machine skills

```
Skill(atomic-gates:validate-issue, { issue_number: 42, pr_number: 17 })
Skill(atomic-gates:review-pr, { pr_number: 42 })
```

The runner takes over. Each turn is a state. Follow the system-reminder
instructions until the machine reaches `done`. The final verdict is in
`.gates/runs/<run_id>/<terminal_state>.output.yaml`.

---

## Architecture

```
atomic-gates/
├── hooks/hooks.json          PreToolUse: Bash → gate-metadata.py
│                             PreToolUse: Skill → runner.py
├── lib/
│   ├── runner.py             state-machine arbiter
│   ├── gate_metadata.py      the commit gate
│   └── schema_validate.py    self-contained JSON Schema subset
├── schemas/                  JSON Schemas for config, machines, runs, metadata
├── templates/                stub files for lazy bootstrap
├── scripts/
│   ├── dev-sync.sh           mirror checkout → Claude Code install paths
│   └── check-tests.sh        legacy quality gate (Stop hook)
└── skills/<name>/
    ├── skill.yaml            the state machine
    ├── SKILL.md              minimal runner-facing instructions
    └── schemas/              per-state output schemas
```

**Guides (start here):**

- [Getting started](./docs/guides/getting-started.md) — hello-world in 5 minutes
- [Using with `superpowers`](./docs/guides/using-with-superpowers.md) — how both plugins coexist
- [Authoring state-machine skills](./docs/guides/authoring-state-machines.md) — write a new skill
- [Authoring atomic gates](./docs/guides/authoring-atomic-gates.md) — write a new blocking hook
- [Refining converter skeletons](./docs/guides/refining-skeletons.md) — promote a `skill.yaml` generated by `lib/import_skill.py` into a production state machine

**Reference:**

- [`docs/atomic-gates.md`](./docs/atomic-gates.md) — full technical reference (schemas, layout, runtime)
- [`docs/compatibility-with-superpowers.md`](./docs/compatibility-with-superpowers.md) — positioning vs `superpowers`

---

## Why "atomic"?

Every gate is **indivisible**: it passes as a whole or fails as a whole,
with no intermediate state. State machines compose multiple atomic gates
in sequence, but composition doesn't weaken any individual gate — each
transition is still all-or-nothing. The name is descriptive, not
decorative.

---

## Development

Python 3 + `pyyaml` (standard on macOS). Zero runtime deps beyond that.
Schemas are validated by a minimal self-contained subset in
`lib/schema_validate.py` — no `jsonschema` / `ajv` / `zod` / anything
else.

Smoke tests:

```bash
# Atomic commit gate standalone
CLAUDE_PLUGIN_ROOT=$PWD CLAUDE_PROJECT_DIR=/tmp/gates-smoke \
  python3 lib/gate_metadata.py <<<'{"tool_name":"Bash","tool_input":{"command":"git commit -m x"}}'

# State-machine runner standalone
CLAUDE_PLUGIN_ROOT=$PWD CLAUDE_PROJECT_DIR=/tmp/gates-smoke \
  python3 lib/runner.py <<<'{"tool_name":"Skill","tool_input":{"skill":"atomic-gates:validate-issue","args":"issue_number=42 pr_number=17"}}'
```

During dev, the plugin is loaded from
`~/.claude/plugins/cache/atomic-gates/atomic-gates/<version>/`, not from
the checkout. Sync changes with:

```bash
./scripts/dev-sync.sh          # mirror checkout into install paths
./scripts/dev-sync.sh --dry    # preview without writing
```

Idempotent. Excludes `__pycache__` and `*.pyc`.

---

## Reference

- [**Rules and Gates**](https://blog.fsck.com/2026/04/07/rules-and-gates/) — Jesse Vincent, April 2026 (the inspiration)
- [`obra/superpowers`](https://github.com/obra/superpowers) — the skill corpus `atomic-gates` complements
