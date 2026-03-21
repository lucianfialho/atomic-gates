---
name: batch-issues
description: Process multiple GitHub issues in parallel using agent teams
---

# Batch Process Issues

Process multiple open GitHub issues labeled "claude" in parallel.

## Process

### 1. List available issues
```bash
gh issue list --state open --label claude --json number,title,labels
```

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
- Maximum 3 parallel agents to avoid rate limits
- Each agent creates its own branch and PR
- If an agent fails, log the error and continue with others
- Report final summary: issues solved, PRs created, failures
