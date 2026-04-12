# Design: `atomic-gates init`

**Date:** 2026-04-12
**Status:** Approved

## Summary

A Python script (`lib/init.py`) that scans a project, detects candidate
directories for gates, and generates `.gates/config.yaml`. A SKILL.md
(`atomic-gates:init`) wraps the script as a conversational wizard the
agent uses to guide the user through directory selection.

## Components

### 1. `lib/init.py` — the engine

Two modes:

- **Report** (default): scans the project, prints structured JSON to
  stdout. The agent or skill parses this to present options.
- **Auto** (`--auto`): generates `.gates/config.yaml` in the target
  project directory.

#### CLI interface

```
# Report mode — scan and output JSON
python3 lib/init.py /path/to/project

# Auto mode — generate config with all candidates
python3 lib/init.py --auto /path/to/project

# Auto mode — generate config with selected candidates only
python3 lib/init.py --auto --candidates 'src/components,src-tauri/src' /path/to/project
```

#### Detection heuristics

The scanner walks 2-3 levels deep and classifies directories by
**name pattern + dominant file extension**.

| Name pattern                              | Extension                    | Specialist   |
|-------------------------------------------|------------------------------|--------------|
| `components/`, `pages/`, `views/`, `ui/`  | `.tsx/.jsx/.vue/.svelte`     | `frontend`   |
| `api/`, `server/`, `commands/`, `src-tauri/` | `.py/.rs/.go/.java`       | `backend`    |
| `store/`, `state/`, `hooks/`              | `.ts/.tsx`                   | `frontend`   |
| `lib/`, `utils/`, `helpers/`              | (determined by extension)    | (varies)     |
| `tests/`, `__tests__/`, `spec/`           | any                          | `test`       |
| `migrations/`, `prisma/`, `schemas/`      | `.sql/.prisma`               | `database`   |
| `scripts/`, `.github/`, `infra/`, `deploy/` | any                       | `infra`      |

**Confidence levels:**

- `high` — both name pattern and extension match
- `medium` — only one matches
- `low` — inferred from extension alone

#### Report output shape

```json
{
  "project_name": "analytics-copilot",
  "project_root": "/path/to/project",
  "detected_stack": ["typescript", "rust", "react"],
  "candidates": [
    {
      "path": "src/components",
      "specialist": "frontend",
      "file_count": 47,
      "dominant_ext": ".tsx",
      "confidence": "high"
    }
  ],
  "suggested_gates": ["gate-metadata"],
  "existing_config": null
}
```

- `project_name`: derived from the directory name or `package.json` name
- `detected_stack`: inferred from file extensions and config files
  (`package.json` → typescript/react, `Cargo.toml` → rust, etc.)
- `suggested_gates`: always includes `gate-metadata`; adds
  `gate-pr-structure` if `.github/` exists
- `existing_config`: path to existing `.gates/config.yaml` if present,
  `null` otherwise (the skill uses this to warn before overwrite)

#### Auto mode behavior

- Writes `.gates/config.yaml` validated against
  `schemas/gates-config.schema.json`
- Creates `.gates/` directory if it doesn't exist
- Prints the created file path to stderr
- If `--candidates` is provided, only includes those paths from the
  scan results
- Without `--candidates`, includes all detected candidates
- Exits non-zero if no candidates are found

### 2. `skills/init/SKILL.md` — the conversational wrapper

A prose SKILL.md (no state machine) with instructions for the agent:

1. Call `python3 lib/init.py $PROJECT_DIR` via Bash
2. Parse the JSON report from stdout
3. Present candidates in a table to the user
4. Ask which directories to index
5. Call `python3 lib/init.py --auto --candidates '<selected>' $PROJECT_DIR`
6. Confirm that `.gates/config.yaml` was created
7. Suggest next steps (first commit to see gate-metadata fire)

### 3. Not included (YAGNI)

- No interactive stdin mode (the agent guides interaction)
- No `--depth` flag (fixed 2-3 level scan)
- No merge with existing config (v1 overwrites, warns if exists)
- No `--stdin` for complex JSON input
- No custom specialist names (user edits config after generation)
