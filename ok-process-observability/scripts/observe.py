"""Dispatcher for the process-observability skill.

Usage:
    python .agents/skills/process-observability/scripts/observe.py metrics "." [--board X.md | --project Y]

All commands are read-only over the kanban tasks/ workspace.
"""

from __future__ import annotations

import sys

import context_metrics

COMMANDS = {
    "metrics": context_metrics.main,
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__.strip())
        print("\nCommands: " + ", ".join(sorted(COMMANDS)))
        return 0
    cmd, rest = argv[0], argv[1:]
    handler = COMMANDS.get(cmd)
    if handler is None:
        print(f"ERROR: unknown command '{cmd}'. Commands: {', '.join(sorted(COMMANDS))}", file=sys.stderr)
        return 2
    return handler(rest)


if __name__ == "__main__":
    sys.exit(main())
