#!/usr/bin/env python3
"""
atomic-gates: SKILL.md → skill.yaml skeleton converter.

Reads a markdown SKILL.md file (e.g. from the superpowers plugin) and
emits a skill.yaml skeleton that a human can then edit. Every `## `
heading in the markdown becomes a state in the machine. The body of
each section becomes the agent_prompt for that state, wrapped in a
TODO comment.

This is intentionally a dumb converter. It does NOT:
  - Decide which sections are "real fases" vs. meta like "Red Flags"
  - Infer output_schemas
  - Infer `when` conditions on transitions
  - Reason about what data each state produces

It produces a linear chain of states in document order, terminating in
`done`. The human then prunes non-states, merges states, adds
output_schemas, refines agent_prompts, etc. The point is to eliminate
the mechanical part of authoring a state machine for an existing
prose skill — NOT to replace human judgment about flow design.

Usage:
  python3 lib/import_skill.py path/to/SKILL.md
  python3 lib/import_skill.py path/to/SKILL.md -o path/to/skill.yaml
  python3 lib/import_skill.py path/to/SKILL.md --skill-id my-skill

Output is printed to stdout by default.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:
    sys.stderr.write("pyyaml is required: pip install pyyaml\n")
    sys.exit(1)


# Headings that are almost always NOT fases of execution. We still
# emit them as states (dumb converter), but we prefix a WARNING comment
# so the human knows to review them.
META_HEADING_KEYWORDS = {
    "red flag",
    "red flags",
    "rationalization",
    "rationalizations",
    "rationalization prevention",
    "persuasion",
    "iron law",
    "iron laws",
    "overview",
    "background",
    "why this exists",
    "notes",
    "caveats",
    "references",
    "reference",
    "see also",
    "when to use",
    "when not to use",
}


def slugify(text: str) -> str:
    """Turn a heading into a lowercase_underscored slug fit for a state id."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")
    return text or "state"


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter if present. Returns (frontmatter, body)."""
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    raw_frontmatter = content[4:end]
    body = content[end + 5 :]
    try:
        parsed = yaml.safe_load(raw_frontmatter) or {}
        if not isinstance(parsed, dict):
            parsed = {}
    except yaml.YAMLError:
        parsed = {}
    return parsed, body


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def split_sections(body: str) -> list[tuple[str, str]]:
    """Return list of (heading, content) pairs for each `## ` section.

    H1 (single #) is treated as the skill title and skipped.
    H3 and deeper (### and below) are kept inside their parent H2 section.
    """
    sections: list[tuple[str, str]] = []
    current_title: str | None = None
    current_start = 0

    lines = body.splitlines(keepends=True)
    cursor = 0

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            if level == 2:
                if current_title is not None:
                    section_body = body[current_start:cursor].rstrip()
                    sections.append((current_title, section_body))
                current_title = title
                current_start = cursor + len(line)
        cursor += len(line)

    if current_title is not None:
        section_body = body[current_start:].rstrip()
        sections.append((current_title, section_body))

    return sections


def is_meta_heading(heading: str) -> bool:
    normalized = heading.lower().strip().rstrip(":")
    return any(kw in normalized for kw in META_HEADING_KEYWORDS)


def build_skeleton(
    skill_id: str,
    description: str,
    sections: list[tuple[str, str]],
    source_path: Path,
    full_body: str,
) -> str:
    """Return the YAML string (with header comments) for the skeleton."""
    state_ids: list[tuple[str, str, str, bool]] = []
    used: set[str] = set()

    if not sections:
        # No headings at all — single "execute" state holding the whole body.
        state_ids.append(("execute", "Execute the skill", full_body.strip(), False))
    else:
        for heading, section_body in sections:
            base = slugify(heading)
            state_id = base
            n = 2
            while state_id in used:
                state_id = f"{base}_{n}"
                n += 1
            used.add(state_id)
            state_ids.append(
                (state_id, heading, section_body, is_meta_heading(heading))
            )

    # Terminal state
    state_ids.append(("done", "Terminal — machine finished", "", False))

    # Build states dict in insertion order
    states: dict[str, Any] = {}
    for i, (sid, title, section_body, is_meta) in enumerate(state_ids):
        if sid == "done":
            states[sid] = {
                "terminal": True,
                "description": title,
            }
            continue

        prompt_lines = [
            "# TODO: refine this prompt. The converter copied the section body"
            " verbatim.",
        ]
        if is_meta:
            prompt_lines.append(
                "# WARNING: heading '" + title + "' looks like documentation,"
                " not a fase. Consider removing this state entirely."
            )
        prompt_lines.append("")
        prompt_lines.append(section_body or "(empty section)")
        prompt_text = "\n".join(prompt_lines)

        next_state = state_ids[i + 1][0]
        states[sid] = {
            "description": title,
            "agent_prompt": prompt_text,
            "transitions": [{"to": next_state}],
        }

    skeleton = {
        "id": skill_id,
        "version": 1,
        "description": description
        or f"Converted skeleton from {source_path.name}. EDIT ME.",
        "initial_state": state_ids[0][0],
        "states": states,
    }

    yaml_body = yaml.safe_dump(
        skeleton, sort_keys=False, allow_unicode=True, width=100
    )

    header = [
        "# SKELETON — generated by lib/import_skill.py from:",
        f"#   {source_path}",
        "#",
        "# This file is a mechanical first draft. Every state was extracted",
        "# from a '## ' heading in the source markdown, in document order,",
        "# terminating in `done`. Next steps:",
        "#",
        "#   1. Prune states that are documentation (Red Flags, Rationalization,",
        "#      Background, Overview) — they were marked with WARNING comments.",
        "#   2. Merge or split states to reflect real workflow fases.",
        "#   3. Replace each agent_prompt with a concrete task, referencing",
        "#      {{inputs.*}}, {{output.*}}, and {{output_path}} as needed.",
        "#   4. Add output_schema paths for states that produce structured data.",
        "#   5. Add `when` conditions to transitions if the machine has branches.",
        "#   6. Declare inputs.required if the skill takes typed arguments.",
        "#",
        "# See docs/atomic-gates.md and schemas/skill-machine.schema.json",
        "# for the full state-machine reference.",
        "",
    ]
    return "\n".join(header) + yaml_body


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a SKILL.md file into a skill.yaml skeleton."
    )
    parser.add_argument("source", type=Path, help="Path to the source SKILL.md")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write to this file instead of stdout",
    )
    parser.add_argument(
        "--skill-id",
        type=str,
        default=None,
        help="Override the skill id (defaults to the frontmatter `name` "
        "or the source directory name)",
    )
    args = parser.parse_args()

    if not args.source.exists():
        sys.stderr.write(f"source file not found: {args.source}\n")
        sys.exit(1)

    content = args.source.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(content)

    skill_id = (
        args.skill_id
        or frontmatter.get("name")
        or args.source.parent.name
        or args.source.stem
    )
    description = frontmatter.get("description", "")

    sections = split_sections(body)
    skeleton = build_skeleton(skill_id, description, sections, args.source, body)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(skeleton, encoding="utf-8")
        sys.stderr.write(f"wrote skeleton to {args.output}\n")
    else:
        sys.stdout.write(skeleton)


if __name__ == "__main__":
    main()
