---
name: validate-issue
description: Verify that a PR implementation covers every requirement from its linked GitHub issue. Use when reviewing a PR to confirm issue coverage before merging.
---

# validate-issue

This skill runs as a gates state machine. You do not need to follow step-by-step
instructions — the gates runner injects a `<system-reminder>` each turn telling
you exactly which state you're in, what task to perform, and where to write the
output.

## How it works

1. You invoke `Skill(validate-issue, { issue_number: N, pr_number: M })`.
2. The gates runner intercepts the invocation, creates a run, and injects the
   first state's task as a system reminder.
3. You execute the task — typically: read inputs, produce a structured YAML
   output file at the path the runner specified, then call
   `Skill(validate-issue, { run_id: '<id from the reminder>' })` to advance.
4. Repeat until the runner tells you the machine reached a terminal state.

## What to do each turn

- Read the `<system-reminder>` carefully. It contains:
  - The current state name
  - The task for this state
  - The `output_path` where your YAML must be written
  - The `run_id` to pass in the next invocation
- Execute the task.
- Write the YAML at the `output_path`.
- Invoke `Skill(validate-issue, { run_id: '<run_id>' })` to advance.

## What not to do

- Do **not** try to do all states in one turn. Each state is a separate turn.
- Do **not** skip writing the YAML output — the runner validates it before
  advancing, and without it the machine cannot proceed.
- Do **not** invent requirements or evidence. If the issue is unclear, the
  final verdict should be `NEEDS_DISCUSSION`, not a fabricated `COMPLETE`.

## Reading the final verdict

When the runner tells you the machine reached a terminal state, the final
verdict is in the `emit_verdict.output.yaml` file under
`.gates/runs/<run_id>/`. That file is the artifact — report its contents.
