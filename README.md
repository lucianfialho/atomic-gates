# atomic-gates

**Replayable, auditable multi-agent workflows on Claude Code.**
Declare your agent pipeline as a YAML state machine; every state output,
every delegation, every sub-run is persisted to `.gates/runs/<uuid>.yaml` —
navigable, analyzable, resumable. The same runtime ships three atomic
`PreToolUse` gates (commit metadata, PR body structure, role scope)
whose firing behavior is tracked via a local telemetry log.

> **30-second pitch:**
> Claude Code sessions normally evaporate when a tab closes.
> atomic-gates turns them into durable state machines. A parent
> `solve-issue` fires a `backend-dev` sub-run; both persist; an
> analyzer can tell you which skill ran, where it got stuck, what
> output each state produced — months later, in 180 lines of Python.

> *Rules are fragile because LLMs rationalize their way around them.
> Gates are robust because the next action literally cannot happen until
> the gate condition is met.*
> — Jesse Vincent, [**Rules and Gates**](https://blog.fsck.com/2026/04/07/rules-and-gates/)

atomic-gates implements that thesis as a plugin. The enforcement
claim is held to a high evidentiary bar — see
[`validation/`](./validation/) for the pre-registered hypotheses and
the [ledger](./validation/ledger.md) tracking which ones survived
contact with real data.

> ⚠️ **Status: experimental, honestly measured.** Shipping infra is
> proven (31 real runs across 2 projects, 87% terminate cleanly,
> declarative delegation works end-to-end — see
> [`docs/dogfood/solve-issue-run.md`](./docs/dogfood/solve-issue-run.md)).
> Enforcement claims ("gates block errors") are currently under
> instrumentation — see [`validation/ledger.md`](./validation/ledger.md)
> for open verdicts. API will change; feedback welcome.

---

## What 31 real runs showed

Before believing the pitch, we ran a retrospective analyzer over
`.gates/runs/` from two real projects. Four hypotheses were
pre-registered with kill criteria *before* looking at data
([`validation/hypotheses.yaml`](./validation/hypotheses.yaml)). Three
out of four killed their marketing version immediately:

| Hypothesis | Verdict | Evidence |
|---|---|---|
| H1: machine-level gates fire in practice | ❔ **inconclusive** | instrument was blind — runner never persisted failures (fixed in commit [df07912](../../commit/df07912), issue [#24](../../issues/24)) |
| H2: runs reach terminal reliably | ✅ **surviving (87%)** | 27/31 terminal, 4 abandoned; GC landed via issue [#26](../../issues/26) |
| H3: rigor skills are actually used | 💀 **killed** | `validate-issue` ran 2× against 13× `solve-issue` — behavioral, not a bug |
| H4: skeleton skills don't trap the runner | 💀 **killed** | one run stuck 64h on `usage` state; fixed in commit [658e9ac](../../commit/658e9ac), issue [#25](../../issues/25) |

What the data **did** support, with zero hedging:

- **Declarative delegation works end-to-end.** `solve-issue` → `backend-dev`
  appeared 11× as proper parent/child sub-runs with bidirectional linking.
- **Cross-plugin discovery works.** `obra/superpowers:brainstorming`
  ran through atomic-gates' runner without any config wire-up.
- **The audit trail is real and queryable.** The retrospective above
  is a 180-LOC Python script reading nothing but YAML. Try doing that
  on a raw Claude Code session.

Full ledger, stats, and protocol at [`validation/`](./validation/).

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

**Atomic gates (blocking hooks — firings logged to `.gates/hook-log.jsonl`):**

- `gate-metadata` — blocks `git commit` without updated `.metadata/summary.yaml`
- `gate-pr-structure` — blocks `gh pr create` with missing required sections
- `gate-role` — blocks `Edit`/`Write` outside the active specialist's scope

**Runtime substrate:**

- State-machine runner (`PreToolUse: Skill` hook, Python)
- Cross-plugin skill discovery — runs `skill.yaml` from ANY installed plugin
- Project scanner + config generator (`lib/init.py`) — detects stack, suggests indexed dirs
- Offline SKILL.md → skill.yaml converter (`lib/import_skill.py`)
- Run garbage collector (`lib/gc_runs.py`) — marks stale runs as `abandoned`
- Self-contained JSON Schema subset validator (only runtime dep is `pyyaml`)
- Schemas for config, skill machines, run state, metadata summaries
- Stub templates for lazy bootstrap
- `scripts/dev-sync.sh` for mirroring the checkout into Claude Code install paths

**Validation tooling (`validation/`):**

- `hypotheses.yaml` — pre-registered, falsifiable claims about atomic-gates itself
- `analyze_runs.py` — retrospective analyzer over `.gates/runs/` across projects
- `analyze_hooks.py` — aggregator for `.gates/hook-log.jsonl` (firing/block rates per gate)
- `ledger.md` — auto-generated verdicts (claim → evidence → verdict)

**No skills.** `atomic-gates` is a pure runtime. For a ready-to-use
state-machine skill corpus, install
[`lucianfialho/claude-dev-pipeline`](https://github.com/lucianfialho/claude-dev-pipeline)
alongside — it ships 15 skills (`solve-issue`, `review-pr`,
`validate-issue`, specialists, review passes) consumed by this runtime
via cross-plugin discovery.

---

## End-to-end dogfood

Rather than describe what the runtime does, here's a real execution:
[`docs/dogfood/solve-issue-run.md`](./docs/dogfood/solve-issue-run.md).

It's a verified walk-through of `claude-dev-pipeline:solve-issue`
resolving a simulated issue end-to-end. Five states in the parent,
three in the sub, one delegation boundary, schema-validated output at
every transition. Every YAML file in
[`docs/dogfood/solve-issue-run/`](./docs/dogfood/solve-issue-run/) is
a direct copy of what the runner wrote to disk during the run —
nothing reconstructed, nothing staged for the docs.

If you want to see atomic-gates doing what the pitch says, read that
first. The parent's history ends with a `sub_run_id` pointing at the
sub-run; the sub ends with `parent_run_id` / `parent_state` /
`parent_skill_id` linking back. The delegation is bidirectionally
auditable.

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

### 1. Scan and generate config

Run the init scanner on your project:

```bash
# Report mode — see what the scanner finds
python3 lib/init.py /path/to/project

# Auto mode — generate .gates/config.yaml from scan results
python3 lib/init.py --auto /path/to/project

# Pick specific directories only
python3 lib/init.py --auto --candidates 'src/components,src/api' /path/to/project
```

The scanner detects your stack (Node, Python, Rust, …), identifies
candidate directories by name patterns and file extensions, assigns
specialists (`frontend`, `backend`, `database`, `infra`, `test`), and
writes a `.gates/config.yaml` ready to use.

Or create it manually:

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
Skill(claude-dev-pipeline:validate-issue, { issue_number: 42, pr_number: 17 })
Skill(claude-dev-pipeline:review-pr, { pr_number: 42 })
```

The runner takes over. Each turn is a state. Follow the system-reminder
instructions until the machine reaches `done`. The final verdict is in
`.gates/runs/<run_id>/<terminal_state>.output.yaml`.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Claude Code Runtime (Host)                  │
│         (PreToolUse · Stop · TaskCompleted)              │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   hooks/hooks.json                       │
│              (Matcher → Gate Dispatch)                    │
└─────────┬──────────────┬──────────────┬─────────────────┘
          │              │              │
   ┌──────┘              │              └──────┐
   ▼                     ▼                     ▼
┌────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Bash      │  │  Skill          │  │  Edit | Write   │
│  Matcher   │  │  Matcher        │  │  Matcher        │
└─────┬──────┘  └───────┬─────────┘  └───────┬─────────┘
      │                 │                     │
      ▼                 ▼                     ▼
┌────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ gate_      │  │    runner.py    │  │   gate_role.py  │
│ metadata   │  │  (State-Machine │  │  (Specialist    │
│ gate_pr    │  │   Arbiter)      │  │   Scope Check)  │
│ _structure │  │                 │  │                 │
└────────────┘  └───────┬─────────┘  └─────────────────┘
                        │
           ┌────────────┼────────────┐
           ▼            ▼            ▼
┌────────────┐ ┌──────────────┐ ┌──────────────────────┐
│  Cross-    │ │  Schema      │ │  Template            │
│  Plugin    │ │  Validator   │ │  Bootstrap           │
│  Discovery │ │  (validate.  │ │  (Stub Gen)          │
│  (skill.   │ │   py)        │ │                      │
│   yaml)    │ └──────────────┘ └──────────────────────┘
└────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│            Persistence (.gates/ + .metadata/)            │
│   config.yaml · runs/<id>.yaml · <state>.output.yaml    │
│       .metadata/summary.yaml · skill.yaml (YAML SM)     │
└─────────────────────────────────────────────────────────┘
```

### File layout

```
atomic-gates/
├── hooks/hooks.json          PreToolUse: Bash → gate_metadata, gate_pr_structure
│                             PreToolUse: Skill → runner.py
│                             PreToolUse: Edit|Write → gate_role
├── lib/
│   ├── runner.py             state-machine arbiter
│   ├── gate_metadata.py      commit gate — blocks without .metadata/summary.yaml
│   ├── gate_pr_structure.py  PR gate — blocks without required sections
│   ├── gate_role.py          role gate — blocks edits outside specialist scope
│   ├── init.py               project scanner + config generator
│   ├── import_skill.py       SKILL.md → skill.yaml converter
│   └── schema_validate.py    self-contained JSON Schema subset
├── schemas/                  JSON Schemas for config, machines, runs, metadata
├── templates/                stub files for lazy bootstrap
└── scripts/
    ├── dev-sync.sh           mirror checkout → Claude Code install paths
    ├── check-tests.sh        legacy quality gate (Stop hook)
    └── check-build.sh        legacy build check (TaskCompleted hook)
```

Skills don't live here — they belong in external plugins (like
[`claude-dev-pipeline`](https://github.com/lucianfialho/claude-dev-pipeline))
which the runner discovers via cross-plugin search.

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
  python3 lib/runner.py <<<'{"tool_name":"Skill","tool_input":{"skill":"claude-dev-pipeline:validate-issue","args":"issue_number=42 pr_number=17"}}'
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
