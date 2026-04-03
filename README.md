# dev-pipeline

An autonomous development pipeline plugin for Claude Code. Classifies issues by domain, delegates to specialist agents, gathers up-to-date library docs, enforces quality gates, and delivers verified PRs.

## How it works

### Solve Issue Pipeline

```mermaid
flowchart TD
    START(["/solve-issue 42"]) --> READ["1. Read Issue\ngh issue view #42"]
    READ --> CLASSIFY{"2. Classify Domain"}

    CLASSIFY -->|UI, components, styling| FE["🎨 frontend-dev"]
    CLASSIFY -->|API, database, auth| BE["⚙️ backend-dev"]
    CLASSIFY -->|Tests, coverage, QA| QA["🧪 qa-engineer"]
    CLASSIFY -->|UX + UI| UXFE["🧑‍🎨 ux-designer\n+ 🎨 frontend-dev"]
    CLASSIFY -->|Full-stack| FULL["⚙️ backend-dev\nthen 🎨 frontend-dev"]
    CLASSIFY -->|Docs, config, CI| DIRECT["📝 Direct"]

    FE --> RESEARCH
    BE --> RESEARCH
    QA --> RESEARCH
    UXFE --> RESEARCH
    FULL --> RESEARCH
    DIRECT --> IMPLEMENT

    RESEARCH["3. Research\nRead package.json\nCheck .claude/docs/ cache\nFetch via context7 if stale"]

    RESEARCH --> IMPLEMENT["4. Implement\nWith specialist expertise"]
    IMPLEMENT --> TESTS["5. Write Tests\nHappy path + edge cases"]

    TESTS --> GATE_T{"Tests?"}
    GATE_T -->|Fail| FIX_T["Fix"] --> GATE_T
    GATE_T -->|Pass| GATE_L{"Lint?"}
    GATE_L -->|Fail| FIX_L["Fix"] --> GATE_L
    GATE_L -->|Pass| GATE_B{"Build?"}
    GATE_B -->|Fail| FIX_B["Fix"] --> GATE_B

    GATE_B -->|Pass| META["6. Write .metadata/\ncontext + prompt + summary\nUpdate CLAUDE.md registry"]
    META --> SEC["7. Security Self-Review\nSecrets, injection, auth"]
    SEC --> VAL["8. Validate Coverage\nAll requirements met?"]
    VAL --> PR["9. Create PR\nStructured summary +\n@claude review-pr all"]
    PR --> GHA["9. GitHub Actions\nDetects @claude in PR body"]
    GHA --> REVIEW["10. Automated Review\nSpecialists run in parallel\non GitHub Actions"]
    REVIEW --> DONE([PR Reviewed])

    style CLASSIFY fill:#1a1a2e,stroke:#e94560,color:#fff
    style FE fill:#0f3460,stroke:#e94560,color:#fff
    style BE fill:#0f3460,stroke:#e94560,color:#fff
    style QA fill:#0f3460,stroke:#e94560,color:#fff
    style UXFE fill:#0f3460,stroke:#e94560,color:#fff
    style FULL fill:#0f3460,stroke:#e94560,color:#fff
    style DIRECT fill:#0f3460,stroke:#e94560,color:#fff
    style RESEARCH fill:#533483,stroke:#e94560,color:#fff
    style IMPLEMENT fill:#0f3460,stroke:#e94560,color:#fff
    style GATE_T fill:#16213e,stroke:#e94560,color:#fff
    style GATE_L fill:#16213e,stroke:#e94560,color:#fff
    style GATE_B fill:#16213e,stroke:#e94560,color:#fff
    style SEC fill:#16213e,stroke:#e94560,color:#fff
    style META fill:#533483,stroke:#00d2ff,color:#fff
    style VAL fill:#16213e,stroke:#e94560,color:#fff
    style PR fill:#1a1a2e,stroke:#00d2ff,color:#fff
    style GHA fill:#533483,stroke:#00d2ff,color:#fff
    style REVIEW fill:#533483,stroke:#00d2ff,color:#fff
    style START fill:#e94560,stroke:#e94560,color:#fff
    style DONE fill:#00d2ff,stroke:#00d2ff,color:#000
```

### PR Review Pipeline

