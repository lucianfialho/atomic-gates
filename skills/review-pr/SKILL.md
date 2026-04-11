---
name: review-pr
description: Review a PR with categorized findings and produce a structured verdict (APPROVE, REQUEST_CHANGES, or COMMENT). Runs as a gates state machine with schema-validated output at every step.
args: pr_number
---

# review-pr

This skill runs as a gates state machine. You do not need step-by-step
instructions — the gates runner injects a `<system-reminder>` each turn
telling you exactly which state you're in, what task to perform, and
where to write the output.

## How it works

1. You invoke `Skill(atomic-gates:review-pr, { pr_number: N })`.
2. The gates runner intercepts, creates a run, and injects the first
   state's task as a system reminder.
3. You execute the task — typically: read inputs, produce a structured
   YAML output at the `output_path` the runner specified, then call
   `Skill(atomic-gates:review-pr, { run_id: '<id from the reminder>' })`
   to advance.
4. Repeat until the runner tells you the machine reached a terminal state.

## States

- **fetch** — pull PR metadata and diff via `gh` CLI, emit structured YAML
- **review** — produce categorized findings (domain + severity) with
  mandatory file:line citations
- **emit_verdict** — aggregate findings into `APPROVE | REQUEST_CHANGES | COMMENT`
- **done** — terminal

## What not to do

- Do **not** try to do all states in one turn. Each state is a separate turn.
- Do **not** skip writing the YAML output — the runner validates it before
  advancing, and without it the machine cannot proceed.
- Do **not** invent findings or evidence. A finding without a concrete
  `file:line` citation is invalid — omit it.
- Do **not** rationalize `APPROVE` when there are critical findings. The
  verdict rules are enforced by the machine, not by your judgment.

## Reading the final verdict

When the runner tells you the machine reached a terminal state, the final
verdict is in `.gates/runs/<run_id>/emit_verdict.output.yaml`. That file
is the artifact — report its contents.
