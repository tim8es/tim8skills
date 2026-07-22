#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_reminders.py — finds tasks with a reminder due today.

Run automatically by the agent during onboarding (SKILL.md §3).

Formats of the `reminder` field in the spec YAML:
  reminder: YYYY-MM-DD          — one-off (fires exactly on this date)
  reminder: weekly:mon          — every Monday (mon/tue/wed/thu/fri/sat/sun)
  reminder: monthly:15          — every 15th of the month
  reminder: daily               — every day
  reminder: null  (or the field is absent) — no reminder set

Usage:
    python scripts/check_reminders.py <WORKSPACE_ROOT>
    python scripts/check_reminders.py <WORKSPACE_ROOT> --date 2026-06-09   # for tests

Exit codes:
    0 — no problems
    2 — at least one problem the agent must show the user:
        a triggered reminder ∪ a task with no activity in UAT ≥ 2 days
        ∪ an active-column overflow (>10) ∪ a DONE overflow

After a one-off reminder fires, the agent asks the user:
"The reminder fired — remove it or move it to a new date?"
and updates the reminder field via the script: `kanban.py tags "." <slug> --reminder <DATE|none>`
(`none` clears it to null). Do not edit the YAML manually — the mutation is deterministic.
"""

from __future__ import annotations

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import datetime as dt
import re
import shutil
from pathlib import Path

import kanban_utils as ku
import lint_board as lb

WEEKDAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEEKLY_RE = re.compile(r"^weekly:(mon|tue|wed|thu|fri|sat|sun)$")
MONTHLY_RE = re.compile(r"^monthly:([1-9]|[12]\d|3[01])$")

ACTIVE_COLUMNS = {"BACKLOG", "TODO", "IN PROGRESS", "BLOCKED", "TESTING", "IN REVIEW", "UAT", "REWORK"}
OVERFLOW_THRESHOLD = 10
DONE_OVERFLOW_THRESHOLD = 10


def is_due(reminder: str, today: dt.date) -> bool:
    """Returns True if the reminder is due today."""
    if not reminder or reminder == "null":
        return False
    if reminder == "daily":
        return True
    if DATE_RE.match(reminder):
        try:
            return dt.date.fromisoformat(reminder) == today
        except ValueError:
            return False
    m = WEEKLY_RE.match(reminder)
    if m:
        return today.weekday() == WEEKDAY_MAP[m.group(1)]
    m = MONTHLY_RE.match(reminder)
    if m:
        return today.day == int(m.group(1))
    return False


def check_overflow(tasks_dir: Path) -> list[tuple[str, str, int]]:
    """Finds ACTIVE (non-DONE) board columns with more than OVERFLOW_THRESHOLD cards."""
    overflows = []
    for slug, counts in ku.board_column_counts(tasks_dir).items():
        for col, count in counts.items():
            if col in ACTIVE_COLUMNS and count > OVERFLOW_THRESHOLD:
                overflows.append((slug, col, count))
    return overflows


def check_done_overflow(tasks_dir: Path) -> list[tuple[str, int]]:
    """Finds boards where DONE column exceeds DONE_OVERFLOW_THRESHOLD cards."""
    overflows = []
    for slug, counts in ku.board_column_counts(tasks_dir).items():
        done_count = counts.get("DONE", 0)
        if done_count > DONE_OVERFLOW_THRESHOLD:
            overflows.append((slug, done_count))
    return overflows


def check_stale_uat(specs_dir: Path, today: dt.date, threshold_days: int = 2) -> list[tuple[str, str, int]]:
    """Returns (slug, title, days_stale) for status=uat specs with no activity
    (updatedAt) for >= threshold_days (fires on the threshold day and later)."""
    stale = []
    for md in sorted(specs_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = lb.parse_frontmatter(text) or {}
        if fm.get("status") != "uat":
            continue
        # Staleness is measured from last activity (updatedAt), not column-entry:
        # updatedAt is bumped by any spec mutation, so a UAT card touched recently
        # is (correctly) not flagged. There is no `uatAt` field — nothing writes it.
        date_str = fm.get("updatedAt", "")
        if not date_str or not DATE_RE.match(date_str[:10]):
            continue
        try:
            entered = dt.date.fromisoformat(date_str[:10])
        except ValueError:
            continue
        days = (today - entered).days
        if days >= threshold_days:
            title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), md.stem)
            stale.append((md.stem, title, days))
    return stale


def board_summary(tasks_dir: Path) -> dict:
    """Returns {board_slug: {column: count}} for all non-archive boards in tasks_dir."""
    return ku.board_column_counts(tasks_dir)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("--date", help="Check date YYYY-MM-DD (default: today)")
    args = ap.parse_args()

    if args.date:
        try:
            today = dt.date.fromisoformat(args.date)
        except ValueError:
            print(f"✗ Invalid date format: {args.date}", file=sys.stderr)
            return 1
    else:
        today = dt.date.today()

    root = Path(args.workspace).expanduser()
    prefix = ku.detect_script_prefix(root)
    tasks = root if root.name == "tasks" else root / "tasks"
    specs_dir = tasks / "specs"

    if not specs_dir.is_dir():
        return 0  # no specs/ — no reminders

    due: list[tuple[str, str, str, str]] = []  # (slug, title, status, reminder)

    for md in sorted(specs_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = lb.parse_frontmatter(text) or {}
        reminder = fm.get("reminder", "")
        if not reminder or reminder == "null":
            continue
        if is_due(reminder, today):
            # extract the task title from the first H1 line
            title = ""
            for line in text.splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            due.append((md.stem, title, fm.get("status", "?"), reminder))

    has_issues = False

    if due:
        has_issues = True
        print(f"\n  🔔 Reminders for {today} ({len(due)}):\n")
        for slug, title, status, reminder in due:
            print(f"  • [[{slug}]] ({status})  —  {title or slug}")
            print(f"      reminder: {reminder}")
        print()
    else:
        print(f"  No reminders for {today}.")

    stale_uat = check_stale_uat(specs_dir, today)
    if stale_uat:
        has_issues = True
        print(f"\n  ⏰ Tasks stuck in UAT ({len(stale_uat)}):\n")
        for slug, title, days in stale_uat:
            print(f"  • [[{slug}]] — {title or slug}")
            print(f"      In UAT for {days} days already. Needs a user decision: "
                  f"accept (move DONE) or reject (move REJECTED).")
        print()

    overflows = check_overflow(tasks)
    if overflows:
        has_issues = True
        print(f"\n  ⚠ Active column overflow ({len(overflows)}):\n")
        for board_name, col, cnt in overflows:
            print(f"  • {board_name}.md → {col}: {cnt} tasks (>{OVERFLOW_THRESHOLD})")
            print(f"      Recommended: move the excess tasks to ICEBOX: "
                  f"python {prefix}kanban.py move \".\" <slug> ICEBOX")
        print()

    done_overflows = check_done_overflow(tasks)
    if done_overflows:
        has_issues = True
        print(f"\n  ⚠ DONE overflow ({len(done_overflows)} boards):\n")
        for board_name, cnt in done_overflows:
            print(f"  • {board_name}.md → DONE: {cnt} tasks (>{DONE_OVERFLOW_THRESHOLD})")
            print(f"      Recommended: python {prefix}kanban.py archive \".\" {board_name}")
        print()

    # Board summary — a compact overview for the agent, avoids manually reading board files
    summary = board_summary(tasks)
    if summary:
        print()
        for board_slug, counts in summary.items():
            parts = [f"{col} {cnt}" for col in ku.COLUMN_ORDER
                     if (cnt := counts.get(col, 0)) > 0]
            if parts:
                print(f"  📋 {board_slug}: {' · '.join(parts)}")

    # Next task: injected into the agent's context during onboarding
    prefix = ku.detect_script_prefix(root)
    next_task = ku.find_next_task(tasks)
    print(ku.format_next_task(next_task, script_prefix=prefix))

    # Dashboard sync: overwrite tasks/kanban-dashboard.html from assets/
    # on every onboarding, so the user always has the up-to-date version.
    assets_dashboard = Path(__file__).parent.parent / "assets" / "kanban-dashboard.html"
    tasks_dashboard = tasks / "kanban-dashboard.html"
    if assets_dashboard.is_file():
        shutil.copy2(assets_dashboard, tasks_dashboard)
        print(f"  ✅ Dashboard synced: assets/kanban-dashboard.html → tasks/kanban-dashboard.html")

    return 2 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
