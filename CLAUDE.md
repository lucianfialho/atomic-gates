# dev-pipeline

An autonomous development pipeline plugin for Claude Code.

## What it does

1. **Issue Solver** (`/solve-issue`) — Picks a GitHub issue, implements it, runs tests, creates a PR
2. **Code Review** — REVIEW.md rules for automated PR review
3. **Quality Gates** — Hooks that enforce tests, lint, and build before stopping
4. **Batch Issues** (`/batch-issues`) — Process multiple issues in parallel with agent teams

## Architecture

```
skills/
  solve-issue.md      — Pick and solve a GitHub issue end-to-end
  batch-issues.md     — Process multiple issues in parallel
  review-rules.md     — Code review guidelines (loaded by REVIEW.md)

hooks/
  hooks.json          — Quality gate hooks (Stop, PostToolUse, TaskCompleted)

scripts/
  check-tests.sh      — Verify tests pass before stopping
  check-lint.sh       — Run linter after file edits
  check-build.sh      — Verify build succeeds
  validate-pr.sh      — Validate PR before creation
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
/validate-issue          — Check if PR addresses all issue requirements
```
