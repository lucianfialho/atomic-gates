---
name: context-sync
description: Build or update the .metadata/ knowledge base for changed files and refresh the Component Registry in CLAUDE.md
args: "mode (optional: 'full' to scan all source dirs, 'diff' for files changed in last commit — defaults to 'diff')"
---

# Context Sync

You are a knowledge manager for this codebase. Your job is to ensure that every source directory has an up-to-date `.metadata/` folder — and that `CLAUDE.md` has an accurate Component Registry.

This creates persistent institutional memory that future Claude sessions (and specialists) can load instead of reading all the code from scratch.

## .metadata/ format

Each source directory gets a `.metadata/` subdirectory with three files:

```
src/components/NavBar/
  index.tsx
  .metadata/
    context.md   — what it does, dependencies, patterns
    prompt.md    — why it exists (origin issue, key decisions)
    summary.md   — one-line description for fast loading
```

## Mode

- `diff` (default) — only process directories containing files changed in the last commit or uncommitted changes
- `full` — process all source directories in the project

## Process

### 1. Identify target directories

**If diff mode:**
```bash
# Files changed in last commit + any uncommitted changes
git diff --name-only HEAD~1 2>/dev/null
git status --porcelain | awk '{print $2}'
```

**If full mode:**
```bash
# All source files — skip generated/config dirs
find . -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" -o -name "*.py" \) \
  | grep -vE "node_modules|\.git|\.next|dist|build|\.metadata|coverage" \
  | sed 's|/[^/]*$||' | sort -u
```

For each changed file, extract its **parent directory**. Deduplicate — one `.metadata/` per directory describes all files in that directory.

**Skip** these directories entirely:
- `node_modules/`, `.git/`, `.next/`, `dist/`, `build/`, `coverage/`
- Directories containing only config files (`*.config.ts`, `*.config.js`)
- Directories containing only generated files (migrations auto-generated, prisma client, etc.)

### 2. For each target directory

#### a. Read the files in the directory
Read source files (skip test files and `.metadata/`). Understand:
- What this module/component does
- What it depends on (imports)
- What patterns and conventions it uses
- Its relationship to other parts of the codebase

Also check git log to understand the origin:
```bash
# Most recent commits touching files in this directory
git log --oneline -5 -- <directory>/
```

#### b. Check for existing metadata
```bash
ls <directory>/.metadata/ 2>/dev/null
```

- If `.metadata/` exists and files are recent: read them, update only what changed
- If `.metadata/` is missing or empty: create fresh metadata

#### c. Write `.metadata/context.md`

```markdown
# <ModuleName> — Context

**Type**: <React Component | API Route | Server Action | Hook | Utility | Schema | Migration | Test suite | etc.>
**Specialist**: <frontend-dev | backend-dev | qa-engineer | ux-designer | none>
**Last updated**: <YYYY-MM-DD>

## Purpose
<What this module does in 2-3 sentences. Be specific — name the feature or system it supports.>

## Key dependencies
- `<import or package>` — <why it's used here>

## Patterns
<Important conventions or non-obvious architectural decisions used in this module.>

## Notes
<Known issues, caveats, performance considerations, or things to watch out for when modifying this module.>
```

#### d. Write `.metadata/prompt.md`

```markdown
# <ModuleName> — Origin

**Issue**: #<number> — <title> (extract from git log commit messages; write "unknown" if not found)
**Specialist**: <role that implemented this>
**Date**: <YYYY-MM-DD>

## Request
<The original requirement that led to this code. Extract from the issue reference in commit messages or PR description.>

## Key decisions
- <Why was this approach chosen? Any alternatives that were considered or rejected?>
```

#### e. Write `.metadata/summary.md`

**One line only** — this file is loaded by specialists before reading code. Optimize for speed:

```
<ModuleName> (<type>, <specialist>, <date>) — <one-sentence description>. Deps: <dep1>, <dep2>.
```

Examples:
```
NavBar (component, frontend-dev, 2026-04-01) — Top navigation with auth-aware avatar and mobile hamburger menu. Deps: next-auth, tailwindcss, @/components/ui/Avatar.
UsersRoute (api-route, backend-dev, 2026-03-28) — CRUD endpoints for user management with pagination and role-based auth. Deps: prisma, zod, next-auth.
useCart (hook, frontend-dev, 2026-03-15) — Client-side cart state with optimistic updates and Zustand persistence. Deps: zustand, @/lib/api.
```

### 3. Update Component Registry in CLAUDE.md

After processing all directories, regenerate the Component Registry section in `CLAUDE.md`.

Find the section between these exact markers:
```
## Component Registry
<!-- context-sync: auto-generated — do not edit manually -->
...
<!-- /context-sync -->
```

If it doesn't exist, append it to the end of `CLAUDE.md`.

Build the table from ALL `.metadata/summary.md` files found in the project:
```bash
find . -path "*/.metadata/summary.md" | grep -vE "node_modules|\.git" | sort
```

For each summary, parse the one-liner and create a table row. Link the module path so it's navigable:

```markdown
## Component Registry
<!-- context-sync: auto-generated — do not edit manually -->
| Module | Summary | Specialist | Updated |
|--------|---------|-----------|---------|
| [`src/components/NavBar/`](src/components/NavBar/) | Top navigation with auth-aware avatar and mobile hamburger menu | frontend-dev | 2026-04-01 |
| [`src/api/users/`](src/api/users/) | CRUD endpoints for user management with pagination | backend-dev | 2026-03-28 |
| [`src/hooks/useCart/`](src/hooks/useCart/) | Client-side cart state with optimistic updates | frontend-dev | 2026-03-15 |
<!-- /context-sync -->
```

### 4. Report results

Output a clear summary:
```
Context sync complete (diff mode):

  Created:
    ✅ src/components/NavBar/.metadata/
    ✅ src/api/users/.metadata/

  Updated:
    ✅ src/components/CheckoutForm/.metadata/context.md

  Skipped (no changes):
    ↩️  src/lib/utils/
    ↩️  src/types/

Component Registry: 8 entries updated in CLAUDE.md
```

## Rules
- NEVER fabricate information — only write what you can verify from the code and git history
- If the issue/origin is unknown, write `unknown` — do not guess
- `summary.md` must be exactly **one line** — it must load instantly
- Do not create `.metadata/` for test files, pure config files, or lock files
- Describe what the code **does**, not what it **should** do
- When a directory has many files (e.g., a multi-route module), describe the whole module
- When a directory has one meaningful file, describe that file specifically
- `.metadata/` files should be committed alongside the code they describe — they are the codebase's long-term memory
