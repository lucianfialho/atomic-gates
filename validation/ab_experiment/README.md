# A/B experiment — CC raw vs atomic-gates pipeline

**Status: scaffold only.** Contents of this directory are placeholders.
The experiment requires explicit budget approval (LLM API spend), a
curated issue corpus with ground-truth expectations, and several hours
of runtime. Do **not** execute without reading `README.md`, setting a
budget ceiling, and editing `rubric.md` so the kill criteria are fixed
*before* any data is collected.

## Protocol

- **N ≥ 30 issues**, paired (same issue run in both modes).
- **Same generator model, randomized ordering** to avoid carryover.
- **LLM-as-judge must be a different model** from the generator
  (e.g. generator=Opus, judge=Gemini 2.5). Measure inter-judge
  concordance on a 10% sample.
- **Rubric is versioned in `rubric.md` BEFORE any run.** No retroactive
  edits once data exists — if you want a new metric, register a new
  hypothesis in `validation/hypotheses.yaml` with its own id.
- **Stats**: McNemar (paired binary outcomes), Wilcoxon signed-rank
  (continuous). Bonferroni correction if more than one primary metric.
- **Budget**: set and enforce a USD ceiling. Abort if exceeded.

## Files (to be built)

```
ab_experiment/
├── README.md          (this file)
├── rubric.md          scoring rubric for LLM-as-judge — VERSIONED
├── issues.yaml        N ≥ 30 fixed issues + expected behavior
├── run_both.py        execute both modes, record outputs + provenance
├── judge.py           LLM-as-judge scoring loop
├── stats.py           McNemar + Wilcoxon + Bonferroni → verdict
├── outputs/           raw per-run outputs (gitignored)
└── runs.csv           one row per (issue, mode, trial) with judge scores
```

## Prerequisites

Issues #24 (gate_failures persistence) and #25 (skeleton trap) must
ship first — otherwise the pipeline arm is contaminated by known bugs
that were present when H1 and H4 were first measured. **Both shipped
in commits `df07912` and `658e9ac` respectively.**

## Why this is not automated yet

Writing a good benchmark is harder than writing the runner. Getting it
wrong means publishing "pipeline beats CC raw" based on leaky
comparison — worse than not publishing. The kill-my-idea protocol
explicitly ordered this experiment **last**: the cheapest tests
(retrospective, ablation) went first and already killed three of four
v1 claims. Don't pay the A/B tax until the surviving claims are
load-bearing for a decision.
