---
name: validate-issue
description: Validate that a PR implementation addresses all requirements from the linked GitHub issue
args: pr_number
---

# Validate Issue Linkage

Compare a PR's implementation against its linked GitHub issue to verify all requirements are met.

## Usage

```
/validate-issue          — Validate the current PR branch
/validate-issue 42       — Validate PR #42
```

Also works as `@claude validate-issue` in GitHub PR comments.

## Process

### 1. Find the linked issue

```bash
# Get PR body and branch name
gh pr view --json number,title,body,headRefName,files

# Extract issue number from:
# - PR body: "Closes #42", "Fixes #42", "Resolves #42"
# - Branch name: "fix/42-description"
```

If no linked issue is found, report: "No linked issue found. Add `Closes #N` to the PR body."

### 2. Read the issue requirements

```bash
gh issue view <number> --json title,body,comments
```

Extract requirements from:
- Issue title and body
- Acceptance criteria (if listed)
- Comments from maintainers (additional requirements or clarifications)
- Labels (bug, feature, refactor — sets expectations)

### 3. Read the PR diff

```bash
gh pr diff
```

### 4. Compare requirements to implementation

For each requirement identified in the issue:
- Is it addressed by the diff?
- Is it fully implemented or only partially?
- Are there edge cases mentioned in comments that aren't handled?

For each change in the diff:
- Does it relate to the issue?
- Is it out-of-scope (not mentioned in the issue)?

### 5. Output format

```markdown
## Issue Coverage Analysis

**Issue #<N>**: <issue title>

### Requirements Met
✅ <requirement> — implemented in `file:line`
✅ <requirement> — implemented in `file:line`

### Requirements Missing
❌ <requirement> — <where it was mentioned (body/comment by @user)>
❌ <requirement> — <where it was mentioned>

### Partially Met
⚠️ <requirement> — <what's done vs what's missing>

### Out-of-Scope Changes
🔍 **`file.ts`** — <description of change not mentioned in issue>
<Intentional refactor? Flag for reviewer attention.>

### Verdict
<COMPLETE | INCOMPLETE | NEEDS_DISCUSSION>
<justification — which requirements are blocking if incomplete>
```

## Rules

- ALWAYS read the full issue including comments — requirements often evolve in discussion
- ALWAYS check both issue body AND comments for requirements
- Flag out-of-scope changes as informational, not blocking — they might be intentional
- If the issue is vague, note which requirements were inferred vs explicitly stated
- Don't flag test files or documentation as "out-of-scope" — they support the implementation
- Be specific about what's missing — "auth not implemented" not just "incomplete"
