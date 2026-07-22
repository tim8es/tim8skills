"""check.py — combined sync+lint in a single call.

Runs sync_properties.py → lint_board.py and prints a combined report.
Returns exit code 1 if ANY of the stages fails (sync OR lint).

--slug is required: check.py is intended to check a single spec in the role cycle §9.
For a full workspace scan use `kanban.py lint "."`.
Without --slug, an actionable hint is printed (exit 2), not a raw argparse error.

Usage:
    python scripts/check.py "$WORKSPACE_ROOT" --slug <slug>
"""

import argparse
import subprocess
import sys
from pathlib import Path

# Windows: without this reconfiguration, sys.stdout/stderr fall back to cp1251 outside a real
# console context (redirect/pipe/automation), producing mojibake on --help and
# on error paths (e.g. the sync_rc != 0 warning below) — the same protection
# already present in all the other scripts/ scripts (found during dogfooding 2026-07-05:
# check.py turned out to be the only one without it).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run(cmd: list[str]) -> tuple[int, bytes]:
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        msg = f"✗ command exceeded the 30s timeout: {' '.join(cmd)}".encode("utf-8")
        return 1, msg
    except (OSError, FileNotFoundError) as exc:
        msg = f"✗ failed to run command {' '.join(cmd)}: {exc}".encode("utf-8")
        return 1, msg
    out = (result.stdout + result.stderr).rstrip()
    return result.returncode, out


def main() -> int:
    # prog = user-facing facade name, not the internal module: the dispatcher
    # (kanban.py) rewrites argv[0] to "check.py", so without this override every
    # argparse error/--help would leak the internal module name and break the
    # single-facade abstraction the agent is told to use (dogfooding 2026-07-09).
    ap = argparse.ArgumentParser(
        prog="kanban.py check",
        description="check.py — sync_properties + lint_board in one call. --slug is required.",
    )
    ap.add_argument("workspace", help="Workspace root ($WORKSPACE_ROOT)")
    ap.add_argument(
        "--slug",
        metavar="SLUG",
        help="Spec to check (required argument — a full scan is not allowed)",
    )
    args = ap.parse_args()

    # --slug is required, but we validate it manually (not via required=True) to
    # emit an actionable message with a path forward instead of a raw argparse
    # error: check is per-spec; a full-workspace scan is a different command (lint).
    if not args.slug:
        sys.stderr.write(
            "✗ check requires --slug: it checks ONE spec in the role cycle §9.\n"
            "  • One spec:        python <SCRIPT_PREFIX>/kanban.py check \".\" --slug <slug>\n"
            "  • Whole workspace: python <SCRIPT_PREFIX>/kanban.py lint \".\"\n"
        )
        return 2

    scripts_dir = Path(__file__).parent
    py = sys.executable

    sync_cmd = [py, str(scripts_dir / "sync_properties.py"), args.workspace, "--slug", args.slug]
    lint_cmd = [py, str(scripts_dir / "lint_board.py"), args.workspace, "--slug", args.slug]

    sync_rc, sync_out = run(sync_cmd)
    lint_rc, lint_out = run(lint_cmd)

    sys.stdout.buffer.write(sync_out + b"\n\n" + lint_out + b"\n")

    if sync_rc != 0:
        sys.stderr.write(f"\n⚠ sync_properties exited with code {sync_rc} — sync was not performed.\n")

    # exit≠0 if ANY stage fails: otherwise a sync failure goes unnoticed
    # and the agent in the role cycle §9 continues the transition, assuming sync succeeded.
    return 1 if (lint_rc or sync_rc) else 0


if __name__ == "__main__":
    sys.exit(main())
