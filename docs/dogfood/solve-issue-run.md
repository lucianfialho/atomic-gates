# Dogfood: `solve-issue` end-to-end run

This document is a **real, verifiable end-to-end execution** of the
`claude-dev-pipeline:solve-issue` orchestrator against the atomic-gates
runtime. Every file in
[`solve-issue-run/`](./solve-issue-run/) is a direct copy of what the
runner produced on disk during the run — nothing was reconstructed
after the fact.

This is the kind of thing I mean when I say atomic-gates is a runtime
for state-machine skill orchestration. The mechanics described in the
README are not hypothetical; they run against real plugin installs and
produce the traces shown below.

---

## What the run demonstrates

- **Two state machines composed via `delegate_to`** — `solve-issue`
  (the parent orchestrator) delegates to `backend-dev` (a specialist
  sub-skill). Both are real skills shipped in
  [`lucianfialho/claude-dev-pipeline`](https://github.com/lucianfialho/claude-dev-pipeline).
- **Schema-validated output at every transition** — each state has a
  JSON Schema for its output; invalid output is rejected and the agent
  is asked to retry.
- **Cross-plugin skill discovery** — the runner lives in atomic-gates
  but the skills live in claude-dev-pipeline. The runner finds them
  via `~/.claude/plugins/**` at invocation time.
- **Bidirectional audit trail** — the parent's history records
  `sub_run_id`; the sub's run-state records `parent_run_id`,
  `parent_state`, and `parent_skill_id`. Every execution is traceable
  in both directions.
- **Output interpolation across the delegate boundary** — the parent's
  `review` state reads `{{output.implementation.summary}}` which is
  sourced from the sub-run's terminal output, rendered as JSON into
  the parent prompt.

---

## The pipeline

```
solve-issue (parent)
├── fetch_issue                schema-validated: issue shape
├── classify                   schema-validated enum: backend | frontend
├── delegate_backend           creates sub-run, waits for terminal
│   │
│   └── backend-dev (sub-run, own run_id, own audit trail)
│       ├── understand         schema-validated: plan shape
│       ├── implement          schema-validated: implementation shape
│       └── done               ← prompts agent to resume parent
│
├── review                     reads {{output.implementation.*}}
│                              from the sub-run's terminal output
└── done
```

Five states in the parent, three in the sub (including the terminal),
one delegation boundary, two JSON Schema-validated outputs on each
side.

---

## Walking the run

### Input

```
Skill(claude-dev-pipeline:solve-issue, { issue_number: 42 })
```

The simulated issue is a logout endpoint: *"Add /api/logout that
clears the session cookie and returns 204 No Content. Remember to
invalidate the refresh token server-side too."*

### State 1 — `fetch_issue`

Runner creates the parent run `a7e545389c54`, injects the first
state's task as a `<system-reminder>`. The task tells the agent to
use `gh issue view` and emit a structured YAML at a specific path.

Agent output (real file, copied verbatim):
[`solve-issue-run/parent/fetch_issue.output.yaml`](./solve-issue-run/parent/fetch_issue.output.yaml)

The schema at `skills/solve-issue/schemas/fetch_issue.output.schema.json`
requires `issue` with `number`, `title`, `body` — the runner validates
before transitioning.

### State 2 — `classify`

Agent prompt includes the previous output interpolated as JSON:
```
Read the issue you just fetched:
  {"number": 42, "title": "Add /api/logout endpoint that clears the session cookie", ...}
```

Agent must emit `specialist: "backend" | "frontend"` with reasoning.
Schema enforces the enum — no other values allowed.

Agent output:
[`solve-issue-run/parent/classify.output.yaml`](./solve-issue-run/parent/classify.output.yaml)

The transition block uses `when` conditions to branch:

```yaml
transitions:
  - to: delegate_backend
    when: "output.specialist == 'backend'"
  - to: delegate_frontend
    when: "output.specialist == 'frontend'"
```

The agent emitted `specialist: backend`, so the runner advances to
`delegate_backend`.

### State 3 — `delegate_backend` (delegation boundary)

This is the key moment. The `delegate_backend` state has:

```yaml
delegate_backend:
  delegate_to: claude-dev-pipeline:backend-dev
  delegate_inputs:
    issue_number: "{{inputs.issue_number}}"
  transitions:
    - to: review
```

The runner:

1. Resolves `delegate_inputs` — interpolates `{{inputs.issue_number}}`
   against the parent's context
2. Creates a **sub-run** `1d2c20db5c6c` with `parent_run_id`,
   `parent_state`, and `parent_skill_id` pointing back at the parent
3. Records `sub_run_id: 1d2c20db5c6c` on the parent's history entry
4. Injects the sub-run's initial state (`understand`) as the agent's
   next task, with guidance to invoke
   `Skill(claude-dev-pipeline:backend-dev, { run_id: '1d2c20db5c6c' })`
   until terminal and then return to the parent

From the agent's point of view: it invoked one skill and got redirected
into a sub-pipeline. From the runtime's point of view: two independent
runs were created, linked bidirectionally, and both will complete with
full audit trail.

### Sub-run state 1 — `understand`

The agent now executes the `backend-dev` sub-skill starting from
`understand`. Produces a concrete plan:

[`solve-issue-run/sub/understand.output.yaml`](./solve-issue-run/sub/understand.output.yaml)

Schema at `skills/backend-dev/schemas/understand.output.schema.json`
requires `plan` with `files_to_change`, `new_behavior`, `tests_needed`.

### Sub-run state 2 — `implement`

Agent prompt includes the plan:
```
Execute the plan from the understand state:
  {"files_to_change": [...], "new_behavior": "...", "tests_needed": [...]}
```

Emits a structured implementation summary with the **shared shape**
that `backend-dev` and `frontend-dev` both produce:

[`solve-issue-run/sub/implement.output.yaml`](./solve-issue-run/sub/implement.output.yaml)

The shared shape — `{ summary, files_touched, tests_run, tests_passed,
notes }` — is what lets the parent's `review` state interpolate output
uniformly regardless of which specialist ran.

### Sub-run state 3 — `done` (terminal)

The sub-run reaches terminal. Because the run has `parent_run_id` set,
the runner emits a special terminal message instead of the standard
"Machine finished":

> Sub-run finished. Final output at
> `<project_dir>/.gates/runs/1d2c20db5c6c/implement.output.yaml`.
>
> This run was delegated from parent run a7e545389c54 (skill
> claude-dev-pipeline:solve-issue). Resume the parent by invoking
> `Skill(claude-dev-pipeline:solve-issue, { run_id: 'a7e545389c54' })`.
> The parent will pick up this sub-run's output and advance via its
> own transitions.

### Parent resumes — `review`

Agent invokes `Skill(claude-dev-pipeline:solve-issue, { run_id: 'a7e545389c54' })`.
The runner:

1. Loads the parent run, sees `current_state: delegate_backend`
2. `delegate_backend` has `delegate_to` → routes through
   `handle_delegate_state`
3. Finds the sub-run (by `parent_run_id` + `parent_state`), which is
   now terminal
4. Extracts the sub-run's last non-terminal output (the `implement`
   output)