```mermaid
flowchart LR
    START(["/review-pr all"]) --> DIFF["Get PR diff\nCategorize files"]

    DIFF --> DISPATCH{"Dispatch\nby file type"}

    DISPATCH --> S1["🔒 code-reviewer\nSecurity"]
    DISPATCH --> S2["⚙️ backend-dev\nAPI, DB, auth"]
    DISPATCH --> S3["🎨 frontend-dev\nComponents, a11y"]
    DISPATCH --> S4["🧑‍🎨 ux-designer\nHeuristics, states"]

    S1 --> MERGE["Unified Report\nCombined verdict table"]
    S2 --> MERGE
    S3 --> MERGE
    S4 --> MERGE

    MERGE --> VERDICT{{"APPROVE | REQUEST_CHANGES"}}

    style DISPATCH fill:#1a1a2e,stroke:#e94560,color:#fff
    style S1 fill:#0f3460,stroke:#e94560,color:#fff
    style S2 fill:#0f3460,stroke:#e94560,color:#fff
    style S3 fill:#0f3460,stroke:#e94560,color:#fff
    style S4 fill:#0f3460,stroke:#e94560,color:#fff
    style MERGE fill:#16213e,stroke:#00d2ff,color:#fff
    style START fill:#e94560,stroke:#e94560,color:#fff
    style VERDICT fill:#00d2ff,stroke:#00d2ff,color:#000
```

### Docs Knowledge Base

```mermaid
flowchart LR
    NEED["Specialist needs\nlibrary docs"] --> CHECK{".claude/docs/\ncache exists?"}

    CHECK -->|"Yes, < 30 days"| READ["Read from cache"]
    CHECK -->|"No or stale"| FETCH["npx @vedanth/context7\ndocs lib topic"]

    FETCH --> SAVE["Save to\n.claude/docs/lib.md"]
    SAVE --> READ

    READ --> USE["Use in\nimplementation"]

    style CHECK fill:#1a1a2e,stroke:#e94560,color:#fff
    style FETCH fill:#533483,stroke:#e94560,color:#fff
    style SAVE fill:#533483,stroke:#e94560,color:#fff
    style READ fill:#0f3460,stroke:#00d2ff,color:#fff
    style USE fill:#0f3460,stroke:#00d2ff,color:#fff
```

