# Getting started with atomic-gates

This guide walks you from zero to seeing a gate bloquer a `git commit`
in about five minutes. If you just want to know what atomic-gates is,
read the [README](../../README.md) first.

---

## What you'll build

By the end of this guide:

- The plugin is installed in Claude Code
- Your project has a `.gates/config.yaml` declaring one indexed directory
- A `git commit` touching that directory **fails with exit 2**
- You fill in the auto-generated `.metadata/summary.yaml` stub
- The same `git commit` now succeeds

That's the full loop. Everything else atomic-gates does — state machines,
role enforcement, PR structure — builds on this same pattern.

---

## Prerequisites

- Claude Code CLI installed (any recent version)
- Python 3 with `pyyaml` (default on macOS; on Linux: `pip install pyyaml`)
- A git repo you can experiment in — create a scratch one if you want

---

## Step 1 — Install the plugin

From inside Claude Code:

```
/plugin marketplace add lucianfialho/atomic-gates
/plugin install atomic-gates
```

Verify the hooks loaded:

```
/hooks
```

You should see entries under `PreToolUse` for:

- `matcher: Bash` → `gate_metadata.py`, `gate_pr_structure.py`
- `matcher: Edit|Write` → `gate_role.py`
- `matcher: Skill` → `runner.py`

If you don't see any of those, the plugin isn't loaded — check
`/plugin list` and reinstall if needed.

---

## Step 2 — Create a scratch project

Outside Claude Code:

```bash
mkdir -p /tmp/gates-hello/components/NavBar
cd /tmp/gates-hello
git init -q
```

Create `.gates/config.yaml`:

```yaml
version: 1
project:
  name: gates-hello
indexed_directories:
  - path: components/NavBar
    specialist: frontend
```

Create a fake component for the gate to trip on:

```bash
cat > components/NavBar/NavBar.tsx <<'TSX'
export function NavBar() {
  return <nav>hi</nav>;
}
TSX
```

Stage it:

```bash
git add components/NavBar/NavBar.tsx
```

---

## Step 3 — Try to commit (watch it fail)

Still outside Claude Code, open a session in this directory:

```bash
claude
```

Then tell Claude to commit:

> Commit the staged files with the message "add NavBar".

Claude will run `git commit -m "add NavBar"`. The gate intercepts and
the commit **fails with exit 2**:

```
gates: commit blocked — metadata problems found

Stub files created — fill these in and `git add` them:
  - components/NavBar/.metadata/summary.yaml

Why: directories indexed in .gates/config.yaml must keep their
.metadata/summary.yaml up to date on every commit that touches them.
```

A stub file was created on disk:

```bash
cat components/NavBar/.metadata/summary.yaml
```

You'll see something like:

```yaml
id: TODO-id
title: TODO-title
covers:
  - TODO-file
specialist: TODO-specialist
touched_by_issues: []
last_updated: TODO-date
status: stub
```

Every field marked `TODO` and `status: stub`. This is the gate's way
of telling the agent exactly what to fill in.

---

## Step 4 — Fill the stub and commit

You can ask Claude to fill it, or edit by hand. Here's a filled version:

```yaml
id: nav-bar
title: Navigation bar
tags: [layout, navigation]
covers:
  - NavBar.tsx
specialist: frontend
touched_by_issues: []
last_updated: "2026-04-11"
status: filled
```

Key things to notice:

- `status: filled` (not `stub`) — the gate rejects `stub`
- `covers:` lists the files inside this directory that this summary
  describes. Must have at least one entry
- `last_updated:` is any ISO date string
- `specialist:` matches what's in `.gates/config.yaml`

Stage it alongside the component:

```bash
git add components/NavBar/.metadata/summary.yaml
```

Ask Claude to commit again:

> Commit the staged files with the message "add NavBar".

This time the gate passes and the commit is created.

---

## What just happened

A hook (`PreToolUse: Bash`) ran before Claude's `git commit` call. It:

1. Saw that `git commit` was about to run
2. Ran `git diff --cached --name-only` to list staged files
3. Cross-referenced those files against `indexed_directories` in
   `.gates/config.yaml`
4. For each indexed directory that had staged changes, checked if
   `.metadata/summary.yaml`:
   - Existed (first run: no → create stub, exit 2)
   - Was staged in the same commit (second run: no → exit 2 telling
     the agent to stage it)
   - Had `status: filled` (third run: yes → exit 0, commit proceeds)

This is a **gate** in the Jesse Vincent *Rules and Gates* sense: a
mechanical check that refuses to let the next step happen unless a
concrete artifact exists and passes validation. Not a prompt asking
Claude to remember.

---

## What to read next

- **[Using atomic-gates with superpowers](./using-with-superpowers.md)** —
  how both plugins coexist; the adapter runtime that lets atomic-gates
  execute superpowers skills with an audit trail
- **[Authoring atomic gates](./authoring-atomic-gates.md)** — how to
  write a new blocking hook like `gate-metadata`
- **[Authoring state-machine skills](./authoring-state-machines.md)** —
  how to declare a skill as a YAML state machine with schema
  validation at every transition
- **[Technical reference](../atomic-gates.md)** — the full layout,
  schemas, and development notes
