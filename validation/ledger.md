# atomic-gates — validation ledger

_Generated: 2026-04-17T11:00:59.890043+00:00_  
_Projects scanned: analytics-copilot, gmp-cli_  
_Protocol: `validation/hypotheses.yaml`_

## Summary

- Total runs: **31**
- Terminal: 27  ·  Running: 4  ·  Error: 0  ·  Abandoned: 0
- Gate failures across all history: **0**
- Stuck runs (>24h in `running`): **4**

### Skill distribution

| skill_id | runs |
|---|---|
| `claude-dev-pipeline:solve-issue` | 13 |
| `claude-dev-pipeline:backend-dev` | 11 |
| `claude-dev-pipeline:validate-issue` | 2 |
| `claude-dev-pipeline:review-pr` | 2 |
| `claude-dev-pipeline:check-security` | 1 |
| `superpowers:brainstorming` | 1 |
| `claude-dev-pipeline:frontend-dev` | 1 |

## Verdicts

### H1 — ❔ INCONCLUSIVE

- Reason: instrument blind — no run in this corpus has ever recorded history[].gate_failures. Runner pre-fix (issue #24) never persisted the field. Re-run after collecting runs on the patched runner before interpreting a rate of 0.

### H2 — ✅ SURVIVING

- Observed: 4 stuck + 0 abandoned of 31 runs (12.9%)
- Kill threshold: <= 15%
- Stuck runs:
  - `3d0b0ca5b143` (claude-dev-pipeline:check-security) stuck 64.8h on `usage`
  - `4aa35505bf4b` (claude-dev-pipeline:solve-issue) stuck 83.1h on `fetch_issue`
  - `b839c9204006` (superpowers:brainstorming) stuck 91.1h on `execute`
  - `b09c71c99b28` (claude-dev-pipeline:validate-issue) stuck 92.1h on `fetch`

### H3 — 💀 KILLED

- Observed: 2 validate-issue vs 13 solve-issue (ratio=0.15)
- Kill threshold: >= 0.2

### H4 — 💀 KILLED

- Observed: 1 runs stuck on meta-section states
- Kill threshold: = 0
- Trap runs (stuck on meta-state):
  - `3d0b0ca5b143` (claude-dev-pipeline:check-security) on `usage`
