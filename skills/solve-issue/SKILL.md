---
name: solve-issue
description: Pick a GitHub issue, classify its domain, delegate to the right specialist, run quality gates, and create a PR
args: issue_number
---

# Solve GitHub Issue

You are an autonomous development orchestrator. Your job is to take a GitHub issue, understand what kind of work it requires, delegate implementation to the right specialist, and deliver a verified Pull Request.

## Configuration

This skill reads from `pipeline.config.json` (repo root or `.claude/`). Relevant settings:
- `issues.label` — GitHub label for auto-discovery (default: `"claude"`)
- `issues.branchPrefix` — Branch name prefix (default: `"fix"`)
- `issues.autoAssign` — Auto-assign issue when solving (default: `true`)

## Input
- If an issue number is provided as argument, solve that specific issue
- If no number provided, use `gh issue list --state open --assignee @me` to find assigned issues, or `gh issue list --state open --label <configured-label>` to find issues labeled for automation

## Process

### 1. Understand the issue
```bash
gh issue view <number> --json title,body,labels,comments,assignees
```
Read the full issue including comments. Understand what needs to be done. Identify acceptance criteria.

### 2. Classify the domain

Analyze the issue and determine which specialist(s) should implement it:

| Signal | Specialist | Examples |
|--------|-----------|----------|
| UI components, pages, styling, responsive, a11y | **frontend-dev** | "add a new dashboard page", "fix button alignment", "make form responsive" |
| API endpoints, database, auth, server logic | **backend-dev** | "create user API", "add migration", "fix auth bypass" |
| Tests, coverage, flaky tests, QA | **qa-engineer** | "add tests for payment flow", "fix flaky test" |
| UI + API together | **frontend-dev** + **backend-dev** | "add comment feature with API" |
| UX improvements, accessibility, interaction | **ux-designer** + **frontend-dev** | "improve onboarding flow" |
| Security fixes, vulnerability patches | **backend-dev** (with security focus) | "fix SQL injection in search" |
| Refactoring, cleanup, tech debt | Use the domain of the files being changed | "refactor auth middleware" → backend-dev |
| Documentation, config, CI/CD | No specialist needed — implement directly | "update README", "add env var" |

**If uncertain**: look at which files will likely be changed and match against `pipeline.config.json` file patterns.

**For full-stack issues**: identify the primary domain (where most work happens) and use that specialist. If roughly equal, use both — backend-dev first (API/data), then frontend-dev (UI).

### 3. Create a branch
```bash
git checkout -b <branchPrefix>/<issue-number>-<short-description>
```

### 4. Research the codebase

First, check for existing `.metadata/` context on relevant directories — this can save significant time vs reading raw code:

```bash
# Find metadata for directories likely involved in the issue
find . -path "*/.metadata/summary.md" | grep -vE "node_modules|\.git" | xargs -I{} cat {} 2>/dev/null
```

If summaries exist for the directories you'll be modifying, read `.metadata/context.md` for those directories first — it captures patterns, dependencies, and caveats from prior work. Only read the full source files if you need more detail than the metadata provides.

Then:
- Read relevant files to understand the current implementation
- Find related tests and existing patterns
- Check CLAUDE.md (including the Component Registry) for project-specific rules
- Identify the test framework and conventions in use

### 4b. Gather library documentation

Before implementing, ensure you have up-to-date docs for the libraries you'll use. The pipeline maintains a local docs cache in `.claude/docs/` that is committed to the repo.

**Process:**

1. Read `package.json` (or `pyproject.toml` / `requirements.txt` for Python) to identify dependencies
2. Based on the classified domain and the issue, pick the 2-3 most relevant libraries
3. For each library, check if docs exist locally:

```bash
# Check if cached docs exist and are recent (< 30 days old)
ls -la .claude/docs/<library-name>.md
```

4. **If cached docs exist and are less than 30 days old**: read them directly
5. **If no cache or stale (> 30 days)**: fetch fresh docs and save to cache:

```bash
mkdir -p .claude/docs
npx @vedanth/context7 docs <library> "<topic relevant to the issue>" --tokens 8000 > .claude/docs/<library-name>.md
```

**Which libs to fetch by specialist:**

| Specialist | Typical libs to check |
|------------|----------------------|
| frontend-dev | react, next.js, tailwindcss, the UI library in use (shadcn, radix, etc.) |
| backend-dev | next.js (API routes/server actions), the ORM in use (prisma, drizzle), auth library |
| qa-engineer | the test framework (vitest, jest, playwright, cypress) |
| ux-designer | the UI component library, accessibility guidelines |

**Naming convention for cache files:**
- `nextjs.md`, `react.md`, `prisma.md`, `vitest.md`, `tailwindcss.md`
- For topic-specific docs: `nextjs-server-actions.md`, `prisma-migrations.md`

**Rules:**
- Always check the cache first — don't re-fetch what's already there
- Only fetch docs for libs that are actually in the project's dependencies
- Pick topics directly relevant to the issue — don't fetch generic docs
- Max 3 fetches per issue to keep context focused
- Use `--tokens 8000` for a good balance of depth and size
- Skip this step for trivial changes (typos, config, docs-only)
- Don't commit docs cache in the issue PR — it's infrastructure, not feature code

### 5. Implement with the specialist

Adopt the role and expertise of the classified specialist(s). This means:

**If frontend-dev**: Follow `skills/frontend-dev/SKILL.md` approach — Server Components by default, push `'use client'` down, semantic HTML, handle all states (loading/error/empty), no `any` types, responsive design, accessibility.

