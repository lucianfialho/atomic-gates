# Authoring state-machine skills

This guide walks you through writing a new skill declared as a YAML
state machine, with schema-validated output at every transition. If
you haven't read [Getting started](./getting-started.md), do that first
— this assumes you understand what a gate is and how the plugin is
installed.

The two skills shipped with `atomic-gates` (`validate-issue` and
`review-pr`) are the best references. This guide explains how they're
built so you can build your own.

---

## The shape of a state machine

Every skill lives in `skills/<name>/` and has three files:

```
skills/<name>/
├── skill.yaml                       # the state machine
├── SKILL.md                         # minimal runner-facing instructions
└── schemas/
    └── <state>.output.schema.json   # one per state that produces structured output
```

The runner (`lib/runner.py`) is a `PreToolUse: Skill` hook that
intercepts skill invocations. When the agent calls `Skill(atomic-gates:<name>, { ... })`:

1. The runner loads `skills/<name>/skill.yaml`
2. If `run_id` is in the arguments, it resumes an existing run; otherwise
   it creates a new one
3. It injects the current state's task as a `<system-reminder>` via
   `additionalContext`
4. The agent executes the task (writes a YAML output to `output_path`)
5. The agent re-invokes `Skill(...)` with the `run_id` to advance
6. The runner validates the output against `output_schema`, runs any
   `gate` scripts, evaluates `transitions`, and moves to the next state
7. Repeat until a terminal state is reached

---

## Minimum skill.yaml

Here's the shape, annotated:

```yaml
id: my-skill                          # must match the directory name
version: 1                            # always 1
description: >                        # one-liner, shows up in audit logs
  Short explanation of what this skill does end-to-end.

inputs:
  required:                           # typed args the skill takes at start
    - name: issue_number
      type: integer
    - name: pr_number
      type: integer

initial_state: fetch                  # which state a new run begins in

states:

  fetch:
    description: Fetch the data this skill needs
    agent_prompt: |
      Read issue #{{inputs.issue_number}} and PR #{{inputs.pr_number}}.
      Emit YAML at {{output_path}} with this shape:
        issue: { title: string, body: string }
        pr:    { title: string, files_changed: [string] }
    output_schema: skills/my-skill/schemas/fetch.output.schema.json
    transitions:
      - to: analyze

  analyze:
    description: Extract structured conclusions from the fetched data
    agent_prompt: |
      Read {{output.issue}} and {{output.pr}}.
      Produce conclusions at {{output_path}}:
        findings: [...]
    transitions:
      - to: emit_verdict

  emit_verdict:
    description: Aggregate findings into a final verdict
    agent_prompt: |
      Read {{output.findings}}.
      Emit verdict: OK | PROBLEM
    transitions:
      - to: done

  done:
    terminal: true
    description: Machine finished
```

Required fields: `id`, `version`, `initial_state`, `states`. The
`inputs` block is optional but recommended — it makes the skill's
contract explicit and the runner validates types on invocation.

---

## State fields

Each entry under `states` supports:

| Field | Type | Purpose |
|---|---|---|
| `description` | string | Human-readable label; shown in system reminders |
| `agent_prompt` | string (multiline) | The task injected for this state. Supports `{{...}}` interpolation |
| `output_schema` | string (path) | JSON Schema for the YAML output this state produces. If set, the runner rejects invalid output and retries the state |
| `gate` | list | Optional shell scripts to run after output validation. Each entry has `script` (path) and `on_fail` (e.g. `retry_state`) |
| `transitions` | list | Where to go next. Each entry has `to` (target state) and optional `when` (condition on output) |
| `terminal` | bool | If `true`, this state ends the run. No `agent_prompt` needed |
| `skip_output_check` | bool | If `true`, the state doesn't need an output file to advance. Used by the adapter runtime for prose skills |

---

## Template interpolation

Inside `agent_prompt`, you can reference:

| Expression | Resolves to |
|---|---|
| `{{inputs.<key>}}` | A value from the skill's input dict |
| `{{output_path}}` | The absolute path where this state's output must be written |
| `{{run_id}}` | The current run's UUID (rarely needed — the runner includes it in the footer automatically) |
| `{{outputs.<state>}}` | The output YAML of a previously completed state, rendered as JSON |
| `{{output.<field>}}` | Shortcut for the **immediately previous** state's output, resolved at a field |

`dict` and `list` values are rendered as **JSON strings** (not Python
`repr`), so the agent can parse them reliably. Scalars render as their
string form. Missing references render as empty strings.

---

## Writing an output schema

The runner ships with a small JSON Schema subset validator
(`lib/schema_validate.py`). It supports:

- `type`, `required`, `properties`, `additionalProperties`
- `items`, `minItems`, `minProperties`, `minLength`
- `enum`, `const`, `uniqueItems`

It does **not** support `$ref`, `allOf`/`anyOf`/`oneOf`,
`patternProperties`, or `format`. Keep schemas in the subset.

