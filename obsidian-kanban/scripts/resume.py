#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""resume.py — read-only context packet for an active kanban task.

Usage:
    python <SCRIPT_PREFIX>/kanban.py resume <WORKSPACE_ROOT> [slug] [--board BOARD]
    python <SCRIPT_PREFIX>/kanban.py resume <WORKSPACE_ROOT> [slug] --full-checklist
    python <SCRIPT_PREFIX>/kanban.py resume <WORKSPACE_ROOT> [slug] --brief

Without slug, the command requires exactly one active task in IN PROGRESS,
REWORK, TESTING, IN REVIEW, UAT, or BLOCKED. It never writes board/spec files.

This is the single context-recovery entry point: an agent that lost context
(dropped session, truncated stdout, resumed conversation) reaches for `resume`
and picks the flag matching how much detail it needs:
    (no flag)          — compact read-only packet (this module's own format)
    --full-checklist   — full role checklist for the task's column
    --brief            — compact spec summary

The checklist/brief rendering logic lives in `role_prompt.print_role_checklist()`
and `spec_brief.print_spec_brief()`; this module calls them directly so there is
exactly one code path per flag.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import hooks
import kanban_utils as ku
import lint_board as lb
import role_prompt
import spec_brief
from move_card import card_slug, card_title
from workflow import find_next_task, format_next_task

ACTIVE_COLUMNS = ["IN PROGRESS", "REWORK", "TESTING", "IN REVIEW", "UAT", "BLOCKED"]


@dataclass(frozen=True)
class ActiveTask:
    slug: str
    title: str | None
    column: str
    board: Path


def iter_cards(tasks: Path, board_hint: str | None = None):
    boards = ku.find_boards(tasks)
    if board_hint:
        board, err = ku.resolve_single_board(tasks, board_hint)
        if err:
            raise ValueError(err)
        boards = [board]
    for board in boards:
        text = board.read_text(encoding="utf-8", errors="replace")
        cols, _ = ku.parse_board(text)
        for column in ku.COLUMN_ORDER:
            for block in cols.get(column, []):
                slug = card_slug(block)
                if not slug:
                    continue
                yield ActiveTask(slug=slug, title=card_title(block), column=column, board=board)


def find_card(tasks: Path, slug: str, board_hint: str | None = None) -> ActiveTask | None:
    matches = [task for task in iter_cards(tasks, board_hint) if task.slug == slug]
    if not matches:
        return None
    if len(matches) > 1:
        boards = ", ".join(sorted(task.board.name for task in matches))
        raise ValueError(f"Slug {slug!r} found on multiple boards: {boards}. Pass --board.")
    return matches[0]


def find_single_active_task(tasks: Path, board_hint: str | None = None) -> ActiveTask:
    active = [task for task in iter_cards(tasks, board_hint) if task.column in ACTIVE_COLUMNS]
    if not active:
        raise ValueError("No active task found. Pass a slug or move one task into an active column.")
    if len(active) > 1:
        rows = "; ".join(f"{task.slug} ({task.column}, {task.board.name})" for task in active)
        raise ValueError(f"Multiple active tasks found: {rows}. Pass an explicit slug.")
    return active[0]


def build_packet(tasks: Path, task: ActiveTask) -> str:
    role = ku.role_for_column(task.column, task.title)
    return hooks.on_resume(tasks, task.slug, task.column, title=task.title, role=role)


def main() -> int:
    ap = argparse.ArgumentParser(description="Print a read-only resume packet for a kanban task.")
    ap.add_argument("workspace", help="Workspace root or tasks/ directory")
    ap.add_argument("slug", nargs="?", help="Task slug. Omit only when exactly one active task exists.")
    ap.add_argument("--board", help="Board filename/stem when workspace has multiple boards")
    ap.add_argument("--full-checklist", action="store_true",
                    help="Print the full role checklist for the task's column")
    ap.add_argument("--brief", action="store_true",
                    help="Print a compact spec brief for the task")
    args = ap.parse_args()

    workspace = Path(args.workspace).expanduser()
    tasks = lb.resolve_tasks_dir(workspace)
    if not tasks.is_dir():
        print(f"✗ tasks/ folder not found: {tasks}", file=sys.stderr)
        return 1

    try:
        if args.slug:
            task = find_card(tasks, args.slug, args.board)
            if task is None:
                print(f"✗ Card not found: {args.slug}", file=sys.stderr)
                return 1
        else:
            try:
                task = find_single_active_task(tasks, args.board)
            except ValueError as exc:
                msg = str(exc)
                if msg.startswith("No active task"):
                    # Queue idle — show next available task instead of erroring
                    prefix = ku.detect_script_prefix(workspace)
                    print(format_next_task(find_next_task(tasks), script_prefix=prefix))
                    return 0
                raise

        if args.full_checklist:
            return role_prompt.print_role_checklist(workspace, task.column, title=task.title)
        if args.brief:
            return spec_brief.print_spec_brief(workspace, task.slug)

        print(build_packet(tasks, task).rstrip())
        return 0
    except ValueError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
