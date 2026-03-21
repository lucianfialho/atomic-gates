---
name: batch-issues
description: Process multiple GitHub issues in parallel using agent teams
---

# Batch Process Issues

Process multiple open GitHub issues in parallel.

## Configuration

This skill reads from `pipeline.config.json` (repo root or `.claude/`). Relevant settings:
- `issues.label` — GitHub label to filter issues (default: `"claude"`)
- `batch.maxParallel` — Maximum parallel agents (default: `3`)

## Process

### 1. List available issues
```bash
gh issue list --state open --label <configured-label> --json number,title,labels
```
Use the `issues.label` from `pipeline.config.json` (default: `claude`).

### 2. For each issue, spawn a subagent
Use the Agent tool with `isolation: "worktree"` for each issue:
- Each agent gets its own git worktree (isolated branch)
- Each agent runs the solve-issue skill
- Agents work in parallel without conflicting

### 3. Monitor progress
- Track which issues are being worked on
- Report back when each PR is created
- Summarize all PRs at the end

## Rules
- Maximum `batch.maxParallel` parallel agents (default: 3) to avoid rate limits
- Each agent creates its own branch and PR
- If an agent fails, log the error and continue with others
- Report final summary: issues solved, PRs created, failures
