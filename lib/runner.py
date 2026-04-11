#!/usr/bin/env python3
"""
gates runner — PreToolUse hook that arbitrates Skill() invocations
against a state machine declared in skills/<name>/skill.yaml.

Invocation contract:
  - stdin: Claude Code PreToolUse hook JSON
  - stdout: hook JSON response (additionalContext, permissionDecision)
  - env:
      CLAUDE_PROJECT_DIR — target project root (where .gates/runs/ lives)
      CLAUDE_PLUGIN_ROOT — plugin root (where skills/, schemas/, lib/ live)

If the intercepted tool is not `Skill`, or the invoked skill has no
skill.yaml (it's a plain markdown skill), the runner exits silently with
no output — Claude Code proceeds as normal.

If the invoked skill has a skill.yaml, the runner:
  - creates a new run (when no run_id is passed) and injects the
    initial state's prompt as additionalContext
  - advances an existing run (when run_id is passed) by reading the
    previous state's output, validating it, running gates, evaluating
    transitions, and injecting the next state's prompt

Failures never break the agent: on unexpected errors the runner logs
to stderr and exits 0 with no output, so the Skill() call proceeds.
The only time the runner blocks the call is when a gate fails.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any

# Make lib/ importable regardless of cwd
_LIB_DIR = Path(__file__).resolve().parent
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

def _fail_silent(reason: str) -> None:
    """Exit 0 without output. The Skill() call proceeds unmodified."""
    print(f"[gates] noop: {reason}", file=sys.stderr)
    sys.exit(0)


try:
    import yaml  # type: ignore
except ImportError:
    _fail_silent("pyyaml not available")

from schema_validate import validate, ValidationError  # noqa: E402


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _emit(additional_context: str, decision: str = "allow", reason: str = "") -> None:
    payload: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
        }
    }
    if additional_context:
        payload["hookSpecificOutput"]["additionalContext"] = additional_context
    if reason:
        payload["hookSpecificOutput"]["permissionDecisionReason"] = reason
    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    sys.exit(0)


def _read_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


# ---------- hook input parsing -----------------------------------------------


def parse_hook_input() -> dict[str, Any]:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            _fail_silent("empty stdin")
        return json.loads(raw)
    except json.JSONDecodeError as e:
        _fail_silent(f"bad stdin json: {e}")
    return {}  # unreachable


def extract_skill_call(
    hook_input: dict,
) -> tuple[str, str | None, dict] | None:
    """Return (skill_name, namespace, arguments) for a Skill() call, else None.

    Claude Code prefixes skill names with the owning plugin namespace
    (e.g. "atomic-gates:validate-issue", "superpowers:tdd"). We split
    the prefix so callers can (a) look for a local skill.yaml under the
    bare name, and (b) fall back to the namespace when searching other
    installed plugins for an adaptable SKILL.md.
    """
    if hook_input.get("tool_name") != "Skill":
        return None
    tool_input = hook_input.get("tool_input") or {}
    full_name = tool_input.get("skill_name") or tool_input.get("skill")
    if not full_name:
        return None

    if ":" in full_name:
        namespace, skill_name = full_name.split(":", 1)
    else:
        namespace, skill_name = None, full_name

    # Arguments may come as structured dict or as a string (user typed `/skill arg`)
    args_raw = tool_input.get("arguments") or tool_input.get("args") or {}
    if isinstance(args_raw, str):
        arguments = _parse_cli_args(args_raw)
    elif isinstance(args_raw, dict):
        arguments = args_raw
    else:
        arguments = {}
    return skill_name, namespace, arguments


def _parse_cli_args(raw: str) -> dict:
    """Parse `key=value key2=value2` style args into a dict."""
    out: dict[str, Any] = {}
    for token in raw.split():
        if "=" not in token:
            continue
        k, v = token.split("=", 1)
        out[k.strip()] = _coerce(v.strip())
    return out


def _coerce(value: str) -> Any:
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value.strip("'\"")


# ---------- skill.yaml loading & validation ----------------------------------


def load_skill_machine(
    plugin_root: Path, skill_name: str, namespace: str | None = None
) -> dict | None:
    """Load skills/<name>/skill.yaml for the given skill.

    Search order:
      1. The current plugin (atomic-gates itself) — skills/<name>/skill.yaml
         under `plugin_root`. This is how atomic-gates' own reference
         skills (validate-issue, review-pr) are loaded.
      2. If the invocation carried a `namespace` prefix (e.g.
         "claude-dev-pipeline:solve-issue"), search other installed
         plugins under ~/.claude/plugins/** for a matching skill.yaml.
         This is what lets a SEPARATE plugin ship its own state-machine
         skills that the atomic-gates runner executes natively.

    When a skill is loaded from an external plugin, the returned machine
    has an `_origin_plugin_root` key pointing at the plugin directory
    that owns the skill. Later stages (output schema resolution) use
    that path so relative references inside the external skill work.
    """
    # 1. Prefer a skill under the current plugin root
    local_path = plugin_root / "skills" / skill_name / "skill.yaml"
    if local_path.exists():
        machine = _load_and_validate_skill_yaml(local_path, plugin_root)
        machine["_origin_plugin_root"] = str(plugin_root)
        return machine

    # 2. Fall back to external plugins on disk
    if namespace:
        external_path = _find_external_skill_yaml(skill_name, namespace)
        if external_path is not None:
            origin_root = _guess_plugin_root_from_skill_path(external_path)
            machine = _load_and_validate_skill_yaml(external_path, plugin_root)
            machine["_origin_plugin_root"] = str(origin_root)
            # Namespace the id so run-state audit trail is unambiguous
            # across plugins (e.g. claude-dev-pipeline:solve-issue instead
            # of just solve-issue)
            machine["id"] = f"{namespace}:{machine['id']}"
            return machine

    return None


def _load_and_validate_skill_yaml(path: Path, plugin_root: Path) -> dict:
    """Read a skill.yaml from disk and validate against the schema that
    ships with atomic-gates. The schema is authoritative regardless of
    which plugin owns the skill file.
    """
    machine = _read_yaml(path)
    schema_path = plugin_root / "schemas" / "skill-machine.schema.json"
    if schema_path.exists():
        schema = json.loads(schema_path.read_text())
        try:
            validate(machine, schema)
        except ValidationError as e:
            _fail_silent(f"skill.yaml invalid at {path}: {e}")
    return machine


def _find_external_skill_yaml(
    skill_name: str, namespace: str | None
) -> Path | None:
    """Search ~/.claude/plugins/** for skills/<name>/skill.yaml.

    Prefers matches whose full path contains the namespace hint — this
    lets an invocation like Skill(claude-dev-pipeline:solve-issue) find
    the skill inside the claude-dev-pipeline plugin directory even if
    other plugins happen to ship a skill with the same bare name.
    """
    home_plugins = Path.home() / ".claude" / "plugins"
    if not home_plugins.exists():
        return None

    pattern = f"skills/{skill_name}/skill.yaml"
    candidates = list(home_plugins.rglob(pattern))
    if not candidates:
        return None

    if namespace:
        for c in candidates:
            if namespace in str(c):
                return c

    return candidates[0]


def _guess_plugin_root_from_skill_path(skill_yaml_path: Path) -> Path:
    """Given a skills/<name>/skill.yaml path, walk up to find the
    plugin root — the ancestor directory that contains .claude-plugin/
    or looks like a plugin (has both skills/ and hooks/).
    """
    for ancestor in skill_yaml_path.parents:
        if (ancestor / ".claude-plugin").exists():
            return ancestor
        if (ancestor / "skills").is_dir() and (ancestor / "hooks").is_dir():
            return ancestor
    # Fallback: /<root>/skills/<name>/skill.yaml → /<root>
    return skill_yaml_path.parent.parent.parent


def load_adapted_skill(
    skill_name: str, namespace: str | None
) -> dict | None:
    """Search ~/.claude/plugins/** for a SKILL.md and wrap it as a
    single-state machine. Used when no native skill.yaml exists for the
    invoked name — e.g. when the agent invokes a superpowers skill and
    we want to run it under atomic-gates for the audit trail alone.
    """
    md_path = _find_external_skill_md(skill_name, namespace)
    if md_path is None:
        return None

    content = md_path.read_text(encoding="utf-8")

    # Strip YAML frontmatter if present (SKILL.md usually starts with ---)
    body = content
    if content.startswith("---\n"):
        end = content.find("\n---\n", 4)
        if end != -1:
            body = content[end + 5 :]

    display_id = f"{namespace}:{skill_name}" if namespace else skill_name
    return {
        "id": display_id,
        "version": 1,
        "description": f"Adapted from {md_path}",
        "initial_state": "execute",
        "states": {
            "execute": {
                "description": "Execute the adapted skill body as-is",
                "agent_prompt": body.strip(),
                "skip_output_check": True,
                "transitions": [{"to": "done"}],
            },
            "done": {
                "terminal": True,
                "description": "Adapted skill finished",
            },
        },
    }


def _find_external_skill_md(
    skill_name: str, namespace: str | None
) -> Path | None:
    """Search standard Claude Code plugin install paths for a SKILL.md
    matching the given skill name. Prefers matches whose path contains
    the namespace, falls back to any match.
    """
    home_plugins = Path.home() / ".claude" / "plugins"
    if not home_plugins.exists():
        return None

    pattern = f"skills/{skill_name}/SKILL.md"
    candidates = list(home_plugins.rglob(pattern))
    if not candidates:
        return None

    if namespace:
        for c in candidates:
            if namespace in str(c):
                return c

    return candidates[0]


def validate_inputs(machine: dict, arguments: dict) -> list[str]:
    """Check that required inputs are present and of the right type."""
    errors: list[str] = []
    spec = (machine.get("inputs") or {}).get("required") or []
    py_types = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
    }
    for item in spec:
        name = item["name"]
        expected_type = item["type"]
        if name not in arguments:
            errors.append(f"missing input: {name}")
            continue
        expected_py = py_types[expected_type]
        value = arguments[name]
        if expected_type == "integer" and isinstance(value, bool):
            errors.append(f"input {name}: expected integer, got boolean")
        elif not isinstance(value, expected_py):
            errors.append(
                f"input {name}: expected {expected_type}, got {type(value).__name__}"
            )
    return errors


# ---------- run state --------------------------------------------------------


def runs_dir(project_dir: Path) -> Path:
    return project_dir / ".gates" / "runs"


def run_file(project_dir: Path, run_id: str) -> Path:
    return runs_dir(project_dir) / f"{run_id}.yaml"


def run_output_path(project_dir: Path, run_id: str, state: str) -> Path:
    return runs_dir(project_dir) / run_id / f"{state}.output.yaml"


def create_run(
    project_dir: Path, machine: dict, arguments: dict
) -> dict:
    run_id = uuid.uuid4().hex[:12]
    initial = machine["initial_state"]
    run = {
        "run_id": run_id,
        "skill_id": machine["id"],
        "status": "running",
        "current_state": initial,
        "inputs": arguments,
        "created_at": _now(),
        "updated_at": _now(),
        "history": [
            {"state": initial, "entered_at": _now()}
        ],
    }
    _write_yaml(run_file(project_dir, run_id), run)
    return run


def load_run(project_dir: Path, run_id: str) -> dict | None:
    path = run_file(project_dir, run_id)
    if not path.exists():
        return None
    return _read_yaml(path)


def save_run(project_dir: Path, run: dict) -> None:
    run["updated_at"] = _now()
    _write_yaml(run_file(project_dir, run["run_id"]), run)


# ---------- template interpolation -------------------------------------------


_TEMPLATE_RE = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


def interpolate(template: str, context: dict) -> str:
    def repl(match: re.Match) -> str:
        expr = match.group(1)
        value = _resolve(expr, context)
        return _render_value(value)
    return _TEMPLATE_RE.sub(repl, template)


def _render_value(value: Any) -> str:
    """Render an interpolated value for agent consumption.

    Scalars render as their string form. Dicts and lists render as JSON —
    inequívoco, parseável, e não se confunde com Python literals.
    """
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _resolve(expr: str, context: dict) -> Any:
    parts = expr.split(".")
    current: Any = context
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ""  # unresolved refs render as empty string
    return current


# ---------- transition evaluation --------------------------------------------


_WHEN_RE = re.compile(
    r"^\s*([\w.]+)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$"
)


def evaluate_when(expression: str, context: dict) -> bool:
    match = _WHEN_RE.match(expression)
    if not match:
        return False
    left_expr, op, right_expr = match.groups()
    left = _resolve(left_expr, context)
    right = _parse_literal(right_expr)
    try:
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == ">=":
            return left >= right
        if op == "<=":
            return left <= right
        if op == ">":
            return left > right
        if op == "<":
            return left < right
    except TypeError:
        return False
    return False


def _parse_literal(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def pick_next_state(
    transitions: list[dict], context: dict
) -> str | None:
    for tr in transitions:
        when = tr.get("when")
        if when is None or evaluate_when(when, context):
            return tr["to"]
    return None


# ---------- gate execution ---------------------------------------------------


def validate_state_output(
    state_def: dict,
    output_path: Path,
    plugin_root: Path,
    machine: dict | None = None,
) -> list[str]:
    """Validate a state's output YAML against its declared schema.

    Returns a list of error messages (empty if valid or no schema declared).
    Errors are shaped the same as gate_failures so the caller can treat them
    uniformly: retry the state with the error message as context.

    When the machine was loaded from an external plugin (cross-plugin
    execution), `machine["_origin_plugin_root"]` points at the plugin
    directory that owns the skill file. Relative `output_schema` paths
    are resolved against that root, not atomic-gates' own plugin_root.
    """
    schema_rel = state_def.get("output_schema")
    if not schema_rel:
        return []
    origin_root = plugin_root
    if machine is not None:
        raw_origin = machine.get("_origin_plugin_root")
        if raw_origin:
            origin_root = Path(raw_origin)
    schema_path = (origin_root / schema_rel).resolve()
    if not schema_path.exists():
        return [f"declared output_schema not found: {schema_rel}"]
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [f"output_schema is not valid JSON: {e}"]
    try:
        output_data = _read_yaml(output_path)
    except Exception as e:  # noqa: BLE001
        return [f"output file is not valid YAML: {e}"]
    try:
        validate(output_data, schema)
    except ValidationError as e:
        return [f"output schema validation failed: {e}"]
    return []


def run_gates(
    gates: list[dict],
    plugin_root: Path,
    project_dir: Path,
    run_id: str,
) -> list[str]:
    failures: list[str] = []
    for gate in gates:
        script = gate["script"]
        script_path = (plugin_root / script).resolve()
        if not script_path.exists():
            failures.append(f"gate script not found: {script}")
            continue
        try:
            result = subprocess.run(
                [str(script_path)],
                cwd=str(project_dir),
                env={**os.environ, "GATES_RUN_ID": run_id},
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"gate {script} timed out")
            continue
        if result.returncode != 0:
            msg = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            failures.append(f"gate {script}: {msg}")
    return failures


# ---------- context building -------------------------------------------------


def build_state_context(
    run: dict, machine: dict, project_dir: Path
) -> dict:
    """Build the template context: inputs + outputs from previous states."""
    context: dict[str, Any] = {
        "inputs": run["inputs"],
        "run_id": run["run_id"],
        "output_path": str(
            run_output_path(project_dir, run["run_id"], run["current_state"])
        ),
    }
    outputs: dict[str, Any] = {}
    for entry in run["history"][:-1]:  # exclude current state
        state = entry["state"]
        out_path = run_output_path(project_dir, run["run_id"], state)
        if out_path.exists():
            outputs[state] = _read_yaml(out_path)
    context["outputs"] = outputs
    # Convenience: last state's output as `output`
    if len(run["history"]) >= 2:
        prev = run["history"][-2]["state"]
        if prev in outputs:
            context["output"] = outputs[prev]
    return context


def state_prompt(
    machine: dict, state_name: str, context: dict
) -> str:
    state = machine["states"][state_name]
    template = state.get("agent_prompt") or state.get("description") or ""
    return interpolate(template, context)


def format_context_message(
    run: dict,
    machine: dict,
    state_name: str,
    prompt: str,
    gate_failures: list[str] | None = None,
) -> str:
    lines = [
        f"gates runner — skill={machine['id']} run_id={run['run_id']}",
        f"state: {state_name}",
    ]
    if gate_failures:
        lines.append("")
        lines.append("PREVIOUS STATE GATES FAILED — retry required:")
        for f in gate_failures:
            lines.append(f"  - {f}")
    lines.append("")
    lines.append("TASK:")
    lines.append(prompt.strip())
    lines.append("")
    lines.append(
        f"When finished, invoke Skill({machine['id']}, {{ run_id: '{run['run_id']}' }}) "
        "to advance the machine."
    )
    return "\n".join(lines)


# ---------- main flow --------------------------------------------------------


def handle_existing_run(
    run: dict,
    machine: dict,
    plugin_root: Path,
    project_dir: Path,
) -> str:
    """Advance an existing run and return the additionalContext string."""
    current = run["current_state"]
    state_def = machine["states"][current]

    if state_def.get("terminal"):
        return (
            f"gates runner — skill={machine['id']} run_id={run['run_id']}\n"
            f"state: {current} (terminal)\n\n"
            "This run already finished. No further action required."
        )

    skip_output_check = state_def.get("skip_output_check", False)
    out_path = run_output_path(project_dir, run["run_id"], current)

    if not skip_output_check:
        if not out_path.exists():
            context = build_state_context(run, machine, project_dir)
            prompt = state_prompt(machine, current, context)
            return format_context_message(
                run, machine, current, prompt,
                gate_failures=[f"output file missing: {out_path}"],
            )

        schema_errors = validate_state_output(
            state_def, out_path, plugin_root, machine
        )
        if schema_errors:
            context = build_state_context(run, machine, project_dir)
            prompt = state_prompt(machine, current, context)
            return format_context_message(
                run, machine, current, prompt, gate_failures=schema_errors
            )

        gate_failures = run_gates(
            state_def.get("gate") or [], plugin_root, project_dir, run["run_id"]
        )
        if gate_failures:
            context = build_state_context(run, machine, project_dir)
            prompt = state_prompt(machine, current, context)
            return format_context_message(
                run, machine, current, prompt, gate_failures=gate_failures
            )

    context = build_state_context(run, machine, project_dir)
    if not skip_output_check and out_path.exists():
        context["output"] = _read_yaml(out_path)
    next_state = pick_next_state(state_def.get("transitions") or [], context)

    if next_state is None:
        run["status"] = "error"
        run["error"] = f"no transition matched from state {current}"
        save_run(project_dir, run)
        return (
            f"gates runner — run {run['run_id']} errored: "
            f"no transition matched from state '{current}'."
        )

    run["history"][-1]["exited_at"] = _now()
    if not skip_output_check and out_path.exists():
        run["history"][-1]["output_path"] = str(out_path)
    run["current_state"] = next_state
    run["history"].append({"state": next_state, "entered_at": _now()})

    if machine["states"][next_state].get("terminal"):
        run["status"] = "terminal"
        save_run(project_dir, run)
        final_location = (
            str(out_path) if (not skip_output_check and out_path.exists())
            else f".gates/runs/{run['run_id']}.yaml (run state)"
        )
        return (
            f"gates runner — skill={machine['id']} run_id={run['run_id']}\n"
            f"state: {next_state} (terminal)\n\n"
            f"Machine finished. Final output at {final_location}."
        )

    save_run(project_dir, run)
    new_context = build_state_context(run, machine, project_dir)
    prompt = state_prompt(machine, next_state, new_context)
    return format_context_message(run, machine, next_state, prompt)


def main() -> None:
    try:
        hook = parse_hook_input()
        call = extract_skill_call(hook)
        if call is None:
            _fail_silent("not a Skill() call")

        skill_name, namespace, arguments = call
        plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or _LIB_DIR.parent)
        project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())

        # 1. Prefer a native skill.yaml. Searches atomic-gates' own
        #    skills/ first, then falls back to OTHER installed plugins
        #    under ~/.claude/plugins/** when a namespace is given.
        machine = load_skill_machine(plugin_root, skill_name, namespace)

        # 2. Fall back to adapting an external plugin's SKILL.md
        #    (e.g. superpowers prose skills) as a single-state run.
        if machine is None:
            machine = load_adapted_skill(skill_name, namespace)

        if machine is None:
            _fail_silent(f"no skill.yaml or adaptable SKILL.md for {skill_name}")

        run_id = arguments.get("run_id")
        if run_id:
            run = load_run(project_dir, run_id)
            if run is None:
                _fail_silent(f"run_id {run_id} not found")
            message = handle_existing_run(run, machine, plugin_root, project_dir)
            _emit(message)
            return

        input_errors = validate_inputs(machine, arguments)
        if input_errors:
            _emit(
                additional_context="gates runner: invalid inputs — "
                + "; ".join(input_errors),
                decision="deny",
                reason="invalid skill inputs",
            )
            return

        run = create_run(project_dir, machine, arguments)
        context = build_state_context(run, machine, project_dir)
        prompt = state_prompt(machine, run["current_state"], context)
        message = format_context_message(run, machine, run["current_state"], prompt)
        _emit(message)

    except SystemExit:
        raise
    except Exception:  # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        _fail_silent("unexpected error")


if __name__ == "__main__":
    main()
