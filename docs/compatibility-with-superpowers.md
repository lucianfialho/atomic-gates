# Compatibility with `superpowers`

[`obra/superpowers`](https://github.com/obra/superpowers) is a polished
skill corpus maintained by Jesse Vincent — the same author who wrote
*[Rules and Gates](https://blog.fsck.com/2026/04/07/rules-and-gates/)*,
the post that inspired `atomic-gates`. It ships 14 skills covering
brainstorming, test-driven development, worktrees, planning, code
review, and more, polished against adversarial prompt-engineering
evaluation.

This document explains how `atomic-gates` relates to `superpowers`, why
they're complementary rather than competing, and the planned interop
roadmap.

---

## TL;DR

- `superpowers` is a **skill library**. It gives you content: 14 ready
  skills with rationalization tables, CSO-optimized descriptions, and a
  disciplined methodology for authoring new ones.
- `atomic-gates` is a **skill runtime**. It gives you infrastructure:
  `PreToolUse` hooks with blocking `exit 2`, a state-machine runner with
  schema validation at every transition, and persisted run state.

You probably want **both**. Install `superpowers` for the corpus; install
`atomic-gates` for the atomic gates on commit/PR and for authoring your
own skills as verified state machines when the discipline of prose isn't
enough for a given domain.

---

## What each project emphasizes

### `superpowers` — content and methodology

- Skills are Markdown with a minimal frontmatter (`name`, `description`).
- The methodology is the product: Iron Laws, Red Flag tables,
  rationalization tables per skill, a whole skill about authoring skills
  under test-driven pressure.
- Enforcement is **prompt-based and probabilistic**: a single
  `SessionStart` hook injects the `using-superpowers` text as
  `additionalContext`, and the rest is the model reading well-crafted
  markdown and choosing to follow.
- Cross-harness: works in Claude Code, Cursor, Codex, OpenCode, Copilot
  CLI, Gemini CLI — they've done the work of porting tool names across
  runtimes.
- Zero runtime dependencies by principle.

### `atomic-gates` — enforcement and verification

- Skills are YAML state machines with per-state output schemas.
- The infrastructure is the product: a `PreToolUse` runner, JSON Schema
  validation, run-state persistence, blocking hooks on `Bash(git commit
  *)`.
- Enforcement is **tool-based and deterministic**: exit code 2 from a
  hook cancels a tool call, and schema mismatch refuses to advance a
  state machine. The agent doesn't decide whether to comply.
- Claude Code only (for now).
- Runtime dep: Python 3 + `pyyaml`.

---

## Side-by-side

| Dimension | `superpowers` | `atomic-gates` |
|---|---|---|
| **Scope** | Content — 14 curated skills | Infrastructure — hooks, runner, schemas |
| **Skill format** | Markdown prose + frontmatter | YAML state machine + JSON Schema per state |
| **Output validation** | None (trust the model) | JSON Schema at every transition |
| **Run persistence** | None (state lives in the model's context) | `.gates/runs/<run_id>.yaml` with full history |
| **Hook layer** | `SessionStart` only | `PreToolUse: Bash` + `PreToolUse: Skill` |
| **Runner** | None; the model reads markdown and decides | `lib/runner.py` intercepts and arbitrates |
| **Dependencies** | Zero | Python 3 + `pyyaml` |
| **Deterministic blocking** | No | Yes (`exit 2` on gate failure) |
| **Cross-harness** | 6 runtimes | Claude Code only |
| **Skill authoring guidance** | A rigorous methodology (RED-GREEN-REFACTOR for prompts, adversarial evals) | (not yet — see roadmap) |
| **Audit trail** | None | Yes (every run persisted) |
| **Corpus maturity** | High — versioned, curated, battle-tested | Illustrative (2 example skills) |
| **Literal fidelity to "Rules and Gates"** | Medium — gates are rhetorical | High — gates block at the tooling layer |

---

## How to use them together

### Today (no interop yet)

1. **Install `superpowers`** for its corpus — brainstorming, TDD,
   worktrees, planning, review. That's your day-to-day methodology.
2. **Install `atomic-gates`** and configure `.gates/config.yaml` in your
   project. This gives you:
   - `gate-metadata` blocking `git commit` when an indexed directory's
     `.metadata/summary.yaml` is stale or missing.
   - Any custom state-machine skills you author (like `validate-issue`
     and `review-pr`) running with schema-validated transitions.

The two plugins coexist without conflict. Their hooks don't collide:
`superpowers` uses `SessionStart` for prompt injection; `atomic-gates`
uses `PreToolUse: Bash` and `PreToolUse: Skill` for enforcement.

### Planned — adapter runtime

The next milestone for interop is making `atomic-gates`' runner able to
execute `superpowers` skills directly. The design (not yet implemented):

1. Agent invokes `Skill(superpowers:test-driven-development)`.
2. `PreToolUse: Skill` hook (runner.py) intercepts.
3. Runner looks for a local `skill.yaml` matching the name. Doesn't find
   one (it's a `superpowers` skill).
4. Runner falls back to locating
   `~/.claude/plugins/**/superpowers/skills/test-driven-development/SKILL.md`.
5. If found, the runner creates a **single-state adapted run** that
   injects the entire markdown as `additionalContext` and marks the run
   as `adapted_from: superpowers`.
6. The run is persisted in `.gates/runs/<id>.yaml` — so even adapted
   `superpowers` skills get an audit trail.

**Tradeoff:** adapted skills don't get per-state schema validation (the
source is prose, not YAML), but they gain persistence and a standard
run-id for observability. A later step is a **semi-automatic converter**
that reads a `SKILL.md` and generates a `skill.yaml` skeleton with
suggested states, which a human then fills in to promote a specific
skill to a fully-verified state machine.

---

## When to pick one or the other

### Pick `superpowers` alone if…

- You want a disciplined dev workflow **today**, not in a month.
- You use multiple harnesses (Cursor, Codex, etc) and need consistency.
- You don't care about audit trails or schema validation.
- You value zero-dependency installs.
- You trust adversarial evaluation + Iron Laws + Red Flag tables more
  than schema enforcement.

### Add `atomic-gates` on top if…

- You want **mechanical enforcement** on specific actions —
  particularly commits, PR creation, file writes outside specialist
  scope.
- You need **audit trails** (regulated environments, compliance
  scenarios, "prove the agent followed the process" requirements).
- You're authoring a **custom workflow** where the rules are too
  domain-specific to express as prose and need structured output at
  every step.
- You're willing to trade cross-harness portability and zero deps for
  deterministic guarantees.

### Pick `atomic-gates` alone if…

- You only need gates, not a corpus — atomic hooks on commit/PR are
  sufficient for your use case.
- You're building your own skills from scratch and don't want the
  `superpowers` methodology.

---

## Why this project exists at all

The honest pitch: **the substrate described in *Rules and Gates* is
missing from the Claude Code ecosystem**. Every plugin author who tries
to enforce a rule ends up writing prose in `CLAUDE.md` and hoping the
model obeys. `superpowers` is the most successful example of doing that
really well — they've productionized the prose layer.

`atomic-gates` is the attempt to add the layer **below** that: hooks that
don't ask the model to follow a rule because the tool call literally
doesn't happen without the artifact. Once this layer exists, skill
libraries like `superpowers` can optionally plug into it for workflows
that need the extra rigor, without giving up the prose methodology for
workflows that don't.

It's not an alternative. It's a substrate.

---

## Reference

- [Rules and Gates](https://blog.fsck.com/2026/04/07/rules-and-gates/) — Jesse Vincent
- [`obra/superpowers`](https://github.com/obra/superpowers) — the skill corpus
- [`docs/atomic-gates.md`](./atomic-gates.md) — technical reference for this plugin
