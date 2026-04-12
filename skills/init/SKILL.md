---
name: init
description: Scan a project and generate .gates/config.yaml with guided directory selection
---

# atomic-gates init

Set up atomic-gates in an existing project. You will scan the project,
present candidate directories, let the user choose which to index, and
generate `.gates/config.yaml`.

## Instructions

Follow these steps exactly:

### 1. Scan the project

Run the scanner to get a JSON report:

```
python3 $CLAUDE_PLUGIN_ROOT/lib/init.py $CLAUDE_PROJECT_DIR
```

Parse the JSON output. It contains `candidates` (directories to gate),
`detected_stack`, `suggested_gates`, and `existing_config`.

If `existing_config` is not null, warn the user that a config already
exists and ask if they want to overwrite it before continuing.

### 2. Present candidates

Show the candidates in a table:

```
Found N candidate directories:

| # | Directory          | Specialist | Files | Confidence |
|---|--------------------|------------|-------|------------|
| 1 | src/components     | frontend   | 30    | high       |
| 2 | src-tauri          | backend    | 4     | high       |
| 3 | src/lib            | frontend   | 5     | medium     |

Detected stack: typescript, rust, react
Suggested gates: gate-metadata, gate-pr-structure
```

Then ask:

> Which directories do you want to index? You can say "all", list
> numbers (e.g. "1, 2"), or "none" to configure manually later.

### 3. Generate config

Based on the user's selection, call the generator:

- If "all": `python3 $CLAUDE_PLUGIN_ROOT/lib/init.py --auto $CLAUDE_PROJECT_DIR`
- If specific: `python3 $CLAUDE_PLUGIN_ROOT/lib/init.py --auto --candidates 'path1,path2' $CLAUDE_PROJECT_DIR`
- If "none": tell the user to create `.gates/config.yaml` manually and
  point them to `docs/guides/getting-started.md`

### 4. Confirm and suggest next steps

After the config is created, tell the user:

> `.gates/config.yaml` created. To see a gate in action:
>
> 1. Edit a file in an indexed directory
> 2. Try to `git commit` — the metadata gate will block it
> 3. Fill in the `.metadata/summary.yaml` stub that gets created
> 4. Stage it and commit again
>
> Run `git add .gates/` to track your gate config.

## Notes

- Do NOT modify the generated config yourself. Let the user review and
  edit it if they want changes.
- The scanner only looks 3 levels deep. If the user wants deeper
  directories, they can add them manually to the config.
- The skill is a one-shot wizard. There is no state machine — just
  follow the steps above linearly.
