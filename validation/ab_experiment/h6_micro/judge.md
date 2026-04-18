# Judge rubric — H6 micro-benchmark v0 (directional)

**Goal:** compare the pipeline arm (PR #95) against the CC-puro arm
(whatever `run-cc-puro.sh` produced) on issue #89.

**Do NOT** use this rubric as final judgment — it's directional.
A positive signal here licences the full N≥30 A/B; a negative signal
kills the claim cheaply.

## Inputs to the judge (LLM OR human, pick one)

- `issue-89.md` — what was asked for
- `pipeline/diff.patch` — what the pipeline produced (PR #95)
- `cc-puro/trial-1.patch` — what CC puro produced

## Score each arm (0–2 each, total 0–10)

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| **solves_chart_validation** | not present | partial (no block) | validate + exit 2 |
| **solves_connector_validation** | not present | partial | validate + exit 2 |
| **tests_present** | no test file | test exists, shallow | tests cover block+allow paths |
| **hooks_json_updated** | not touched | added, malformed | added correctly with matchers |
| **scope_discipline** | touches unrelated dirs | some creep | only `hooks/` + `hooks.json` |

## Verdict

- **pipeline - cc_puro ≥ 4 points** → pipeline wins directionally. Invest in N≥30 A/B (issue #29).
- **|pipeline - cc_puro| < 2 points** → tie or noise. Harness investment NOT justified by this data. Question the pipeline.
- **cc_puro - pipeline ≥ 4 points** → pipeline *loses*. Hard signal. Re-examine the whole value prop.

## Who judges

Fastest: a human (you) reads both patches and fills out the table.
Takes 20 min. No LLM cost, no inter-judge concordance concern, no
prompt sensitivity.

If you want LLM judge for honesty: use Gemini 2.5 Pro (different
family from generator). Pin the exact rubric prompt in
`judge-prompt.md` (not yet written — scaffold it after first trial).

## Why only 1 trial per arm

This is directional, not publishable. Trial-count is a design decision
that lives in the full N≥30 experiment (#29). Rushing to N=3 here
adds 2× cost and gives a statistically worthless signal anyway.
One trial each side, one judge, one decision. Ship the answer.
