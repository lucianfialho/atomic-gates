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


def extract_skill_call(hook_input: dict) -> tuple[str, dict] | None:
    """Return (skill_name, arguments) if this is a Skill() call, else None."""
    if hook_input.get("tool_name") != "Skill":
        return None
    tool_input = hook_input.get("tool_input") or {}
    skill_name = tool_input.get("skill_name") or tool_input.get("skill")
    if not skill_name:
        return None

    # Claude Code prefixes skill names with the plugin namespace
    # (e.g. "atomic-gates:validate-issue"). Strip it so we can locate
    # the file under skills/<bare_name>/skill.yaml.
    if ":" in skill_name:
        skill_name = skill_name.split(":", 1)[1]

    # Arguments may come as structured dict or as a string (user typed `/skill arg`)
    args_raw = tool_input.get("arguments") or tool_input.get("args") or {}
    if isinstance(args_raw, str):
        arguments = _parse_cli_args(args_raw)
    elif isinstance(args_raw, dict):
        arguments = args_raw
    else:
        arguments = {}
    return skill_name, arguments


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


def load_skill_machine(plugin_root: Path, skill_name: str) -> dict | None:
    """Load skills/<name>/skill.yaml. Returns None if it doesn't exist."""
    path = plugin_root / "skills" / skill_name / "skill.yaml"
    if not path.exists():
        return None
    machine = _read_yaml(path)
    schema_path = plugin_root / "schemas" / "skill-machine.schema.json"
    if schema_path.exists():
        schema = json.loads(schema_path.read_text())
        try:
            validate(machine, schema)
        except ValidationError as e:
            _fail_silent(f"skill.yaml invalid: {e}")
    return machine


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
    state_def: dict, output_path: Path, plugin_root: Path
) -> list[str]:
    """Validate a state's output YAML against its declared schema.

    Returns a list of error messages (empty if valid or no schema declared).
    Errors are shaped the same as gate_failures so the caller can treat them
    uniformly: retry the state with the error message as context.
    """
    schema_rel = state_def.get("output_schema")
    if not schema_rel:
        return []
    schema_path = (plugin_root / schema_rel).resolve()
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

    out_path = run_output_path(project_dir, run["run_id"], current)
    if not out_path.exists():
        context = build_state_context(run, machine, project_dir)
        prompt = state_prompt(machine, current, context)
        return format_context_message(
            run, machine, current, prompt,
            gate_failures=[f"output file missing: {out_path}"],
        )

    schema_errors = validate_state_output(
        state_def, out_path, plugin_root
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
    run["history"][-1]["output_path"] = str(out_path)
    run["current_state"] = next_state
    run["history"].append({"state": next_state, "entered_at": _now()})

    if machine["states"][next_state].get("terminal"):
        run["status"] = "terminal"
        save_run(project_dir, run)
        return (
            f"gates runner — skill={machine['id']} run_id={run['run_id']}\n"
            f"state: {next_state} (terminal)\n\n"
            f"Machine finished. Final output at {out_path}."
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

        skill_name, arguments = call
        plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or _LIB_DIR.parent)
        project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())

        machine = load_skill_machine(plugin_root, skill_name)
        if machine is None:
            _fail_silent(f"no skill.yaml for {skill_name}")

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
