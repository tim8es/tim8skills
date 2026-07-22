"""Deterministic context-cost metrics over a kanban tasks/ workspace.

Reads tasks/ strictly read-only and prints context-cost rows that complement
the kanban historical proxy metrics (kanban.py metrics) without modifying
any kanban skill file.

Limitations: no token telemetry is available from the host, so all numbers
are deterministic proxies (bytes, lines, counts) — never exact token counts.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ATTENTION_MARKER = "!!!ВНИМАНИЕ!!!"
SECTION_RE = re.compile(r"^## (.+?)\s*$")
FRONTMATTER_KEY_RE = re.compile(r"^(\w+):\s*(.*)$")


class ScopeError(ValueError):
    pass


def normalize_board_name(board: str) -> str:
    board = board.strip()
    return board if board.endswith(".md") else board + ".md"


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the simple flat YAML frontmatter used by kanban specs."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = FRONTMATTER_KEY_RE.match(line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm


def project_of_spec(fm: dict[str, str]) -> str | None:
    flow_id = fm.get("flowId", "")
    return flow_id.split("/", 1)[0] if "/" in flow_id else None


def section_body(text: str, heading: str) -> str:
    """Return the body of a `## heading` section (up to the next ## or EOF)."""
    lines = text.splitlines()
    out: list[str] = []
    inside = False
    for line in lines:
        m = SECTION_RE.match(line)
        if m:
            if inside:
                break
            inside = m.group(1).strip().lower() == heading.lower()
            continue
        if inside:
            out.append(line)
    return "\n".join(out).strip()


def resolve_projects(board: str | None, project: str | None) -> set[str] | None:
    if board and project:
        raise ScopeError("Use only one scope: --board or --project")
    if board:
        return {normalize_board_name(board)[:-3]}
    if project:
        return {project.strip()}
    return None


def collect(tasks: Path, *, board: str | None = None, project: str | None = None) -> dict:
    projects = resolve_projects(board, project)

    boards: list[tuple[str, int]] = []  # (name, bytes)
    for f in sorted(tasks.glob("*.md")):
        stem = f.stem
        if projects is not None and stem not in projects:
            continue
        boards.append((f.name, f.stat().st_size))

    specs_dir = tasks / "specs"
    per_task: list[dict] = []
    for f in sorted(specs_dir.glob("*.md")) if specs_dir.is_dir() else []:
        text = f.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text)
        proj = project_of_spec(fm)
        if projects is not None and proj not in projects:
            continue
        comments = section_body(text, "Comments")
        changelog = section_body(text, "Changelog")
        per_task.append(
            {
                "slug": f.stem,
                "spec_bytes": f.stat().st_size,
                "spec_lines": text.count("\n") + 1,
                "comments_bytes": len(comments.encode("utf-8")),
                "changelog_bytes": len(changelog.encode("utf-8")),
                "attention_count": text.count(ATTENTION_MARKER),
            }
        )

    return {
        "scope": board or project or "all",
        "boards": boards,
        "tasks": per_task,
    }


def render(data: dict) -> str:
    rows: list[str] = []
    rows.append(f"context-cost scope: {data['scope']}")
    rows.append(f"boards scanned: {len(data['boards'])}")
    for name, size in data["boards"]:
        rows.append(f"board {name}: {size} bytes")
    tasks = data["tasks"]
    rows.append(f"specs scanned: {len(tasks)}")
    rows.append(f"specs total bytes: {sum(t['spec_bytes'] for t in tasks)}")
    rows.append(f"comments total bytes: {sum(t['comments_bytes'] for t in tasks)}")
    rows.append(f"changelog total bytes: {sum(t['changelog_bytes'] for t in tasks)}")
    rows.append(f"attention flags: {sum(t['attention_count'] for t in tasks)}")
    heaviest = sorted(tasks, key=lambda t: t["comments_bytes"] + t["changelog_bytes"], reverse=True)[:5]
    for t in heaviest:
        rows.append(
            "task {slug}: spec={spec_bytes}B comments={comments_bytes}B "
            "changelog={changelog_bytes}B attention={attention_count}".format(**t)
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to a legacy codepage; specs use Cyrillic slugs.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Print deterministic context-cost rows (read-only).")
    ap.add_argument("workspace", help="Workspace root containing tasks/")
    ap.add_argument("--board", help="Limit to one board file, e.g. claude-obsidian-kanban.md")
    ap.add_argument("--project", help="Limit to one project/board stem")
    args = ap.parse_args(argv)

    tasks = Path(args.workspace) / "tasks"
    if not tasks.is_dir():
        print(f"ERROR: tasks/ not found under {args.workspace}", file=sys.stderr)
        return 1
    try:
        data = collect(tasks, board=args.board, project=args.project)
    except ScopeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
