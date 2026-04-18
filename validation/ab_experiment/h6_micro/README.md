# H6 micro-benchmark — pipeline vs CC puro on issue #89

**Status: ready to run. Budget: ~$1–3 + 30 min.**

Directional answer to H6 ("pipeline beats Claude Code raw on issue →
PR"). One real issue, pipeline arm already captured from PR #95,
CC-puro arm takes one `./run-cc-puro.sh` invocation. Judge by hand
in 20 min.

## Why this issue

Issue [#89 in `analytics-copilot`](https://github.com/metricasboss/analytics-copilot/issues/89)
asked for three PreToolUse hooks (chart validation, connector
validation, query validation) with specific acceptance criteria.
Pipeline closed it via PR #95 (460 lines / 4 files). Clean test case
because acceptance criteria are checklist-style.

Base commit (pre-PR): `019038a89029d5a6f00609b6809980268ef42710`
Head commit (PR tip): `c44d13a84abc0118580b328d51c48cc94a8c1ca5`

## Files here

```
h6_micro/
├── README.md                 ← this file
├── issue-89.md               issue body, cached (no network needed at run time)
├── pipeline/diff.patch       pipeline's output = PR #95 diff, pre-captured
├── cc-puro/                  where CC-puro output lands (one file per trial)
├── run-cc-puro.sh            worktree + headless claude -p + capture diff
├── judge.md                  scoring rubric (5 criteria × 0-2 each)
└── results.md                write verdict here after judging
```

## How to run — 3 steps

### 1. Make sure `claude` CLI is authenticated

```bash
claude --version    # should print the CLI version
```

If it errors, `claude login` first.

### 2. Run the CC-puro arm

From the atomic-gates repo root:

```bash
./validation/ab_experiment/h6_micro/run-cc-puro.sh
```

The script:
- creates a git worktree at the pre-PR base commit `/tmp/h6-cc-puro-trial-1`
- runs `claude -p` headless with the issue body as prompt
- `--dangerously-skip-permissions` so it doesn't stop to ask
- unsets `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PROJECT_DIR` so atomic-gates
  doesn't contaminate the puro arm
- captures the resulting diff to `cc-puro/trial-1.patch`

~5–15 min wall clock depending on how much CC chews on the issue.

### 3. Judge by hand

Open both patches side by side:

```bash
less validation/ab_experiment/h6_micro/pipeline/diff.patch
less validation/ab_experiment/h6_micro/cc-puro/trial-1.patch
```

Fill out `judge.md`'s table for each arm. Write verdict into
`results.md`.

## Starter prompt for a fresh Claude Code session

If you want Claude to drive the run and judge, paste this into a new
session opened at `/Users/lucianfialho/Code/atomic-gates`:

> I want to run the H6 micro-benchmark in
> `validation/ab_experiment/h6_micro/`. Execute `run-cc-puro.sh`,
> then compare the two patches against the rubric in `judge.md`,
> and write the verdict into `results.md`. Do not modify the
> pipeline arm — only the `cc-puro/` files and `results.md`.
> When done, `git add` those files and show me the diff before
> committing.

## Decision gate

`judge.md` has three bands:

- **pipeline wins ≥4 pts** → green light for #29 (full N≥30 A/B) and
  for investing in the harness.
- **tie (< 2 pt delta)** → harness not justified. Re-think value prop.
- **pipeline loses ≥4 pts** → hard signal. Pitch itself is wrong.

Act on the band directly. Don't shop for a more favorable rubric.
