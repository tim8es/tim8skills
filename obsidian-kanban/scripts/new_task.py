#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""new_task.py — task/subtask spec scaffolder.

Creating a spec is the only unscripted workspace mutation and the most fragile one:
14 YAML fields, a 3-part flowId, a canonical set of sections. It used to all be written
by hand, with errors caught only by post-hoc lint. This script generates the spec from a template
(templates/task.md, §6) and stamps createdAt/updatedAt with system time — the model
no longer writes dates by hand (it doesn't know "today").

The project for flowId is taken from the name of the single board in tasks/ (or --board).
YAML is assembled via sync_properties.render_frontmatter (single field order §8),
sections via kanban_utils.build_spec_text (shared code with new_epic.py).

Usage:
    python scripts/new_task.py <WORKSPACE_ROOT> <slug> "<TAG: Title>" [options]

Options:
    --epic <slug>            parentId (parent epic slug); default null
    --subtask                itemType: subtask instead of task (usually together with --epic)
    --priority high|medium|low   priority (default medium)
    --owner <role|user>      task author; default analyst (agent workflow)
    --card                   immediately add the card to BACKLOG (add_card.py)
    --column <COLUMN>        target column with --card (default BACKLOG)
    --board <name.md>        board file name, if there are several in tasks/
    --dry-run                show the spec without writing

Exit codes: 0 — created/simulated; 1 — error (duplicate slug, board not found/
ambiguous, add_card error with --card).
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
from pathlib import Path

import lint_board as lb      # resolve_tasks_dir
import kanban_utils as ku    # scaffold_spec


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("slug", help="task slug (spec file name without .md)")
    ap.add_argument("name", help="display name with a category tag, e.g. 'DEV: Title'")
    ap.add_argument("--epic", default=None, help="parent epic slug (parentId)")
    ap.add_argument("--subtask", action="store_true", help="itemType: subtask instead of task")
    ap.add_argument("--priority", default="medium", choices=["high", "medium", "low"],
                    help="priority (default medium)")
    ap.add_argument("--owner", default="analyst",
                    help="task author: agent role or user (default analyst)")
    ap.add_argument("--card", action="store_true", help="add the card to BACKLOG")
    ap.add_argument("--column", default="BACKLOG", help="target column with --card (default BACKLOG)")
    ap.add_argument("--board", default=None, help="board file name, if there are several")
    ap.add_argument("--dry-run", action="store_true", help="show the spec without writing")
    args = ap.parse_args()

    tasks = lb.resolve_tasks_dir(Path(args.workspace).expanduser())
    if not tasks.is_dir():
        print(f"✗ tasks/ folder not found: {tasks}", file=sys.stderr)
        return 1
    if args.owner not in lb.VALID_OWNER:
        print(f"✗ Invalid owner: {args.owner!r}. "
              f"Valid: {', '.join(sorted(lb.VALID_OWNER))}", file=sys.stderr)
        return 1

    item_type = "subtask" if args.subtask else "task"
    rc, msg = ku.scaffold_spec(
        tasks, item_type, args.slug, args.name, priority=args.priority,
        parent=args.epic, board_hint=args.board, card=args.card,
        column=args.column, owner=args.owner, dry_run=args.dry_run)
    print(msg, file=sys.stderr if rc else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main())
