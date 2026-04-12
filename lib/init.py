#!/usr/bin/env python3
"""
gates: project init scanner and config generator.

Two modes:
  - Report (default): scans the project, prints a JSON report to stdout
    with candidate directories, detected stack, and suggested gates.
  - Auto (--auto): generates .gates/config.yaml from scan results.

Usage:
  python3 lib/init.py /path/to/project
  python3 lib/init.py --auto /path/to/project
  python3 lib/init.py --auto --candidates 'src/components,src/store' /path/to/project
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_LIB_DIR = Path(__file__).resolve().parent
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

try:
    import yaml  # type: ignore
except ImportError:
    print('{"error": "pyyaml not available"}')
    sys.exit(1)

from schema_validate import validate, ValidationError  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_DEPTH = 3

# Name pattern → specialist mapping
NAME_PATTERNS: dict[str, str] = {
    "components": "frontend",
    "pages": "frontend",
    "views": "frontend",
    "ui": "frontend",
    "store": "frontend",
    "state": "frontend",
    "hooks": "frontend",
    "api": "backend",
    "server": "backend",
    "commands": "backend",
    "src-tauri": "backend",
    "lib": "",       # determined by extension
    "utils": "",
    "helpers": "",
    "tests": "test",
    "__tests__": "test",
    "spec": "test",
    "migrations": "database",
    "prisma": "database",
    "scripts": "infra",
    ".github": "infra",
    "infra": "infra",
    "deploy": "infra",
}

# Extension → specialist fallback (when name pattern gives "")
EXT_SPECIALIST: dict[str, str] = {
    ".tsx": "frontend",
    ".jsx": "frontend",
    ".vue": "frontend",
    ".svelte": "frontend",
    ".css": "frontend",
    ".scss": "frontend",
    ".py": "backend",
    ".rs": "backend",
    ".go": "backend",
    ".java": "backend",
    ".rb": "backend",
    ".sql": "database",
    ".prisma": "database",
    ".ts": "frontend",  # default; ambiguous without context
    ".js": "frontend",
}

# Extensions that indicate a stack
STACK_INDICATORS: dict[str, list[str]] = {
    "typescript": [".ts", ".tsx"],
    "javascript": [".js", ".jsx"],
    "python": [".py"],
    "rust": [".rs"],
    "go": [".go"],
    "java": [".java"],
    "ruby": [".rb"],
}

# Config files that indicate a stack/framework
CONFIG_INDICATORS: dict[str, str] = {
    "package.json": "node",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "Gemfile": "ruby",
}

FRAMEWORK_INDICATORS: dict[str, str] = {
    "next.config": "nextjs",
    "nuxt.config": "nuxt",
    "vite.config": "vite",
    "svelte.config": "svelte",
    "angular.json": "angular",
    "tauri.conf": "tauri",
}

# Directories to always skip
SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".next", ".nuxt",
    "dist", "build", "target", ".venv", "venv", ".gates",
    ".metadata", ".claude", ".agents", "coverage",
}

# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def _count_extensions(directory: Path) -> Counter:
    """Count file extensions in a directory (non-recursive)."""
    counts: Counter = Counter()
    try:
        for entry in directory.iterdir():
            if entry.is_file() and entry.suffix:
                counts[entry.suffix] += 1
    except PermissionError:
        pass
    return counts


def _dominant_ext(counts: Counter) -> str | None:
    """Return the most common extension, or None if empty."""
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def _specialist_from_ext(ext: str | None) -> str:
    """Determine specialist from a file extension."""
    if ext is None:
        return "unknown"
    return EXT_SPECIALIST.get(ext, "unknown")


def _classify_directory(
    rel_path: str, dir_name: str, ext_counts: Counter
) -> dict[str, Any] | None:
    """Classify a directory as a gate candidate, or None if not relevant."""
    file_count = sum(ext_counts.values())
    if file_count == 0:
        return None

    dominant = _dominant_ext(ext_counts)
    name_specialist = NAME_PATTERNS.get(dir_name)

    if name_specialist is not None:
        # Name pattern matched
        if name_specialist == "":
            # Ambiguous name (lib, utils) — use extension
            specialist = _specialist_from_ext(dominant)
            confidence = "medium"
        else:
            specialist = name_specialist
            ext_spec = _specialist_from_ext(dominant)
            if ext_spec == specialist:
                confidence = "high"
            else:
                confidence = "high"  # name pattern is authoritative
    else:
        # No name pattern — only extension
        specialist = _specialist_from_ext(dominant)
        if specialist == "unknown":
            return None  # skip unclassifiable directories
        confidence = "low"

    return {
        "path": rel_path,
        "specialist": specialist,
        "file_count": file_count,
        "dominant_ext": dominant,
        "confidence": confidence,
    }


def scan_project(project_dir: Path) -> dict[str, Any]:
    """Scan a project and return a structured report."""
    project_name = project_dir.name

    # Try to get name from package.json
    pkg_json = project_dir / "package.json"
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            project_name = pkg.get("name", project_name)
        except (json.JSONDecodeError, OSError):
            pass

    # Detect stack from config files
    detected_stack: list[str] = []
    for config_file, stack in CONFIG_INDICATORS.items():
        if (project_dir / config_file).exists():
            if stack not in detected_stack:
                detected_stack.append(stack)

    # Detect frameworks
    for entry in project_dir.iterdir():
        if entry.is_file():
            for pattern, framework in FRAMEWORK_INDICATORS.items():
                if entry.name.startswith(pattern):
                    if framework not in detected_stack:
                        detected_stack.append(framework)

    # Detect stack from extensions (walk to find what languages are used)
    all_ext_counts: Counter = Counter()
    candidates: list[dict[str, Any]] = []

    def _walk(current: Path, depth: int, prefix: str) -> None:
        if depth > MAX_DEPTH:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda e: e.name)
        except PermissionError:
            return

        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name in SKIP_DIRS or entry.name.startswith("."):
                # Allow .github specifically
                if entry.name != ".github":
                    continue

            rel = f"{prefix}/{entry.name}" if prefix else entry.name
            ext_counts = _count_extensions(entry)
            all_ext_counts.update(ext_counts)

            candidate = _classify_directory(rel, entry.name, ext_counts)
            if candidate is not None:
                candidates.append(candidate)

            _walk(entry, depth + 1, rel)

    _walk(project_dir, 0, "")

    # Add language stacks from extensions found
    for stack_name, exts in STACK_INDICATORS.items():
        if any(all_ext_counts.get(ext, 0) > 0 for ext in exts):
            if stack_name not in detected_stack:
                detected_stack.append(stack_name)

    # Detect react from package.json deps
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
            all_deps = {
                **pkg.get("dependencies", {}),
                **pkg.get("devDependencies", {}),
            }
            if "react" in all_deps and "react" not in detected_stack:
                detected_stack.append("react")
            if "vue" in all_deps and "vue" not in detected_stack:
                detected_stack.append("vue")
            if "svelte" in all_deps and "svelte" not in detected_stack:
                detected_stack.append("svelte")
        except (json.JSONDecodeError, OSError):
            pass

    # Filter out tiny directories (fewer than 3 files)
    candidates = [c for c in candidates if c["file_count"] >= 3]

    # Deduplicate: when a parent is a strong candidate (high/medium),
    # drop low-confidence children that would just add noise.
    # When a parent is low-confidence but has specific children, drop
    # the parent instead.
    all_paths = {c["path"]: c for c in candidates}
    deduped: list[dict[str, Any]] = []
    for c in candidates:
        path = c["path"]

        # Check if this directory has children that are also candidates
        has_children = any(
            p != path and p.startswith(path + "/") for p in all_paths
        )
        # Check if a parent directory is already a candidate
        parent_candidate = None
        for p in all_paths:
            if p != path and path.startswith(p + "/"):
                parent_candidate = all_paths[p]
                break

        # Drop vague parents when specific children exist
        if has_children and c["confidence"] == "low":
            continue

        # Drop low-confidence children when parent is already a candidate
        if parent_candidate and c["confidence"] == "low":
            continue

        deduped.append(c)

    # Suggested gates
    suggested_gates = ["gate-metadata"]
    if (project_dir / ".github").is_dir():
        suggested_gates.append("gate-pr-structure")

    # Check existing config
    existing = project_dir / ".gates" / "config.yaml"
    existing_config = str(existing) if existing.exists() else None

    return {
        "project_name": project_name,
        "project_root": str(project_dir),
        "detected_stack": detected_stack,
        "candidates": deduped,
        "suggested_gates": suggested_gates,
        "existing_config": existing_config,
    }


# ---------------------------------------------------------------------------
# Config generation
# ---------------------------------------------------------------------------


def generate_config(
    report: dict[str, Any],
    selected_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Build a .gates/config.yaml dict from a scan report."""
    candidates = report["candidates"]

    if selected_paths is not None:
        selected_set = set(selected_paths)
        candidates = [c for c in candidates if c["path"] in selected_set]

    if not candidates:
        print("error: no candidates to include in config", file=sys.stderr)
        sys.exit(1)

    # Collect unique specialists
    specialists = sorted(set(c["specialist"] for c in candidates))

    config: dict[str, Any] = {
        "version": 1,
        "project": {
            "name": report["project_name"],
        },
    }

    if report.get("detected_stack"):
        config["project"]["stack"] = report["detected_stack"]

    if specialists:
        config["specialists"] = specialists

    config["indexed_directories"] = [
        {"path": c["path"], "specialist": c["specialist"]}
        for c in candidates
    ]

    return config


