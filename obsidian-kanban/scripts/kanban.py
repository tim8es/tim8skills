#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kanban.py — single entry point (dispatcher) for all skill operations.

    python <SCRIPT_PREFIX>/kanban.py <command> <arguments...>

Why: a single `--help`, a single source of command documentation (less surface for drift).
Each <command> delegates to the corresponding module's main() — behavior and arguments are identical to a direct run.

Commands (→ module):
    setup        → setup            new-task   → new_task
    new-epic     → new_epic         add-card   → add_card
    remove-card  → remove_card      move       → move_card
    tags         → set_card_tags    set-type   → set_item_type
    step         → set_step         check-item → check_item
    comment      → add_comment      check      → check
    lint         → lint_board       sync       → sync_properties
    reminders    → check_reminders  archive    → archive_done
    resume       → resume (read-only packet, --full-checklist / --brief)
    metrics      → loop_metrics     update     → update (batch of spec mutations in 1 call)
    next         → next_task

Usage:
    python <SCRIPT_PREFIX>/kanban.py <command> [arguments...]
    python <SCRIPT_PREFIX>/kanban.py <command> --help    # help for the command
    python <SCRIPT_PREFIX>/kanban.py --help              # this list

Exit codes: proxied from the called command; 2 — unknown command.
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import importlib

# CLI command -> module name (in the same scripts/ folder)
COMMANDS = {
    "setup": "setup",
    "new-task": "new_task",
    "new-epic": "new_epic",
    "add-card": "add_card",
    "remove-card": "remove_card",
    "move": "move_card",
    "tags": "set_card_tags",
    "step": "set_step",
    "set-type": "set_item_type",
    "check-item": "check_item",
    "comment": "add_comment",
    "update": "update",
    "check": "check",
    "lint": "lint_board",
    "sync": "sync_properties",
    "reminders": "check_reminders",
    "archive": "archive_done",
    "resume": "resume",
    "metrics": "loop_metrics",
    "next": "next_task",
}


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0

    cmd = argv[0]
    module_name = COMMANDS.get(cmd)
    if module_name is None:
        print(f"✗ Unknown command: {cmd!r}. Available: {', '.join(COMMANDS)}",
              file=sys.stderr)
        return 2

    module = importlib.import_module(module_name)
    # Rewrite argv as if the module itself were run: argv[0] = script name (for prog
    # in its argparse), followed by the command's arguments. The module's main() works unchanged.
    sys.argv = [f"{module_name}.py"] + argv[1:]
    rc = module.main()
    return rc if isinstance(rc, int) else 0


if __name__ == "__main__":
    sys.exit(main())
