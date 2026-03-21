---
name: pr-summary
description: Generate a structured PR summary — what changed, why, impact, and review focus areas
args: pr_number
---

# PR Summary

Generate a structured summary for a PR that helps reviewers understand the changes quickly.

## Usage

```
/pr-summary              — Summarize the current PR branch
/pr-summary 42           — Summarize PR #42
```

Also works as `@claude summarize` in GitHub PR comments.

## Process

### 1. Gather context

```bash
# Get PR metadata
gh pr view --json number,title,body,files,commits,labels,baseRefName

# Get the full diff
gh pr diff

# Get commit messages
gh pr view --json commits -q '.commits[].messageHeadline'

# Check for linked issues
gh pr view --json body -q '.body' | grep -oE '#[0-9]+'
```

### 2. Analyze changes

For each changed file:
- What was the purpose of the change?
- Is it a new feature, bug fix, refactor, or config change?
- What's the blast radius (how much of the app is affected)?

Look for:
- **Breaking changes**: Modified API contracts, renamed exports, changed DB schemas
- **New dependencies**: Check package.json diff for added/removed packages
- **Database changes**: New migrations, schema modifications
- **Environment variables**: New or changed env vars required
- **Security impact**: Auth changes, new endpoints, permission changes

### 3. Output format

```markdown
## Summary

<1-2 sentence description of what this PR does and why>

## Changes

- **`path/to/file.ts`** — <what changed and why>
- **`path/to/other.ts`** — <what changed and why>

## Impact

- **Breaking changes**: <None | description>
- **New dependencies**: <None | list with versions>
- **Database changes**: <None | description of migrations>
- **Requires env vars**: <None | list of new/changed vars>
- **Security impact**: <None | description>

## Review Focus

Areas that need careful review:
- <file:line — why this needs attention>
- <file:line — why this needs attention>

## Related

- <Closes #N | Related to #N | No linked issues>
```

### 4. Post the summary

Two modes:

**Update PR body** (when creating a new PR via `/solve-issue`):
- Prepend the summary to the existing PR body

**Post as comment** (when invoked on an existing PR via `@claude summarize`):
- Post the summary as a PR comment

## Rules

- ALWAYS read the actual diff — never summarize from title/body alone
- ALWAYS check for breaking changes and call them out prominently
- ALWAYS list new environment variables (reviewers need to know for deployment)
- Keep file descriptions concise — what changed, not how (the diff shows how)
- Link to specific lines for review focus areas
- If the PR has linked issues, verify the changes address the issue requirements
