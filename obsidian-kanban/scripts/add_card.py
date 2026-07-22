#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""add_card.py — deterministic card addition to the board.

Replaces manual board editing when creating a task (§9 → "Add a
card to BACKLOG"). Manual editing is a source of format errors (orphaned
tag lines, broken indentation, duplicates). The script assembles a correct card
block (`- [ ] [[slug|Title]]` line + tab-prefixed tags line) and inserts it into the
target column, then rebuilds the board in the canonical format (§6).

Format, COLUMN_TO_STATUS, parser, and serializer are reused from move_card.py /
lint_board.py (single source of truth for the board format). No dependencies (stdlib).

Default tags line: `➕ <today>` (creation date). Overridden via
--tags. The checkbox is set to `[x]` only if the column is DONE, otherwise `[ ]`.

Usage:
    python scripts/add_card.py <WORKSPACE_ROOT> <slug> "<TAG: Title>" [options]

Options:
    --column <COLUMN>   target column (default BACKLOG)
    --tags "<string>"   tags string without a tab (default `➕ <today>`)
    --board <name.md>   board file name, if there are several boards in tasks/
    --dry-run           show the result without writing

Exit codes: 0 — added/simulated; 1 — error (duplicate slug, unknown
column, board not found/ambiguous).
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import datetime as dt
from pathlib import Path

import lint_board as lb      # shared COLUMN_TO_STATUS, COLUMN_ORDER, CARD_RE, resolve_tasks_dir
import move_card as mc       # shared parse_board / emit_board / set_checkbox / card_slug
import kanban_utils as ku    # resolve_board

COLUMN_TO_STATUS = lb.COLUMN_TO_STATUS
COLUMN_ORDER = lb.COLUMN_ORDER


def slug_on_board(cols: dict, slug: str) -> str | None:
    for c in COLUMN_ORDER:
        for b in cols[c]:
            if mc.card_slug(b) == slug:
                return c
    return None


def add_card_to_board(tasks: Path, slug: str, name: str, *, column: str = "BACKLOG",
                      tags: str | None = None, board_hint: str | None = None,
                      dry_run: bool = False) -> tuple[int, str]:
    """Adds a card to the board in the canonical format. Returns (rc, message).

    rc=0 — added/simulated; rc=1 — error (text in message). Reused by
    new_task.py/new_epic.py (the --card flag), which is why the logic is factored out of main()."""
    column = ku.normalize_column(column)
    if column not in COLUMN_TO_STATUS:
        return 1, (f"✗ Unknown column: {column!r}. "
                   f"Valid: {', '.join(COLUMN_ORDER)}")
    board_file, err = ku.resolve_single_board(tasks, board_hint)
    if err:
        return 1, err
    if tags is not None:
        tag_str = tags
    else:
        tag_str = f"➕ {dt.date.today().isoformat()}"
        if column == "DONE":
            tag_str += f" ✅ {ku.now_stamp()}"
    checkbox = "x" if column == "DONE" else " "
    block = [f"- [{checkbox}] [[{slug}|{name}]]", f"\t{tag_str}"]

    def transform(cols, settings):
        existing = slug_on_board(cols, slug)
        if existing:
            raise ku.MutationError(f"✗ Card [[{slug}]] already on the board (column {existing}). "
                                   f"Use move_card.py to move it.")
        cols[column].append(block)
        return cols, f"Added: [[{slug}]] → {column} ({board_file.name}); tags: {tag_str}"

    return ku.mutate_board(tasks, board_file, transform, dry_run=dry_run)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("slug", help="card slug (without [[]])")
    ap.add_argument("name", help="display name with a category tag, e.g. 'FIX: Title'")
    ap.add_argument("--column", default="BACKLOG", help="target column (default BACKLOG)")
    ap.add_argument("--tags", default=None, help="tags string without a tab; default `➕ <today>`")
    ap.add_argument("--board", default=None, help="board file name, if there are several")
    ap.add_argument("--dry-run", action="store_true", help="show the result without writing")
    args = ap.parse_args()

    tasks = lb.resolve_tasks_dir(Path(args.workspace).expanduser())
    if not tasks.is_dir():
        print(f"✗ tasks/ folder not found: {tasks}", file=sys.stderr)
        return 1

    rc, msg = add_card_to_board(
        tasks, args.slug, args.name, column=args.column, tags=args.tags,
        board_hint=args.board, dry_run=args.dry_run)
    print(msg, file=sys.stderr if rc else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main())