Specialists read `package.json` to identify project dependencies, then check `.claude/docs/` for cached documentation before fetching fresh docs via [context7](https://github.com/VedanthB/context7-cli). The cache is committed to the repo so the whole team benefits.

### Context Management

```mermaid
flowchart LR
    SPECIALIST["Specialist starts\nworking on files"] --> CHECK{".metadata/\nexists?"}

    CHECK -->|"Yes"| READ_META["Read\n.metadata/context.md\n+ summary.md"]
    CHECK -->|"No"| READ_CODE["Read full\nsource files"]

    READ_META --> IMPLEMENT["Implement\nwith context"]
    READ_CODE --> IMPLEMENT

    IMPLEMENT --> WRITE_META["Write .metadata/\ncontext.md\nprompt.md\nsummary.md"]

    WRITE_META --> REGISTRY["Update\nCLAUDE.md\nComponent Registry"]

    REGISTRY --> COMMIT["Commit metadata\nalongside code"]

    style CHECK fill:#1a1a2e,stroke:#e94560,color:#fff
    style READ_META fill:#0f3460,stroke:#00d2ff,color:#fff
    style READ_CODE fill:#0f3460,stroke:#e94560,color:#fff
    style WRITE_META fill:#533483,stroke:#e94560,color:#fff
    style REGISTRY fill:#533483,stroke:#00d2ff,color:#fff
    style COMMIT fill:#16213e,stroke:#00d2ff,color:#fff
```

Each source directory gets a `.metadata/` folder committed alongside the code:

```
src/components/NavBar/
  index.tsx
  .metadata/
    context.md   — what it does, key dependencies, patterns, caveats
    prompt.md    — origin issue, specialist used, key decisions
    summary.md   — one line for fast loading by future specialists
```

The `CLAUDE.md` file maintains a **Component Registry** table (auto-updated by `/context-sync`) listing all modules with their one-line summaries, so any session can quickly orient itself without reading source files.

Run `/context-sync` manually after batch work, or let `solve-issue` update metadata automatically as part of every PR.

### End-to-End Flow

```mermaid
sequenceDiagram
    participant Dev as Developer (local)
    participant CC as Claude Code (local)
    participant GH as GitHub
    participant GHA as GitHub Actions

    Dev->>CC: /solve-issue 42
    CC->>GH: gh issue view #42
    CC->>CC: Classify domain → pick specialist
    CC->>CC: Research libs (package.json + context7 cache)
    CC->>CC: Implement with specialist expertise
    CC->>CC: Write tests + quality gates
    CC->>CC: Write .metadata/ for changed files
    CC->>CC: Update CLAUDE.md Component Registry
    CC->>CC: Self-review (security + coverage)
    CC->>GH: git push + gh pr create<br/>(metadata committed alongside code)
    GH->>GHA: PR opened → triggers claude.yml
    GHA->>GHA: Load dev-pipeline plugin
    GHA->>GHA: Run batch-review with specialists
    GHA->>GH: Post review comments + verdict
    GH-->>Dev: PR ready with automated review
```

## Install

Add the marketplace and install the plugin (inside Claude Code):
```
claude plugin marketplace add lucianfialho/claude-dev-pipeline
claude plugin install dev-pipeline
```

Or load directly from a local directory:
```bash
claude --plugin-dir /path/to/claude-dev-pipeline
```

## Skills

### Issue Solving

| Skill | Description |
|-------|-------------|
| `/solve-issue [number]` | Classify domain, research libs, delegate to specialist, implement, verify, and create PR |
| `/batch-issues` | Process multiple issues labeled "claude" in parallel using agent teams |
| `/context-sync [full]` | Update `.metadata/` for changed files and refresh Component Registry in CLAUDE.md |

### PR Review

| Skill | Description |
|-------|-------------|
| `/review-pr [specialist]` | Targeted review: `frontend`, `backend`, `security`, `ux`, or `all` (parallel) |
| `/batch-review [pr_number]` | Run all applicable specialists in parallel with unified verdict |
| `/check-security [pr_number]` | OWASP Top 10, secrets, auth gaps, dependency audit |
| `/suggest-tests [pr_number]` | Missing tests, edge cases, regression risks with skeleton code |
| `/ux-review [pr_number]` | Nielsen's heuristics, WCAG 2.1 AA, interaction design |
| `/pr-summary [pr_number]` | Structured summary: changes, impact, review focus areas |
| `/validate-issue [pr_number]` | Verify PR covers all requirements from linked issue |

All review skills work as `@claude <command>` in GitHub PR comments.

### Specialists

These specialists are used by `solve-issue` for implementation and by review skills for analysis. Each researches up-to-date library docs before working.

| Specialist | Domain | Researches |
|------------|--------|------------|
| `frontend-dev` | React/Next.js, components, a11y, responsive | Framework, UI library, CSS tooling |
| `backend-dev` | APIs, database, auth, server logic | Framework, ORM, auth library |
| `qa-engineer` | Tests, edge cases, coverage | Test runner, mocking, assertion APIs |
| `ux-designer` | UX heuristics, accessibility, interaction | UI component library, a11y guidelines |
| `code-reviewer` | Bugs, security, performance, quality | Always included in reviews |

## Quality Gates (Hooks)

| Hook | When | What |
|------|------|------|
| **Stop** | Before Claude stops | Runs test suite — blocks if tests fail |
| **PostToolUse** (Write/Edit) | After file edits | Async lint check — reports issues |
| **TaskCompleted** | Before task closes | Runs build — blocks if build breaks |

## Review Rules

Domain-specific review rules are loaded based on changed file types:

| Rule Set | Triggers on | Focus |
|----------|------------|-------|
| `base.md` | Always | Secrets, error handling, single responsibility, code style |
| `frontend.md` | `.tsx`, `.jsx`, `.css` | Server Components, a11y, performance, design system |
| `backend.md` | `route.ts`, `actions.ts`, `api/` | Status codes, validation, queries, auth |
| `security.md` | Security reviews | Injection, secrets, auth, CSRF, CORS |
| `database.md` | `migration*`, `schema*`, `.prisma` | Migrations, N+1, transactions, indexes |
| `performance.md` | Performance reviews | Rendering, fetching, caching, assets |

Include `REVIEW.md` in your repo root for project-specific review rules. Works with Claude Code Review.

## Usage

```bash
# Solve a specific issue (classifies domain, researches libs, picks specialist)
/dev-pipeline:solve-issue 42

# Or let Claude pick from labeled issues
/dev-pipeline:solve-issue

# Process all "claude" labeled issues in parallel
/dev-pipeline:batch-issues

# Review a PR with all specialists in parallel
/dev-pipeline:review-pr all

# Review with a specific specialist
/dev-pipeline:review-pr security

# Run security check on current PR
/dev-pipeline:check-security
```

## GitHub Actions Integration

The pipeline includes two GitHub Actions workflows:

**`claude.yml`** — Runs when `@claude` is mentioned in issues, PR comments, or PR body. Loads the dev-pipeline plugin so specialists can run remotely.

**`claude-code-review.yml`** — Runs automatic code review on every PR opened or updated.

When `solve-issue` creates a PR, it includes `@claude review-pr all` in the body, which automatically triggers a full specialist review via GitHub Actions — no manual intervention needed.

**Setup**: Add `CLAUDE_CODE_OAUTH_TOKEN` as a repository secret. Copy the workflow files from `.github/workflows/` to your repo.

## Configuration

Create a `pipeline.config.json` in your repo root to customize behavior:

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

All fields are optional — defaults are used for anything not specified.

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
