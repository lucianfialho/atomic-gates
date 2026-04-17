# validation/ — kill-my-idea protocol for atomic-gates

This directory applies Popperian rigor to atomic-gates itself: each claim is
falsifiable, each falsifier is cheap, and verdicts are logged before
confirmation bias has a chance to win.

## Files

- `hypotheses.yaml` — **pre-registered** claims. Edited only to add new
  hypotheses or mark verdicts. Kill criteria are never softened after
  observing data.
- `analyze_runs.py` — retrospective analyzer over `.gates/runs/` from real
  projects. Emits `stats.json` + updates `ledger.md`.
- `ledger.md` — auto-generated verdict log. Source of truth.
- `stats.json` — raw numbers for plotting / further analysis.

## Run the retrospective (1h, free)

```bash
python3 validation/analyze_runs.py \
  ~/Code/analytics-copilot \
  ~/Code/gmp-cli
```

Reads every `<project>/.gates/runs/*.yaml`, evaluates H1–H4 in
`hypotheses.yaml`, writes verdicts to `ledger.md`.

## Next experiments (if H1–H4 survive)

Add to `hypotheses.yaml` and implement alongside:

- **H5** — atomic gates (commit/pr/role) fire in practice.
  Method: instrument hooks with telemetry (append to `.gates/hook-log.jsonl`).
  Run 2 weeks, count firings.
- **H6** — pipeline beats CC raw on paired issues (**N≥30**, McNemar).
  Method: `ab_experiment/run_both.py`, LLM-as-judge (different model from
  generator), Bonferroni correction.
- **H7** — audit trail `.gates/runs/` is read, not just written.
  Method: `stat` access-time on yaml files 2 weeks after creation.

## Rules of engagement

1. **Pre-register.** Kill criteria for every H written before data is seen.
2. **Cheapest test first.** Retrospective > ablation > prospective A/B.
3. **Ship the verdict.** `ledger.md` is committed even when claims die.
   Especially when claims die.
4. **No p-hacking.** No moving the kill_criterion after the fact. If you
   want a softer bar, register a new hypothesis with a new id.
5. **Don't build the framework.** N=1 use of the protocol, inside this
   repo. Only extract to its own repo if N≥2 cases accumulate.
