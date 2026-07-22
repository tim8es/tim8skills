#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""archive_done.py — archives old DONE tasks to a separate board.

When the DONE column overflows (>N tasks), moves the oldest cards
to the archive board `tasks/<board>-archive.md`, preserving the Obsidian Kanban format.

Algorithm:
  1. Reads the main board `tasks/<board>.md`.
  2. Sorts DONE cards by completion date ✅ (newest first).
  3. Keeps the first `--keep` cards on the main board.
  4. Moves the rest to `tasks/<board>-archive.md` (creates it if missing).
  5. Rewrites both files.

Usage:
    python scripts/archive_done.py <WORKSPACE_ROOT> <board-slug> [--keep N] [--dry-run]
    Example: python scripts/archive_done.py "." claude-obsidian-kanban --keep 10

Exit codes: 0 — success; 1 — error.
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
import kanban_utils as ku

COLUMN_ORDER = ku.COLUMN_ORDER
WIKILINK_RE = ku.WIKILINK_RE
SETTINGS_DEFAULT = ku.SETTINGS_DEFAULT
parse_board = ku.parse_board
emit_board = ku.emit_board
done_sort_key = ku.done_sort_key


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("board", help="main board slug (without .md)")
    ap.add_argument("--keep", type=int, default=10,
                    help="how many cards to keep in DONE on the main board (default: 10)")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would be done without writing files")
    args = ap.parse_args()

    root = Path(args.workspace).expanduser()
    tasks = lb.resolve_tasks_dir(root)
    board_file = tasks / f"{args.board}.md"
    archive_file = tasks / f"{args.board}-archive.md"

    if not board_file.is_file():
        print(f"✗ Board not found: {board_file}", file=sys.stderr)
        return 1

    text = board_file.read_text(encoding="utf-8")
    if "kanban-plugin: board" not in text:
        print(f"✗ File is not a Kanban board: {board_file}", file=sys.stderr)
        return 1

    cols, settings = parse_board(text)

    # sort DONE by completion date (newest first)
    done_cards = sorted(cols["DONE"], key=done_sort_key, reverse=True)
    keep = max(0, args.keep)

    to_keep = done_cards[:keep]
    to_archive = done_cards[keep:]

    if not to_archive:
        print(f"ⓘ DONE has {len(done_cards)} tasks — archiving not needed (threshold: {keep}).")
        return 0

    print(f"  Board: {board_file.name}")
    print(f"  DONE: {len(done_cards)} tasks → keep {len(to_keep)}, archive {len(to_archive)}")

    if args.dry_run:
        print("\n[dry-run] Cards to archive:")
        for b in to_archive:
            slug = None
            if b and (mm := WIKILINK_RE.search(b[0])):
                slug = mm.group(1)
            print(f"  - [[{slug}]]" if slug else f"  - {b[0][:60]}")
        return 0

    with ku.board_lock(tasks):
        # update / create the archive
        if archive_file.is_file():
            arch_text = archive_file.read_text(encoding="utf-8")
            if "kanban-plugin: board" in arch_text:
                arch_cols, arch_settings = parse_board(arch_text)
            else:
                arch_cols = {c: [] for c in COLUMN_ORDER}
                arch_settings = SETTINGS_DEFAULT
        else:
            arch_cols = {c: [] for c in COLUMN_ORDER}
            arch_settings = SETTINGS_DEFAULT

        # add the archived cards to the archive's DONE (already sorted)
        arch_cols["DONE"] = sorted(
            arch_cols["DONE"] + to_archive, key=done_sort_key, reverse=True)
        # write the archive FIRST: an interruption between writes must not lose cards —
        # if the main board isn't rewritten, the cards will remain duplicated
        # (in main's DONE + in the archive), but won't disappear without a trace.
        ku._fsync_write(archive_file, emit_board(arch_cols, arch_settings))

        # update the main board
        cols["DONE"] = to_keep
        ku._fsync_write(board_file, emit_board(cols, settings))

    print(f"✅ Main board: {len(to_keep)} tasks remaining in DONE")
    print(f"✅ Archive: {archive_file.name} — {len(arch_cols['DONE'])} tasks in DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