5. Writes it as the parent state's output at
   `<project_dir>/.gates/runs/a7e545389c54/delegate_backend.output.yaml`
6. Advances parent's `current_state` to `review` via the transition
7. Builds the context for `review` — `{{output.*}}` now points at the
   delegate state's output, which is the sub-run's terminal output

The agent prompt for `review` renders:
```
The specialist sub-skill finished and returned:
  summary:       Added POST /api/logout that reads the session cookie, ...
  files_touched: ["app/api/logout/route.ts", "lib/auth/session.ts", ...]
  tests_passed:  True
```

Agent output:
[`solve-issue-run/parent/review.output.yaml`](./solve-issue-run/parent/review.output.yaml)

### State 5 — `done`

Parent reaches terminal. Run-state updated, final output pointed at
the review's YAML.

---

## The final run-state files

### Parent run-state ([full file](./solve-issue-run/parent/run-state.yaml))

```yaml
run_id: a7e545389c54
skill_id: claude-dev-pipeline:solve-issue
status: terminal
current_state: done
inputs:
  issue_number: 42
history:
- state: fetch_issue
  entered_at: '2026-04-11T19:36:16...'
  exited_at:  '2026-04-11T19:36:43...'
  output_path: <project_dir>/.gates/runs/a7e545389c54/fetch_issue.output.yaml
- state: classify
  entered_at: '2026-04-11T19:36:43...'
  exited_at:  '2026-04-11T19:36:51...'
  output_path: <project_dir>/.gates/runs/a7e545389c54/classify.output.yaml
- state: delegate_backend
  entered_at: '2026-04-11T19:36:51...'
  sub_run_id: 1d2c20db5c6c             # ← the delegation boundary
  exited_at:  '2026-04-11T19:37:19...'
  output_path: <project_dir>/.gates/runs/a7e545389c54/delegate_backend.output.yaml
- state: review
  entered_at: '2026-04-11T19:37:19...'
  exited_at:  '2026-04-11T19:37:26...'
  output_path: <project_dir>/.gates/runs/a7e545389c54/review.output.yaml
- state: done
  entered_at: '2026-04-11T19:37:26...'
```

