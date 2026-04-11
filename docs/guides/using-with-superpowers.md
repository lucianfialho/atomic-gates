# Using atomic-gates with superpowers

[`obra/superpowers`](https://github.com/obra/superpowers) is the most
polished skill corpus in the Claude Code ecosystem — 14 skills covering
brainstorming, TDD, worktrees, planning, and code review. `atomic-gates`
is the enforcement layer underneath it: hooks that block actions, state
machines that validate structured output.

They're not alternatives. This guide shows how to install both, how
they interact, and when to use which.

---

## Install both plugins

From inside Claude Code:

```
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers

/plugin marketplace add lucianfialho/atomic-gates
/plugin install atomic-gates
```

Verify both are active:

```
/plugin list
/hooks
```

You should see:

- Hooks from `superpowers`: one `SessionStart` hook that injects the
  `using-superpowers` prompt
- Hooks from `atomic-gates`: `PreToolUse` hooks for `Bash`, `Edit|Write`,
  and `Skill`

They don't collide. `superpowers` uses a different hook event
(`SessionStart`), and `atomic-gates` uses `PreToolUse`. Both run on
every session without stepping on each other.

---

## Which one does what

| Situation | Plugin that handles it |
|---|---|
| You open a new session | `superpowers` injects `using-superpowers` |
| You ask Claude to "brainstorm an API" | `superpowers` skill `brainstorming` runs |
| You ask Claude to "write this using TDD" | `superpowers` skill `test-driven-development` runs |
| Claude runs `git commit` after touching an indexed directory | `atomic-gates` gate `gate-metadata` blocks if `.metadata/summary.yaml` is stale |
| Claude runs `gh pr create` | `atomic-gates` gate `gate-pr-structure` blocks if body is missing required sections |
| Claude edits a file outside an active specialist's scope | `atomic-gates` gate `gate-role` blocks if `CLAUDE_ACTIVE_SPECIALIST` doesn't match |
| Claude invokes a custom skill declared as a YAML state machine | `atomic-gates` runner validates output schema at every transition |

**Mental model:** `superpowers` is **what to do**. `atomic-gates` is
**what can't happen**. You use both because the good workflow and the
mechanical enforcement are orthogonal.

---

## The adapter runtime

`atomic-gates` can execute `superpowers` skills directly, wrapping their
`SKILL.md` as a single-state virtual machine. You don't convert or copy
anything — the adapter runtime handles it at invocation time.

### How it works

When Claude invokes `Skill(superpowers:test-driven-development)`:

1. The `PreToolUse: Skill` hook fires and runs `lib/runner.py`
2. The runner looks for a local `skills/test-driven-development/skill.yaml`
   under the `atomic-gates` plugin. It doesn't find one.
3. The runner falls back to searching `~/.claude/plugins/**/skills/test-driven-development/SKILL.md`
4. It finds the `superpowers` version, reads it, strips YAML frontmatter
5. It constructs a **virtual machine** with one state (`execute`) whose
   `agent_prompt` is the markdown body verbatim, with `skip_output_check:
   true` so no YAML output is required
6. It creates a run in `.gates/runs/<run_id>.yaml`, persisting the
   invocation with `skill_id: "superpowers:test-driven-development"`
7. It injects the markdown body as `additionalContext` on the tool call

From Claude's perspective, it looks identical to loading the skill
directly. The difference is **you now have an audit trail**: every
invocation of every skill (native or adapted) is recorded in
`.gates/runs/` with a timestamp and history.

### Verifying adaptation happened

After Claude invokes a `superpowers` skill, check:

```bash
ls .gates/runs/
cat .gates/runs/<run_id>.yaml
```

You'll see something like:

```yaml
run_id: 1f4fcf19c5ca
skill_id: superpowers:test-driven-development
status: terminal
current_state: done
inputs: {}
created_at: '2026-04-11T15:16:22.808004+00:00'
updated_at: '2026-04-11T15:16:34.252662+00:00'
history:
- state: execute
  entered_at: '2026-04-11T15:16:22.808180+00:00'
  exited_at: '2026-04-11T15:16:34.252507+00:00'
- state: done
  entered_at: '2026-04-11T15:16:34.252660+00:00'
```

The `skill_id` preserves the `superpowers:` namespace, so you can tell
native vs. adapted runs apart when auditing.

### Limits of adaptation

Adapted runs don't validate output against a schema. The source is
prose — there's no YAML shape to enforce. If you want structured
output enforcement (e.g. "final verdict must be one of COMPLETE |
INCOMPLETE | NEEDS_DISCUSSION, no rationalization"), you need to
**promote** the skill to a native state machine.

---

## Promoting a superpowers skill to a state machine

If a particular `superpowers` skill is central to your workflow and you
want schema-validated output at every step, use the offline converter
to generate a starting skeleton:

```bash
python3 lib/import_skill.py \
  ~/.claude/plugins/cache/claude-plugins-official/superpowers/5.0.7/skills/test-driven-development/SKILL.md \
  -o skills/tdd-strict/skill.yaml
```

The converter reads the markdown, extracts every `## ` heading as a
state, and emits a YAML skeleton. **It is intentionally dumb** — every
agent_prompt starts with `# TODO: refine`, and meta headings (Red
Flags, Rationalization, Notes) are marked with `# WARNING` comments
because they're documentation, not fases.

From the skeleton, you:

1. Prune states that are documentation
2. Merge or split states to reflect real workflow fases
3. Replace each `agent_prompt` with a concrete task referencing
   `{{inputs.*}}`, `{{output.*}}`, and `{{output_path}}`
4. Add `output_schema` paths for states that produce structured data
5. Add `when` conditions to transitions if the machine has branches
6. Write a minimal `SKILL.md` that delegates to the runner

Once the machine is valid, test it standalone:

```bash
CLAUDE_PLUGIN_ROOT=$PWD CLAUDE_PROJECT_DIR=/tmp/test \
  python3 lib/runner.py <<<'{"tool_name":"Skill","tool_input":{"skill":"atomic-gates:tdd-strict","args":""}}'
```

And then the native version takes priority over the adapted version
automatically — the runner's cascade is `native → adapted → fail_silent`.

See [`authoring-state-machines.md`](./authoring-state-machines.md) for
the full state machine authoring guide.

---

## When to use which

**Use `superpowers` alone if:**

- You want a disciplined dev workflow **today** with zero setup
- You work across multiple harnesses (Cursor, Codex, Copilot CLI,
  Gemini CLI) and need consistency
- You don't need audit trails or schema validation — prose discipline
  is enough
- You value zero runtime dependencies

**Add `atomic-gates` on top if:**

- You want **mechanical enforcement** — particularly on commits, PR
  creation, or file writes outside specialist scope
- You need **audit trails** (regulated environments, compliance,
  "prove the agent followed the process")
- You're authoring a **custom workflow** where the rules are too
  domain-specific for prose and need structured output at every step
- You're willing to trade cross-harness portability and zero deps for
  deterministic guarantees

**Use `atomic-gates` alone if:**

- You only need gates, not a skill corpus
- Atomic hooks on commit/PR are sufficient for your use case
- You're building a custom workflow from scratch

---

## Troubleshooting

**Hook `PreToolUse: Skill` doesn't fire when Claude invokes a
superpowers skill.**

Check that `atomic-gates` is actually installed and its hooks are
loaded via `/hooks`. If the hook is listed but not firing, the most
common cause is that Claude Code hasn't been restarted after the most
recent plugin install/update. Hooks are loaded at session startup.

**Adapter can't find a superpowers `SKILL.md`.**

The runner searches `~/.claude/plugins/**/skills/<name>/SKILL.md`. If
`superpowers` was installed under a different path (e.g. via
`--plugin-dir` to a custom checkout), the rglob may not reach it. Run:

```bash
find ~/.claude/plugins -name SKILL.md -path "*/<skill-name>/*"
```

If nothing shows, the skill isn't on a path the adapter searches.
Either install `superpowers` via the standard marketplace, or write a
native skill.yaml in your own plugin.

**Gates fire during a `superpowers` skill and break its flow.**

This is correct behavior, not a bug. If a `superpowers` skill tries to
run `git commit` and you have `gate-metadata` configured, the commit
will fail — the gate doesn't know or care that a skill is running. If
you want certain skills to bypass certain gates, you'll need to make
the gate aware via a config flag or environment variable. File an
issue on `atomic-gates` if you hit this and want a design discussion.

---

## See also

- [Getting started](./getting-started.md) — if you haven't done the hello-world yet
- [Authoring state machines](./authoring-state-machines.md) — for building native skills
- [`docs/compatibility-with-superpowers.md`](../compatibility-with-superpowers.md) — the full comparison table and positioning
