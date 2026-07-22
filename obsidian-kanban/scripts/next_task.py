#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""next_task.py — prints the next task by priority (REWORK→TODO→BACKLOG).

Scans all boards in REWORK, then TODO, then BACKLOG and prints the card with the
highest priority. Always exits 0 (an empty queue is not an error).

Usage:
    python scripts/next_task.py <WORKSPACE_ROOT> [options]
    python <SCRIPT_PREFIX>/kanban.py next <WORKSPACE_ROOT> [options]

Options:
    --json      output as JSON instead of human-readable text

Exit codes: 0 — always (task found or the queue is empty); 1 — read error.
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import json
from pathlib import Path

import kanban_utils as ku
import lint_board as lb
import workflow as wf


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT")
    ap.add_argument("--json", action="store_true", help="output as JSON")
    args = ap.parse_args()

    tasks = lb.resolve_tasks_dir(Path(args.workspace).expanduser())
    if not tasks.is_dir():
        print(f"✗ tasks/ folder not found: {tasks}", file=sys.stderr)
        return 1

    task = wf.find_next_task(tasks)

    if args.json:
        print(json.dumps(task or {}, ensure_ascii=False))
    else:
        script_prefix = ku.detect_script_prefix(Path(args.workspace).expanduser())
        print(wf.format_next_task(task, script_prefix=script_prefix))

    return 0


if __name__ == "__main__":
    sys.exit(main())