### Sub run-state ([full file](./solve-issue-run/sub/run-state.yaml))

```yaml
run_id: 1d2c20db5c6c
skill_id: claude-dev-pipeline:backend-dev
status: terminal
current_state: done
inputs:
  issue_number: 42
history:
- state: understand
  entered_at: '2026-04-11T19:36:51...'
  exited_at:  '2026-04-11T19:37:02...'
  output_path: <project_dir>/.gates/runs/1d2c20db5c6c/understand.output.yaml
- state: implement
  entered_at: '2026-04-11T19:37:02...'
  exited_at:  '2026-04-11T19:37:12...'
  output_path: <project_dir>/.gates/runs/1d2c20db5c6c/implement.output.yaml
- state: done
  entered_at: '2026-04-11T19:37:12...'
parent_run_id: a7e545389c54              # ← linked back
parent_state: delegate_backend
parent_skill_id: claude-dev-pipeline:solve-issue
```

The two run-state files reference each other via `sub_run_id` (on the
parent's history) and `parent_run_id` / `parent_state` /
`parent_skill_id` (on the sub). You can navigate the pipeline in
either direction, inspect any individual state's output, or replay
the run.

---

## Reproducing this run

Prerequisites: install both plugins.

```bash
claude plugin marketplace add lucianfialho/atomic-gates
claude plugin install atomic-gates

claude plugin marketplace add lucianfialho/claude-dev-pipeline
claude plugin install claude-dev-pipeline
```

Then, in a scratch project, ask Claude to:

> Use the skill `claude-dev-pipeline:solve-issue` to resolve a fake
> GitHub issue 42: "Add /api/logout endpoint that clears the session
> cookie". There is no real issue on GitHub — invent plausible
> specialist output at each state. Walk through the whole pipeline
> end to end and show me the run-state files at the end.

The specific run_ids and timestamps will be different, but the
shape — five states in the parent, three in the sub, one delegation
boundary with bidirectional linkage — will be identical.

---

## Status

**Experimental.** This is an exploratory implementation of Jesse
Vincent's *[Rules and Gates](https://blog.fsck.com/2026/04/07/rules-and-gates/)*
thesis. The pipeline above runs end-to-end in the scenario I
dogfooded, but the API will change and the corpus is small. I built
it because I wanted to understand the thesis mechanically; sharing
the artifacts here because they're the most concrete thing I have to
offer for feedback.