def write_config(project_dir: Path, config: dict[str, Any]) -> Path:
    """Write .gates/config.yaml and return the path."""
    gates_dir = project_dir / ".gates"
    gates_dir.mkdir(parents=True, exist_ok=True)

    config_path = gates_dir / "config.yaml"

    # Validate against schema before writing
    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", ""))
    schema_path = _LIB_DIR.parent / "schemas" / "gates-config.schema.json"
    if not schema_path.exists() and plugin_root:
        schema_path = plugin_root / "schemas" / "gates-config.schema.json"

    if schema_path.exists():
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            validate(config, schema)
        except ValidationError as e:
            print(f"error: generated config fails validation: {e}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"warning: could not parse schema: {e}", file=sys.stderr)

    with config_path.open("w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return config_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan a project and generate .gates/config.yaml"
    )
    parser.add_argument(
        "project_dir",
        nargs="?",
        default=os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()),
        help="Path to the project to scan (default: $CLAUDE_PROJECT_DIR or cwd)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Generate .gates/config.yaml instead of printing a report",
    )
    parser.add_argument(
        "--candidates",
        type=str,
        default=None,
        help="Comma-separated list of candidate paths to include (auto mode only)",
    )

    args = parser.parse_args()
    project_dir = Path(args.project_dir).resolve()

    if not project_dir.is_dir():
        print(f"error: {project_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    report = scan_project(project_dir)

    if not args.auto:
        # Report mode — print JSON to stdout
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
        sys.exit(0)

    # Auto mode — generate config
    selected = None
    if args.candidates:
        selected = [p.strip() for p in args.candidates.split(",") if p.strip()]

    if report["existing_config"]:
        print(
            f"warning: overwriting existing config at {report['existing_config']}",
            file=sys.stderr,
        )

    config = generate_config(report, selected)
    config_path = write_config(project_dir, config)
    print(f"created: {config_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
