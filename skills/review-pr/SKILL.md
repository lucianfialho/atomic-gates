---
name: review-pr
description: Review a PR with specialist skills — frontend, backend, security, UX, or all
args: specialist
---

# Review PR with Specialists

Run targeted code reviews on the current PR using specialist skills.

## Usage

```
/review-pr frontend     — React/Next.js, components, a11y, performance
/review-pr backend      — API design, security, DB patterns, error handling
/review-pr security     — Security-focused checklist (OWASP, secrets, auth)
/review-pr ux           — UX heuristics, accessibility, visual hierarchy
/review-pr all          — Run all applicable specialists sequentially
```

If no argument is provided, defaults to `all`.

## Process

### 1. Get the PR diff

Detect the current PR from the branch:
```bash
gh pr view --json number,title,body,files
gh pr diff
```

If not on a PR branch, ask the user for a PR number.

### 2. Dispatch to specialist

Based on the argument, load the corresponding specialist skill and provide it with:
- The full PR diff
- The PR description for context
- The review output format (below)

| Argument | Specialist Skill | Focus Area |
|----------|-----------------|------------|
| `frontend` | `/frontend-dev` | React/Next.js patterns, components, a11y, responsiveness, performance, state management |
| `backend` | `/backend-dev` | API design, database, auth, error handling, input validation, security |
| `security` | `/code-reviewer` | Security-only: injection, XSS, CSRF, secrets, auth bypass, dependencies |
| `ux` | `/ux-designer` | Nielsen's heuristics, accessibility, visual hierarchy, interaction design, empty states |
| `all` | All of the above | Run each sequentially, combine output |

### 3. Review output format

Every specialist MUST output findings in this consistent format:

```
## <Specialist Name> Review

### Summary
<1-2 sentence overview of the review>

### Findings

#### 🔴 Critical
Issues that must be fixed before merge.

- **`file.tsx:42`** — <description>
  **Fix:** <concrete suggestion>

#### 🟡 Warning
Issues that should be fixed but aren't blocking.

- **`file.ts:15`** — <description>
  **Fix:** <concrete suggestion>

#### 💡 Suggestion
Improvements that would make the code better.

- **`file.ts:88`** — <description>
  **Fix:** <concrete suggestion>

### Verdict
<APPROVE | REQUEST_CHANGES | COMMENT>
<1 sentence justification>
```

### 4. For `review all`

Run specialists **sequentially** (not in parallel) to avoid noisy output:

1. First: security review (highest priority)
2. Then: check changed files to decide which other specialists are relevant
3. Run relevant specialists in order: backend → frontend → ux
4. Combine all outputs under a single review comment

Skip specialists that have no relevant files in the diff (e.g., skip frontend if no .tsx/.css files changed).

## Rules

- ALWAYS fetch the actual PR diff — never review from memory
- ALWAYS use the consistent output format above
- NEVER auto-approve — always provide at least the verdict
- If a specialist finds no issues, say so explicitly: "No issues found in <area>"
- For `review all`, include a final combined verdict based on the worst finding across all specialists
- Be thorough but concise — explain WHY something is an issue
- Provide concrete fix suggestions, not just complaints
