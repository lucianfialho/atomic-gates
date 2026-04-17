# LLM-as-judge rubric — atomic-gates vs CC raw

**Versioned. Do NOT edit after any data has been collected against
this version. If you need a new metric, register a new hypothesis id
in `validation/hypotheses.yaml` and bump this file to v2.**

Version: v1 (scaffold — not yet used)
Judge model: **different from generator** (e.g. generator=Opus →
judge=Gemini 2.5 Pro). Pin exact model versions below at run time.

## Primary metrics (binary, paired)

For each `(issue, mode)`, the judge sees: the issue body, the resulting
diff/PR, and any test output. Scores **0 or 1** on each item:

1. **solves_issue** — does the diff actually satisfy the acceptance
   criteria stated in the issue?
2. **tests_present** — does the diff include at least one test that
   exercises the new/changed behavior?
3. **no_regressions** — does the diff pass the project's existing test
   suite? (populated from CI result, not judged by the LLM.)

## Secondary metrics (continuous, paired)

4. **scope_score** — ratio of lines changed to lines required by the
   spec. Lower is better. Judge estimates "required" from the issue.
5. **iterations** — number of agent turns before the diff was produced.
6. **wall_clock_seconds** — end-to-end time.
7. **usd_cost** — LLM spend for this run.

## Multiple comparisons

Running 3 binary + 4 continuous = 7 tests per arm. Use Bonferroni
correction: reject null only when `p < 0.05 / 7 ≈ 0.007`.

## Inter-judge concordance

Randomly select 10% of runs. Have a second instance of the judge
(same model family, different run) re-score blind. Report Cohen's
kappa. Below 0.6 → judge is noisy, results are provisional.