**If backend-dev**: Follow `skills/backend-dev/SKILL.md` approach — validate all inputs, parameterized queries, proper HTTP status codes, error handling, transactions for multi-step ops, never expose internal errors.

**If qa-engineer**: Follow `skills/qa-engineer/SKILL.md` approach — happy path first, then edge cases (empty, large, invalid, boundary, unicode, concurrent), descriptive test names, clean test data.

**If ux-designer + frontend-dev**: Follow `skills/ux-designer/SKILL.md` for design decisions (heuristics, a11y, visual hierarchy, states) and `skills/frontend-dev/SKILL.md` for implementation.

**If multiple specialists**: Implement backend/data layer first, then frontend/UI layer. Each layer follows its specialist's rules.

### 6. Write tests

Regardless of the domain, always write tests for new code:
- Match the project's test framework and conventions
- Cover the happy path + at least 2 edge cases
- For API changes: test valid input, invalid input, auth, and error cases
- For UI changes: test rendering, user interactions, and edge states
- For bug fixes: write a regression test that would have caught the bug

### 7. Verify quality

Run all quality gates in order — fix issues before proceeding:

```
1. Tests    → run project test command → fix failures
2. Lint     → run project lint command → fix issues
3. Build    → run project build command → fix errors
```

### 8. Self-review: security check

Before committing, scan your own changes for security issues:
- Hardcoded secrets or API keys → use env vars
- Unsanitized user input in SQL, HTML, shell commands, or file paths
- Missing auth/authorization checks on new endpoints
- Sensitive data in logs or error responses
- New dependencies with known vulnerabilities (`npm audit`)

If you find issues, fix them before proceeding.

### 9. Self-review: validate coverage

Before committing, verify your implementation covers the issue:
- Re-read the issue title, body, and comments
- Check each requirement or acceptance criterion is addressed
- If something is out of scope, note it in the PR description
- If something is unclear, note it as a question in the PR description

### 10. Write metadata for changed files

Before committing, update the `.metadata/` context for every directory you modified. This keeps the codebase's institutional memory current.

For each directory containing files you created or changed:

```bash
mkdir -p <directory>/.metadata
```

Write three files:

**`.metadata/context.md`** — what the module does, key dependencies, patterns used:
```markdown
# <ModuleName> — Context

**Type**: <React Component | API Route | Hook | Utility | etc.>
**Specialist**: <your role>
**Last updated**: <YYYY-MM-DD>

## Purpose
<2-3 sentences: what this module does and which feature it supports>

## Key dependencies
- `<dep>` — <why it's used>

## Patterns
<Non-obvious conventions or architectural decisions>

## Notes
<Caveats, known issues, things to watch out for>
```

**`.metadata/prompt.md`** — why this code exists (link back to the issue):
```markdown
# <ModuleName> — Origin

**Issue**: #<number> — <issue title>
**Specialist**: <your role>
**Date**: <YYYY-MM-DD>

## Request
<Key requirements from the issue>

## Key decisions
- <Why this approach was chosen>
```

**`.metadata/summary.md`** — one line, optimized for fast loading by future specialists:
```
<ModuleName> (<type>, <specialist>, <date>) — <one-sentence description>. Deps: <dep1>, <dep2>.
```

After writing all metadata, refresh the Component Registry in `CLAUDE.md`:

```bash
# Find all summary files and build the registry table
find . -path "*/.metadata/summary.md" | grep -vE "node_modules|\.git" | sort | xargs -I{} sh -c 'dir=$(dirname $(dirname {})); echo "| [\`$dir/\`]($dir/) | $(cat {}) |"'
```

Replace the content between `<!-- context-sync: auto-generated -->` and `<!-- /context-sync -->` markers in `CLAUDE.md` with the updated table. If the markers don't exist yet, append the Component Registry section at the end.

### 11. Commit and push
- Include the `.metadata/` files in the commit alongside the code changes
- Write a clear commit message referencing the issue
- Push the branch

### 11. Create PR with structured summary

```bash
gh pr create --title "<type>: <description>" --body "$(cat <<'EOF'
Closes #<number>

## Summary
<1-2 sentences: what this PR does and why>

## Domain
<frontend | backend | full-stack | tests | infra | docs>
Specialist: <which specialist role was used>

## Changes
<for each file changed:>
- **`file`** — <what changed and why>

## Impact
- Breaking changes: <yes/no — details if yes>
- New dependencies: <list or "none">
- DB changes: <migrations, schema changes, or "none">
- New env vars: <list or "none">
- Security considerations: <any auth/input changes, or "none">

## Test plan
- <how to verify this works>
- <edge cases covered in tests>

## Issue coverage
- ✅ <requirement 1 from issue>
- ✅ <requirement 2 from issue>
- <❌ or ⚠️ if anything is partially covered or intentionally skipped, with explanation>

---
🤖 Implemented by Claude Code dev-pipeline (<specialist> specialist)

@claude review-pr all
EOF
)"
```

The `@claude review-pr all` at the end of the PR body triggers the GitHub Actions workflow to automatically run a full specialist review on the PR.

## Rules
- NEVER skip tests. If tests fail, fix them before creating the PR
- NEVER force push or use destructive git operations
- NEVER modify files unrelated to the issue
- NEVER implement without adopting the appropriate specialist role
- Keep changes minimal and focused
- If the issue is unclear, comment on it asking for clarification instead of guessing
- Always write tests — even for "simple" changes
- Always self-review for security before committing
- Always validate issue coverage before creating the PR