Example from `skills/validate-issue/schemas/fetch.output.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "validate-issue/fetch output",
  "type": "object",
  "additionalProperties": false,
  "required": ["issue", "pr"],
  "properties": {
    "issue": {
      "type": "object",
      "additionalProperties": false,
      "required": ["title", "body"],
      "properties": {
        "title": { "type": "string", "minLength": 1 },
        "body": { "type": "string" },
        "comments": { "type": "array", "items": { "type": "string" } }
      }
    },
    "pr": {
      "type": "object",
      "additionalProperties": false,
      "required": ["title", "files_changed"],
      "properties": {
        "title": { "type": "string", "minLength": 1 },
        "files_changed": { "type": "array", "items": { "type": "string" }, "minItems": 1 }
      }
    }
  }
}
```

Two things make this schema effective:

- `additionalProperties: false` — the agent can't sneak extra fields
- `required` on every level that matters — missing fields are caught

Rule of thumb: **if a field is ever referenced in a downstream state's
`agent_prompt`, mark it required in the upstream state's schema.**

---

## Transitions with `when`

Transitions are evaluated in order. The first one whose `when` matches
(or has no `when`) wins:

```yaml
emit_verdict:
  agent_prompt: |
    Read {{output.coverage}}.
    Emit verdict: COMPLETE | INCOMPLETE | NEEDS_DISCUSSION
  transitions:
    - to: done
      when: "output.verdict == 'COMPLETE'"
    - to: implement
      when: "output.verdict == 'INCOMPLETE'"
    - to: needs_human
      when: "output.verdict == 'NEEDS_DISCUSSION'"
```

The `when` expression supports simple comparisons (`==`, `!=`, `<`,
`<=`, `>`, `>=`) against dotted field paths. Literals are strings
(quoted), numbers, `true`, or `false`. No `and`/`or`/`not` — if you
need compound logic, split it across multiple transitions in the right
order.

**The runner validates the output before evaluating transitions.** If
the schema rejects the output, the machine stays in the current state
and re-injects the task with the validation error. Transitions never
run against invalid data.

---

## The minimal SKILL.md

Every skill needs a `SKILL.md` because that's what Claude Code's `Skill`
tool loads when the agent invokes the skill. The runner then takes over
via the `PreToolUse: Skill` hook, but the agent still needs something
to read first.

Use this stub as a template:

```markdown
---
name: my-skill
description: One-sentence "use when..." — see CSO rules, don't summarize the workflow
---

# my-skill

This skill runs as a gates state machine. Each turn, the runner injects
a `<system-reminder>` telling you what state you're in, what task to
perform, and where to write the output.

## How to act each turn

- Read the `<system-reminder>` carefully
- Execute the task it describes
- Write the YAML at the exact `output_path` the runner specified
- Invoke `Skill(atomic-gates:my-skill, { run_id: '<id>' })` to advance
- Do not try to do all states in one turn — each state is a separate turn
- Do not skip writing the YAML output — the runner won't advance without it
```

That's it. The real instructions live in `skill.yaml`, injected at the
right moment by the runner.

---

## Developer workflow

### 1. Write the files

```
skills/my-skill/skill.yaml
skills/my-skill/SKILL.md
skills/my-skill/schemas/<state>.output.schema.json  (one per validated state)
```

### 2. Add the skill to dev-sync

Edit `scripts/dev-sync.sh` and add `skills/my-skill` to `SYNC_DIRS`.
This ensures the runtime picks it up when you run the script.

### 3. Sync to the install paths

```bash
./scripts/dev-sync.sh
```

### 4. Smoke test standalone

You can exercise the machine without reloading Claude Code:

```bash
# Create a new run
CLAUDE_PLUGIN_ROOT=$PWD CLAUDE_PROJECT_DIR=/tmp/my-test \
  python3 lib/runner.py <<<'{"tool_name":"Skill","tool_input":{"skill":"atomic-gates:my-skill","args":"issue_number=42 pr_number=17"}}'

# The runner prints the first state's additionalContext and creates .gates/runs/<id>.yaml.
# Manually write /tmp/my-test/.gates/runs/<id>/fetch.output.yaml matching your schema.
# Then advance:

CLAUDE_PLUGIN_ROOT=$PWD CLAUDE_PROJECT_DIR=/tmp/my-test \
  python3 lib/runner.py <<<'{"tool_name":"Skill","tool_input":{"skill":"atomic-gates:my-skill","args":"run_id=<id-from-above>"}}'
```

Iterate until every transition works, the final state emits the
verdict you expect, and invalid outputs are rejected with useful
error messages.

### 5. Test in a live Claude Code session

Open Claude Code in a fresh directory and invoke:

> Use the skill atomic-gates:my-skill passing issue_number=42 and pr_number=17.

If the runner is wired correctly, Claude receives the first state's
task as a system reminder, executes it, writes the YAML, and invokes
`Skill(...)` with the `run_id` to advance. Walk through every state.

---

## Common pitfalls

**Forgot to add the skill to `SYNC_DIRS`.** The runner looks up
skill.yaml via `CLAUDE_PLUGIN_ROOT`, which points at the **installed**
plugin, not the checkout. If you edit a skill in the checkout but
don't sync, nothing changes at runtime. Run `./scripts/dev-sync.sh`
after every edit.

