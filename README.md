# dev-pipeline

An autonomous development pipeline plugin for Claude Code. Picks up GitHub issues, implements them, runs quality gates, and creates PRs.

## Install

```bash
claude plugin add /path/to/claude-dev-pipeline
```

Or from GitHub:
```bash
claude plugin add github:lucianfialho/claude-dev-pipeline
```

## Skills

### `/solve-issue [number]`
Solve a single GitHub issue end-to-end:
1. Reads the issue
2. Creates a branch
3. Implements the solution
4. Runs tests, lint, build
5. Creates a PR that closes the issue

### `/batch-issues`
Process multiple issues labeled "claude" in parallel using agent teams.

### `/pr-summary [pr_number]`
Generate a structured PR summary — what changed, why, impact (breaking changes, new deps, env vars), and review focus areas. Works as `@claude summarize` in PR comments.

## Quality Gates (Hooks)

| Hook | When | What |
|------|------|------|
| **Stop** | Before Claude stops | Runs test suite — blocks if tests fail |
| **PostToolUse** (Write/Edit) | After file edits | Async lint check — reports issues |
| **TaskCompleted** | Before task closes | Runs build — blocks if build breaks |

## Code Review

Include `REVIEW.md` in your repo root (or copy ours) for automated PR review guidelines. Works with Claude Code Review.

## Usage with Foundd (example)

```bash
# Install the plugin
claude plugin add /path/to/claude-dev-pipeline

# Solve a specific issue
/solve-issue 1

# Or let Claude pick from labeled issues
/solve-issue

# Process all "claude" labeled issues
/batch-issues
```

## Customization

- Edit `REVIEW.md` for project-specific review rules
- Adjust hook timeouts in `hooks/hooks.json`
- Scripts auto-detect npm/pytest — add more in `scripts/`
