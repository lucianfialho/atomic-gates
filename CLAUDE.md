# dev-pipeline

An autonomous development pipeline plugin for Claude Code.

## What it does

1. **Issue Solver** (`/solve-issue`) — Classifies issue domain, delegates to the right specialist, implements, verifies, and creates a PR
2. **PR Review** (`/review-pr`) — Targeted specialist reviews: frontend, backend, security, UX, or all (parallel)
3. **Code Review** — REVIEW.md + domain-specific rules for automated PR review
4. **Quality Gates** — Hooks that enforce tests, lint, and build before stopping
5. **Batch Issues** (`/batch-issues`) — Process multiple issues in parallel with agent teams

## Architecture

```
pipeline.config.json  — User-customizable settings (optional, has defaults)
schemas/
  pipeline-config.schema.json — JSON Schema for IDE autocompletion

skills/
  solve-issue/SKILL.md    — Orchestrator: classify → delegate → implement → verify → PR
  batch-issues/SKILL.md   — Process multiple issues in parallel

  # Specialists (used for implementation AND review)
  frontend-dev/SKILL.md   — React/Next.js, components, a11y, responsive
  backend-dev/SKILL.md    — APIs, database, auth, server logic
  qa-engineer/SKILL.md    — Tests, edge cases, coverage
  ux-designer/SKILL.md    — UX heuristics, accessibility, interaction
  code-reviewer/SKILL.md  — Bugs, security, performance, quality

  # Review skills
  review-pr/SKILL.md      — Dispatch to specialists (parallel when "all")
  batch-review/SKILL.md   — All specialists in parallel with unified verdict
  check-security/SKILL.md — OWASP Top 10, secrets, auth, dependencies
  suggest-tests/SKILL.md  — Missing tests with skeleton code
  ux-review/SKILL.md      — Nielsen's heuristics, WCAG 2.1 AA
  pr-summary/SKILL.md     — Structured PR summary
  validate-issue/SKILL.md — Verify PR covers issue requirements

review-rules/
  base.md                 — Always loaded (secrets, errors, style)
  frontend.md             — .tsx, .jsx, .css files
  backend.md              — route.ts, actions.ts, api/
  security.md             — Security reviews
  database.md             — Migrations, schemas, ORM
  performance.md          — Rendering, caching, assets

hooks/
  hooks.json              — Quality gate hooks (Stop, PostToolUse, TaskCompleted)

scripts/
  load-config.sh          — Config loader (sources pipeline.config.json)
  check-tests.sh          — Verify tests pass before stopping
  check-lint.sh           — Run linter after file edits
  check-build.sh          — Verify build succeeds
```

## Usage

Install:
```
claude plugin marketplace add lucianfialho/claude-dev-pipeline
claude plugin install dev-pipeline
```

Then:
```
/solve-issue 42          — Solve issue #42 (classifies domain, picks specialist)
/solve-issue             — Pick the next unassigned issue
/batch-issues            — Process all open issues labeled "claude"
/review-pr frontend      — Review current PR with frontend specialist
/review-pr security      — Security-focused review
/review-pr all           — Run all applicable specialists in parallel
/suggest-tests           — Suggest missing tests for the current PR
/check-security          — Security-focused review of current PR
/ux-review               — UX-focused review of UI changes in current PR
/pr-summary              — Generate structured PR summary
/validate-issue          — Check if PR addresses all issue requirements
/batch-review            — Run all applicable specialists on a PR in parallel
```
