#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""remove_card.py — deterministic card removal from the board.

Removes the card line and the tags line from the given board under board_lock.
Does not remove the spec — only the card from the board. If the spec exists, prints a WARNING.

Usage:
    python scripts/remove_card.py <WORKSPACE_ROOT> <slug> [options]

Options:
    --board <name.md>   board file name, if there are several boards in tasks/
    --dry-run           show the result without writing

Exit codes: 0 — removed/simulated; 1 — error (card not found,
board not found/ambiguous).
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
from pathlib import Path

import lint_board as lb
import move_card as mc
import kanban_utils as ku

COLUMN_ORDER = lb.COLUMN_ORDER


def remove_card_from_board(tasks: Path, slug: str, *, board_hint: str | None = None,
                           dry_run: bool = False) -> tuple[int, str]:
    """Removes the card from the board. Returns (rc, message)."""
    board_file, err = ku.resolve_single_board(tasks, board_hint)
    if err:
        return 1, err

    spec_path = tasks / "specs" / f"{slug}.md"
    has_spec = spec_path.exists()

    def transform(cols, settings):
        for col in COLUMN_ORDER:
            for i, block in enumerate(cols[col]):
                if mc.card_slug(block) == slug:
                    cols[col].pop(i)
                    msg = f"✅ Card [[{slug}]] removed from the board ({board_file.name}, column {col})"
                    if has_spec:
                        msg += f"\n⚠️  WARNING: spec tasks/specs/{slug}.md exists — remove it manually if needed"
                    return cols, msg
        raise ku.MutationError(f"✗ Card [[{slug}]] not found in any column of board {board_file.name}")

    return ku.mutate_board(tasks, board_file, transform, dry_run=dry_run)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("slug", help="card slug (without [[]])")
    ap.add_argument("--board", default=None, help="board file name, if there are several")
    ap.add_argument("--dry-run", action="store_true", help="show the result without writing")
    args = ap.parse_args()

    tasks = lb.resolve_tasks_dir(Path(args.workspace).expanduser())
    if not tasks.is_dir():
        print(f"✗ tasks/ folder not found: {tasks}", file=sys.stderr)
        return 1

    rc, msg = remove_card_from_board(tasks, args.slug, board_hint=args.board, dry_run=args.dry_run)
    print(msg, file=sys.stderr if rc else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main())
