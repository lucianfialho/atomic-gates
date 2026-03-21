# dev-pipeline

An autonomous development pipeline plugin for Claude Code.

## What it does

1. **Issue Solver** (`/solve-issue`) — Picks a GitHub issue, implements it, runs tests, creates a PR
2. **PR Review** (`/review-pr`) — Targeted specialist reviews: frontend, backend, security, UX, or all
3. **Code Review** — REVIEW.md rules for automated PR review
4. **Quality Gates** — Hooks that enforce tests, lint, and build before stopping
5. **Batch Issues** (`/batch-issues`) — Process multiple issues in parallel with agent teams

## Architecture

```
pipeline.config.json  — User-customizable settings (optional, has defaults)
schemas/
  pipeline-config.schema.json — JSON Schema for IDE autocompletion

skills/
  solve-issue/SKILL.md   — Pick and solve a GitHub issue end-to-end
  batch-issues/SKILL.md  — Process multiple issues in parallel
  code-reviewer/SKILL.md — Code review specialist
  frontend-dev/SKILL.md  — Frontend development specialist
  backend-dev/SKILL.md   — Backend development specialist
  qa-engineer/SKILL.md   — QA and testing specialist
  ux-designer/SKILL.md   — UX/UI review specialist

hooks/
  hooks.json          — Quality gate hooks (Stop, PostToolUse, TaskCompleted)

scripts/
  load-config.sh      — Config loader (sources pipeline.config.json)
  check-tests.sh      — Verify tests pass before stopping
  check-lint.sh       — Run linter after file edits
  check-build.sh      — Verify build succeeds
```

## Usage

Install in any repo:
```
claude plugin add /path/to/claude-dev-pipeline
```

Then:
```
/solve-issue 42          — Solve issue #42
/solve-issue             — Pick the next unassigned issue
/batch-issues            — Process all open issues labeled "claude"
/review-pr frontend      — Review current PR with frontend specialist
/review-pr security      — Security-focused review
/review-pr all           — Run all applicable specialists
/suggest-tests           — Suggest missing tests for the current PR
/check-security          — Security-focused review of current PR
/ux-review               — UX-focused review of UI changes in current PR
/pr-summary              — Generate structured PR summary
/validate-issue          — Check if PR addresses all issue requirements
/batch-review            — Run all applicable specialists on a PR in parallel
```
