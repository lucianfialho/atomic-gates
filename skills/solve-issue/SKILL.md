---
name: solve-issue
description: Pick a GitHub issue, implement it, run tests, and create a PR
args: issue_number
---

# Solve GitHub Issue

You are an autonomous developer. Your job is to take a GitHub issue and deliver a working implementation as a Pull Request.

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
gh issue view <number>
```
Read the full issue. Understand what needs to be done. Check comments for additional context.

### 2. Create a branch
```bash
git checkout -b <branchPrefix>/<issue-number>-<short-description>
```
Use the `issues.branchPrefix` from `pipeline.config.json` (default: `fix`).

### 3. Research the codebase
- Read relevant files to understand the current implementation
- Find related tests
- Understand the project structure and conventions
- Check CLAUDE.md for project-specific rules

### 4. Implement the solution
- Make the minimum changes needed to solve the issue
- Follow existing code patterns and conventions
- Add or update tests for your changes
- Update documentation if needed

### 5. Verify quality
- Run the test suite: use the project's test command
- Run the linter: use the project's lint command
- Run the build: use the project's build command
- All three must pass before proceeding

### 6. Commit and push
- Write a clear commit message referencing the issue
- Push the branch

### 7. Create PR
```bash
gh pr create --title "<type>: <description>" --body "Closes #<number>

## Summary
<1-3 bullet points>

## Changes
<list of files changed and why>

## Test plan
<how to verify this works>

---
🤖 Implemented by Claude Code dev-pipeline"
```

## Rules
- NEVER skip tests. If tests fail, fix them before creating the PR
- NEVER force push or use destructive git operations
- NEVER modify files unrelated to the issue
- Keep changes minimal and focused
- If the issue is unclear, comment on it asking for clarification instead of guessing
