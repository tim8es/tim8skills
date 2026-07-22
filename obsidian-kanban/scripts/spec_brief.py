#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec_brief.py — compact spec summary for role entry.

The recommended entry point for an agent is `kanban.py resume <WORKSPACE_ROOT>
[slug] --brief`, which calls `print_spec_brief()` below directly (the same
code, a single render path). This module holds the brief formatting logic itself;
its own CLI (`main()`) is kept for a direct point call outside the `kanban.py`
dispatcher.

Prints only the actionable parts of the spec, saving 50-70% of tokens
compared to a full Read when entering a role:
  - Key YAML fields: status, step, priority, owner
  - Unchecked [ ] items from DoD, Subtasks, Test Checklist, Review Checklist
  - The Output / Artifacts section (in full)
  - !!!ВНИМАНИЕ!!! lines from ## Comments

Checked [x] items and regular comments are not printed.
Sections with no unchecked items are omitted.

Usage:
    python scripts/spec_brief.py "$WORKSPACE_ROOT" <slug>
    python scripts/kanban.py resume "$WORKSPACE_ROOT" <slug> --brief
"""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import re
from pathlib import Path

import lint_board as lb

# Checklist sections — print only unchecked [ ] items
CHECKLIST_SECTIONS = {
    "Definition of Done (DoD)",
    "DoD",
    "Subtasks",
    "Test Checklist",
    "Тестовый чеклист",
    "Review Checklist",
    "Чеклист ревью",
}

# Sections printed in full (no filtering)
FULL_SECTIONS = {
    "Output / Artifacts",
    "Artifacts",
}

UNCHECKED_RE = re.compile(r"^\s*-\s+\[ \]\s*\S")
ATTENTION_RE = re.compile(r"!!!ВНИМАНИЕ!!!")


def split_sections(text: str) -> list[tuple[str, list[str]]]:
    """Splits the spec body (after the frontmatter) into sections [(heading, lines)].
    Headings inside a code fence (``` ... ```) are ignored.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
        if not in_fence:
            m = re.match(r"^(#{1,3})\s+(.+)", line)
            if m:
                if current_title or current_lines:
                    sections.append((current_title, current_lines))
                current_title = m.group(2).strip()
                current_lines = []
                continue
        current_lines.append(line)
    if current_title or current_lines:
        sections.append((current_title, current_lines))
    return sections


def print_spec_brief(workspace: str | Path, slug: str) -> int:
    """Render and print the compact spec brief for `slug` — the shared body of
    `spec_brief.py`'s CLI, called directly by both that CLI and
    `resume.py --brief` so the two entry points stay byte-for-byte identical.
    Do not duplicate this logic elsewhere; extend here instead.

    Returns the process exit code (0 on success, 1 if the spec file is
    missing — same contract as the original `spec_brief.main()`).
    """
    root = Path(workspace).expanduser()
    specs_dir = (root if root.name == "tasks" else root / "tasks") / "specs"
    spec_path = specs_dir / f"{slug}.md"

    if not spec_path.is_file():
        print(f"✗ Spec not found: {spec_path}", file=sys.stderr)
        return 1

    text = spec_path.read_text(encoding="utf-8")

    # --- Frontmatter ---
    fm = lb.parse_frontmatter(text) or {}
    status   = fm.get("status", "?")
    step     = fm.get("step") or "—"
    priority = fm.get("priority", "?")
    owner    = fm.get("owner", "?")

    # --- Body (after the frontmatter) ---
    body_start = text.find("\n---", 3)
    body = text[body_start + 4:] if body_start != -1 else text
    sections = split_sections(body)

    # --- Assemble the output ---
    out_lines: list[str] = []
    out_lines.append(f"=== SPEC BRIEF: {slug} ===")
    out_lines.append(f"status: {status}  step: {step}  priority: {priority}  owner: {owner}")

    attention_lines: list[str] = []

    for title, lines in sections:
        # Collect !!!ВНИМАНИЕ!!! from ## Comments
        if title in ("Comments", "Комментарии"):
            for line in lines:
                if ATTENTION_RE.search(line):
                    attention_lines.append(line.strip())
            continue

        # Checklist sections: unchecked only
        if title in CHECKLIST_SECTIONS:
            unchecked = [l for l in lines if UNCHECKED_RE.match(l)]
            if unchecked:
                out_lines.append("")
                out_lines.append(f"## {title}")
                out_lines.extend(unchecked)
            continue

        # Output / Artifacts — in full (no leading blank lines)
        if title in FULL_SECTIONS:
            content = [l for l in lines if l.strip()]
            if content:
                out_lines.append("")
                out_lines.append(f"## {title}")
                out_lines.extend(content)
            continue

    # !!!ВНИМАНИЕ!!! — at the end
    if attention_lines:
        out_lines.append("")
        out_lines.append("## !!!ВНИМАНИЕ!!!")
        out_lines.extend(attention_lines)

    out_lines.append("===")
    print("\n".join(out_lines))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="Workspace root ($WORKSPACE_ROOT)")
    ap.add_argument("slug", help="Task spec slug")
    args = ap.parse_args()
    return print_spec_brief(args.workspace, args.slug)


if __name__ == "__main__":
    sys.exit(main())
