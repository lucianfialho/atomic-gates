---
name: batch-review
description: Run multiple specialist reviews on a PR in parallel using subagents
args: pr_number
---

# Batch Review

Run all applicable specialist reviews on a PR in parallel using subagents, then produce a unified review report.

This is the "premium" review mode — dispatches up to 3 specialists simultaneously for comprehensive coverage. Use `/review-pr <specialist>` for individual reviews.

## Usage

```
/batch-review            — Full review of the current PR branch
/batch-review 42         — Full review of PR #42
```

## Prerequisites

Depends on these specialist skills being available:
- `code-reviewer` — Code quality and security review
- `frontend-dev` — Frontend/React specialist
- `backend-dev` — Backend/API specialist
- `ux-designer` — UX/accessibility review
- `qa-engineer` — Test coverage and quality

## Process

### 1. Analyze the PR diff

```bash
gh pr view --json number,title,body,files
gh pr diff
```

Categorize changed files:
- **Frontend**: `.tsx`, `.jsx`, `.css`, `.scss`, `.module.css`
- **Backend**: `route.ts`, `route.js`, `actions.ts`, files in `api/`
- **Database**: `migration*`, `schema*`, `*.prisma`, `*.sql`
- **Tests**: `*.test.*`, `*.spec.*`, `__tests__/`
- **Config**: `*.config.*`, `*.json`, `*.yaml`, `.env*`

### 2. Select applicable specialists

Based on changed file categories:

| Files Changed | Specialists to Run |
|--------------|-------------------|
| Frontend files | `frontend-dev`, `ux-designer` |
| Backend files | `backend-dev` |
| Any files | `code-reviewer` (security focus) |
| No test files for new code | `qa-engineer` (suggest tests) |

**Always run**: security review (code-reviewer)
**Skip if no relevant files**: frontend-dev, ux-designer, backend-dev

Minimum: 1 specialist (security). Maximum: 4 specialists.

### 3. Dispatch subagents in parallel

Use the Agent tool to run up to 3 specialists in parallel:

```
For each selected specialist:
  Agent(
    prompt: "Review this PR diff as a <specialist>. Use the /<skill> format. PR diff: <diff>",
    subagent_type: "general-purpose"
  )
```

**Constraints**:
- Max 3 parallel agents (to avoid rate limits)
- If 4+ specialists needed, run the 4th after the first batch completes
- Each agent gets the full PR diff but only reviews their domain

### 4. Collect and merge results

Wait for all agents to complete, then merge their outputs into a unified review:

```markdown
## Comprehensive Review

**PR #<N>**: <title>
**Specialists**: <list of specialists that ran>

---

### 🔒 Security Review
<output from code-reviewer>

---

### ⚙️ Backend Review
<output from backend-dev, or "N/A — no backend files changed">

---

### 🎨 Frontend Review
<output from frontend-dev, or "N/A — no frontend files changed">

---

### 🧑‍🎨 UX Review
<output from ux-designer, or "N/A — no UI files changed">

---

### 🧪 Test Suggestions
<output from qa-engineer, or "All new code has corresponding tests">

---

## Combined Verdict

| Specialist | Verdict | Critical Issues |
|-----------|---------|-----------------|
| Security | <PASS/FAIL> | <count> |
| Backend | <PASS/FAIL/N/A> | <count> |
| Frontend | <PASS/FAIL/N/A> | <count> |
| UX | <PASS/FAIL/N/A> | <count> |

**Overall**: <APPROVE | REQUEST_CHANGES | COMMENT>
<1-2 sentence justification based on worst finding>
```

### 5. Smart filtering

To reduce noise on small PRs:
- If a category has fewer than 3 changed files, include those files in the general security review instead of spawning a separate specialist
- If the PR is under 50 lines total, run only the security review
- If the PR is only test files, skip all reviews and just verify test quality

## Rules

- ALWAYS run at least the security review
- ALWAYS include a combined verdict table at the end
- NEVER run more than 3 agents simultaneously
- Each specialist reviews ONLY their relevant files (reduces noise)
- Skip specialists gracefully — "N/A" not errors
- If all specialists approve, the combined verdict is APPROVE
- If any specialist has critical issues, the combined verdict is REQUEST_CHANGES
