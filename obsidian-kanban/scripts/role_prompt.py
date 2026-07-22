#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""role_prompt.py — standalone role checklist injector (adapter-agnostic).

The recommended entry point for an agent is `kanban.py resume <WORKSPACE_ROOT> [slug]
--full-checklist`, which calls `print_role_checklist()` below directly (the
same code, a single render path). This module holds the checklist formatting
logic itself; its own CLI (`main()`) is kept for a direct point call outside
the `kanban.py` dispatcher.

Prints the role checklist for the given column — the same output that `move_card.py`
gives after moving a card. Used by external adapters (Linear, Trello, GitHub
Projects, etc.), where the card move is done via an MCP tool rather than
`move_card.py`. Allows following the §9 role cycle (hard stop) with any
PM tool, without rewriting a single line of business logic.

Usage (after any card move via an external adapter):
    python <SCRIPT_PREFIX>/role_prompt.py <WORKSPACE_ROOT> <COLUMN> [--title "RESEARCH: ..."]

COLUMN: BACKLOG | ICEBOX | TODO | IN PROGRESS | BLOCKED | TESTING | IN REVIEW |
        REJECTED | REWORK | DONE
Shell-safe aliases: IN_PROGRESS, IN_REVIEW

Options:
    --title <text>   Card title — affects IN PROGRESS→RESEARCH: routing
                     (if the title starts with "RESEARCH:", routes to researcher.md)

Exit codes: 0 — checklist printed; 1 — unknown column or role file not found.
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
from pathlib import Path

import kanban_utils as ku
import lint_board as lb


# Single compaction implementation lives in workflow.compact_text (leaf module),
# exposed via kanban_utils. Aliased here so external adapters that call
# role_prompt.compact_text keep the identical behaviour without a second copy.
compact_text = ku.compact_text


def print_role_checklist(workspace: Path, column: str, title: str | None = None, compact: bool = True) -> int:
    """Render and print the full role checklist for `column` — the shared body of
    `role_prompt.py`'s CLI, called directly by both that CLI and
    `resume.py --full-checklist` so the two entry points stay byte-for-byte
    identical. Do not duplicate this logic elsewhere; extend here instead.

    Returns the process exit code (0 on success, 1 on unknown column or missing
    role file — same contract as the original `role_prompt.main()`).
    """
    raw_column = column
    column = ku.normalize_column(raw_column)
    if column not in lb.COLUMN_ORDER:
        print(
            f"✗ Unknown column: {raw_column!r}. "
            f"Valid: {', '.join(lb.COLUMN_ORDER)}",
            file=sys.stderr)
        return 1

    name, role, text = ku.role_checklist(column, title)

    if text is None:
        if role:
            print(
                f"▲ WARN: role file agents/{role}.md not found — "
                f"read the role checklist for {column} manually.",
                file=sys.stderr)
        return 1

    prefix = ku.detect_script_prefix(workspace)
    print(f"\n=== РОЛЬ: {name} ({column}) ===")
    print(f"⚙️  SCRIPT_PREFIX: {prefix}  (use it in the commands below)")
    _PLACEHOLDER = "<SCRIPT_PREFIX>/"
    _CANONICAL = "obsidian-kanban/scripts/"
    if prefix != _CANONICAL:
        text = text.replace(_CANONICAL, prefix)
    text = text.replace(_PLACEHOLDER, prefix)
    if compact:
        text = compact_text(text)
    print("Hard stop (§9): execute this checklist in full before doing anything else.\n")
    print(text.rstrip())
    print("\n=== КОНЕЦ ЧЕКЛИСТА ===")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("column", help="target column (after moving the card)")
    ap.add_argument("--title", default=None,
                    help="card title (for RESEARCH: → researcher routing)")
    ap.add_argument("--full", action="store_true",
                    help="print the full checklist text, including command blocks (by default only section headings and checklist lines are printed)")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser()
    return print_role_checklist(workspace, args.column, title=args.title, compact=not args.full)


if __name__ == "__main__":
    sys.exit(main())
