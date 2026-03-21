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

## Configuration

Create a `pipeline.config.json` in your repo root (or `.claude/`) to customize behavior:

```json
{
  "$schema": "https://raw.githubusercontent.com/lucianfialho/claude-dev-pipeline/main/schemas/pipeline-config.schema.json",
  "specialists": {
    "defaults": ["code-reviewer"],
    "filePatterns": {
      "src/components/**": "frontend-dev",
      "src/api/**": "backend-dev",
      "**/*.test.*": "qa-engineer",
      "**/*.tsx": "ux-designer"
    }
  },
  "issues": {
    "label": "claude",
    "branchPrefix": "fix",
    "autoAssign": true
  },
  "batch": {
    "maxParallel": 3
  },
  "quality": {
    "requireTests": true,
    "requireBuild": true,
    "requireLint": true
  },
  "review": {
    "securityCheck": true,
    "performanceCheck": true,
    "maxFileReviewSize": 500
  }
}
```

All fields are optional — defaults are used for anything not specified. The `$schema` field enables autocompletion in VS Code and other editors.

### Configuration Reference

| Section | Key | Default | Description |
|---------|-----|---------|-------------|
| `specialists` | `defaults` | `["code-reviewer"]` | Specialists that always run on reviews |
| `specialists` | `filePatterns` | `{}` | Map file globs to specialists |
| `issues` | `label` | `"claude"` | GitHub label for issue discovery |
| `issues` | `branchPrefix` | `"fix"` | Branch naming prefix |
| `issues` | `autoAssign` | `true` | Auto-assign issues when solving |
| `batch` | `maxParallel` | `3` | Max parallel agents (1-10) |
| `quality` | `requireTests` | `true` | Run tests before stopping |
| `quality` | `requireBuild` | `true` | Run build before task completion |
| `quality` | `requireLint` | `true` | Run linter after file edits |
| `review` | `securityCheck` | `true` | Include security checklist |
| `review` | `performanceCheck` | `true` | Include performance checklist |
| `review` | `maxFileReviewSize` | `500` | Max lines per file to review |

## Other Customization

- Edit `REVIEW.md` for project-specific review rules
- Adjust hook timeouts in `hooks/hooks.json`
- Scripts auto-detect npm/pytest — add more in `scripts/`
