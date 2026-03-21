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

### `/review-pr [specialist]`
Run targeted code reviews on the current PR using specialist skills:

```
/review-pr frontend     — React/Next.js, components, a11y, performance
/review-pr backend      — API design, security, DB patterns, error handling
/review-pr security     — Security-focused checklist (OWASP, secrets, auth)
/review-pr ux           — UX heuristics, accessibility, visual hierarchy
/review-pr all          — Run all applicable specialists (default)
```

Works with `@claude` in GitHub PR comments for on-demand specialist reviews.

### `/check-security [pr_number]`
Security-focused review covering OWASP Top 10, hardcoded secrets, auth gaps, and dependency vulnerabilities. Works as `@claude check security` in PR comments.

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
