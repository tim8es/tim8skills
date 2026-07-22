#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""new_epic.py — epic spec scaffolder.

Generates an epic spec from a template (templates/epic.md, §6): a full YAML block
(itemType: epic, status: backlog, owner: analyst, parentId: null) with
createdAt/updatedAt stamped with system time, and a canonical set of sections
(Goal, Context, DoD, Tasks, Dependencies, Risks, Review Checklist, Changelog, Comments).

The project for flowId is taken from the name of the single board in tasks/ (or --board).
Shared code with new_task.py — kanban_utils.scaffold_spec / build_spec_text.

Usage:
    python scripts/new_epic.py <WORKSPACE_ROOT> <slug> "<TAG: Title>" [options]

Options:
    --priority high|medium|low   priority (default medium)
    --card                   immediately add the card to BACKLOG (add_card.py)
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
    ap.add_argument("slug", help="epic slug (spec file name without .md)")
    ap.add_argument("name", help="display name with a category tag, e.g. 'DEV: Title'")
    ap.add_argument("--priority", default="medium", choices=["high", "medium", "low"],
                    help="priority (default medium)")
    ap.add_argument("--card", action="store_true", help="add the card to BACKLOG")
    ap.add_argument("--board", default=None, help="board file name, if there are several")
    ap.add_argument("--dry-run", action="store_true", help="show the spec without writing")
    args = ap.parse_args()

    tasks = lb.resolve_tasks_dir(Path(args.workspace).expanduser())
    if not tasks.is_dir():
        print(f"✗ tasks/ folder not found: {tasks}", file=sys.stderr)
        return 1

    rc, msg = ku.scaffold_spec(
        tasks, "epic", args.slug, args.name, priority=args.priority,
        parent=None, board_hint=args.board, card=args.card, dry_run=args.dry_run)
    print(msg, file=sys.stderr if rc else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main())
