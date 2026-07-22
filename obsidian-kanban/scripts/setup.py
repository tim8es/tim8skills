"""setup.py — Obsidian Kanban workspace initialization.

Usage (from the project root):
    python obsidian-kanban/scripts/setup.py <workspace_root> <project-slug>

Example:
    python obsidian-kanban/scripts/setup.py "." my-project

Creates (if they don't already exist):
    <workspace_root>/tasks/                          — workspace directory
    <workspace_root>/tasks/specs/                    — task specs
    <workspace_root>/tasks/<project-slug>.md         — Kanban board
    <workspace_root>/tasks/kanban-dashboard.html     — web dashboard

Idempotent: re-running does not overwrite existing files.
Exit 0 — success. Exit 1 — error.
"""

import sys

# Windows: force UTF-8 so the ✅ in the final message doesn't fail with UnicodeEncodeError
# on a cp1251 console (setup.py is the first onboarding script, a traceback = a bad first impression).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import shutil
from pathlib import Path

import kanban_utils as ku


def build_board_template() -> str:
    """Canonical empty board from the single source `kanban_utils` (§6).

    Columns and `list-collapse` are taken from `COLUMN_ORDER` / `SETTINGS_DEFAULT`, so
    the board structure cannot diverge from what `lint_board.py` requires
    (previously the inline template lagged behind: `## REWORK` was missing, list-collapse had 9 values
    instead of 10 — and every new board immediately produced 2 lint ERRORs)."""
    return ku.emit_board({c: [] for c in ku.COLUMN_ORDER}, ku.SETTINGS_DEFAULT)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    slug = sys.argv[2]

    skill_dir = Path(__file__).parent.parent
    tasks_dir = root / "tasks"
    specs_dir = tasks_dir / "specs"
    board_file = tasks_dir / f"{slug}.md"
    dashboard_src = skill_dir / "assets" / "kanban-dashboard.html"
    dashboard_dst = tasks_dir / "kanban-dashboard.html"

    created = []
    skipped = []

    for d in (tasks_dir, specs_dir):
        if not d.exists():
            d.mkdir(parents=True)
            created.append(d.relative_to(root))
        else:
            skipped.append(d.relative_to(root))

    if not board_file.exists():
        board_file.write_text(build_board_template(), encoding="utf-8", newline="\n")
        created.append(board_file.relative_to(root))
    else:
        skipped.append(board_file.relative_to(root))

    if not dashboard_dst.exists():
        if dashboard_src.exists():
            shutil.copy2(dashboard_src, dashboard_dst)
            created.append(dashboard_dst.relative_to(root))
        else:
            print(f"WARNING: dashboard source not found: {dashboard_src}", file=sys.stderr)
    else:
        skipped.append(dashboard_dst.relative_to(root))

    if created:
        print(f"Created ({len(created)}):")
        for p in created:
            print(f"  + {p}")
    if skipped:
        print(f"Already exist (skipped): {', '.join(str(p) for p in skipped)}")

    print(f"\n✅ Workspace ready.")
    print(f"   Root:  {root}")
    print(f"   Board: tasks/{slug}.md")
    print(f"\nNext step:")
    print(f"   python {ku.detect_script_prefix(root)}kanban.py reminders \".\"")


if __name__ == "__main__":
    main()