**Output schema is too strict.** If the agent legitimately can't
produce a field (e.g. an issue has no comments and `comments: [string]`
is required), the machine locks in a retry loop. Make optional fields
actually optional.

**Output schema is too loose.** If `additionalProperties` isn't set
to `false`, the agent may emit extra fields that downstream states
accidentally reference and get wrong data. Default to strict.

**Circular transitions without a break condition.** If state A transits
to state B and state B transits back to state A based on output, make
sure at least one path eventually reaches a terminal state. The runner
doesn't detect infinite loops — you'll burn tokens.

**`{{output.X}}` returns empty.** This shortcut resolves to the
immediately previous state's output. If you need output from three
states ago, use `{{outputs.<state_name>.X}}` instead.

**The agent invokes the skill without a `run_id` in the middle of a
run.** This creates a new run instead of advancing the existing one.
The runner doesn't detect this — you end up with an orphaned run.
Fix: make the `SKILL.md` stub emphatic about "when finished, invoke
with the `run_id` from the reminder."

---

## Shipping skills in a separate plugin (cross-plugin discovery)

You don't have to ship your state-machine skills inside `atomic-gates`
itself. Since v0.3.0, the runner discovers skills across **any**
installed plugin. This is what lets a dedicated plugin (for example,
an `autonomous-dev-pipeline`) ship its own `skills/<name>/skill.yaml`
files and have them executed by the atomic-gates runner as native
state machines — not flattened into single-state adapted runs.

### How discovery works

When the agent invokes `Skill(my-plugin:solve-issue, { ... })`:

1. Runner extracts `namespace=my-plugin` and `skill_name=solve-issue`.
2. Runner looks for `skills/solve-issue/skill.yaml` under the current
   plugin root (atomic-gates itself). **Not found.**
3. Runner falls back to `~/.claude/plugins/**/skills/solve-issue/skill.yaml`,
   preferring matches whose path contains `my-plugin`.
4. When it finds the external `skill.yaml`, it:
   - Validates it against `schemas/skill-machine.schema.json` from atomic-gates (the schema is authoritative)
   - Walks up from the file to find the owning plugin root (looking for `.claude-plugin/` or `skills/` + `hooks/` siblings)
   - Stores that root internally so `output_schema` paths inside the external skill resolve correctly
   - Namespaces the `id` in the run-state as `my-plugin:solve-issue` for unambiguous audit trail

### What this unlocks

You can now build a **separate plugin** whose entire value proposition
is a corpus of state-machine skills, and use atomic-gates strictly as
the runtime. Two concrete examples:

- **A dev-pipeline plugin**: `skills/solve-issue`, `skills/backend-dev`,
  `skills/frontend-dev`, etc. Each as a state machine with schema-
  validated transitions. Install `atomic-gates` alongside and every
  skill gets audit trail, schema validation, and run persistence for
  free.

- **A domain-specific pipeline**: your team ships a plugin with skills
  like `ship-new-feature`, `investigate-incident`, `migrate-schema`.
  Each is a state machine tuned for your workflow. `atomic-gates`
  never changes — it just runs them.

### Constraints

Three things to be aware of when shipping skills in an external plugin:

1. **Your skill.yaml paths are relative to YOUR plugin root**, not
   atomic-gates. `output_schema: skills/foo/schemas/bar.json` resolves
   inside your plugin. Good practice: always use the full path from
   your plugin root (`skills/<name>/schemas/<state>.output.schema.json`)
   rather than trying to use `..` or absolute paths.

2. **The schema is atomic-gates' schema, not yours.** You can't extend
   the state-machine schema from your plugin — your `skill.yaml` must
   conform to `schemas/skill-machine.schema.json` in atomic-gates.
   If you need fields atomic-gates doesn't support, file an issue there.

3. **Skill name collisions.** If two plugins both ship
   `skills/solve-issue/skill.yaml`, the namespace in the invocation
   disambiguates: `Skill(plugin-a:solve-issue)` vs
   `Skill(plugin-b:solve-issue)`. But if you invoke without a
   namespace, the first match wins — test both orders.

---

## See also

- [Refining converter skeletons](./refining-skeletons.md) — the companion guide for when you *didn't* write `skill.yaml` from scratch but generated it from an existing `SKILL.md` via `lib/import_skill.py` and want to promote the mechanical first draft into a production state machine
- [`claude-dev-pipeline/skills/validate-issue/skill.yaml`](https://github.com/lucianfialho/claude-dev-pipeline/blob/main/skills/validate-issue/skill.yaml) — 4-state machine, uses `output_schema` on the first state (refined, not converter-generated)
- [`claude-dev-pipeline/skills/review-pr/skill.yaml`](https://github.com/lucianfialho/claude-dev-pipeline/blob/main/skills/review-pr/skill.yaml) — 3-state machine with findings aggregation (refined, not converter-generated)
- [`schemas/skill-machine.schema.json`](../../schemas/skill-machine.schema.json) — the JSON Schema every `skill.yaml` must match
- [`docs/atomic-gates.md`](../atomic-gates.md) — full technical reference
