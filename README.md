# dev-pipeline

An autonomous development pipeline plugin for Claude Code. Picks up GitHub issues, implements them, runs quality gates, and creates PRs.

## Install

Add the marketplace and install the plugin (inside Claude Code):
```
/plugin marketplace add lucianfialho/claude-dev-pipeline
/plugin install dev-pipeline
```

Or load directly from a local directory:
```bash
claude --plugin-dir /path/to/claude-dev-pipeline
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

## Quality Gates (Hooks)

| Hook | When | What |
|------|------|------|
| **Stop** | Before Claude stops | Runs test suite — blocks if tests fail |
| **PostToolUse** (Write/Edit) | After file edits | Async lint check — reports issues |
| **TaskCompleted** | Before task closes | Runs build — blocks if build breaks |

## Code Review

Include `REVIEW.md` in your repo root (or copy ours) for automated PR review guidelines. Works with Claude Code Review.

## Usage

```bash
# After installing, use the skills inside Claude Code:

# Solve a specific issue
/dev-pipeline:solve-issue 1

# Or let Claude pick from labeled issues
/dev-pipeline:solve-issue

# Process all "claude" labeled issues
/dev-pipeline:batch-issues
```

## Customization

- Edit `REVIEW.md` for project-specific review rules
- Adjust hook timeouts in `hooks/hooks.json`
- Scripts auto-detect npm/pytest — add more in `scripts/`
