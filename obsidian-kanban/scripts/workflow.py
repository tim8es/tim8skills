"""workflow.py — column/role mapping, role_checklist, next-task lookup.

Exported by kanban_utils.py (backward-compat facade).
"""
from __future__ import annotations

import re
from pathlib import Path

import lint_board as lb
from board_io import find_boards, parse_board, parse_tag_line

WIKILINK_RE = lb.WIKILINK_RE

# §5 SKILL.md: board column -> role file slug (agents/<slug>.md).
COLUMN_TO_ROLE = {
    "BACKLOG": "analyst",
    "ICEBOX": "archivist",
    "TODO": "planner",
    "IN PROGRESS": "developer",
    "BLOCKED": "communicator",
    "TESTING": "tester",
    "IN REVIEW": "reviewer",
    "UAT": "uat",
    "REJECTED": "debugger",
    "REWORK": "developer",
    "DONE": "documenter",
}

# CLI-safe aliases for columns with spaces.
COLUMN_ALIASES = {
    "IN_PROGRESS": "IN PROGRESS",
    "IN-PROGRESS": "IN PROGRESS",
    "INREVIEW": "IN REVIEW",
    "IN_REVIEW": "IN REVIEW",
    "IN-REVIEW": "IN REVIEW",
}

# agents/ lives next to scripts/ in the skill's infrastructure
AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"


def compact_text(text: str) -> str:
    """Filter role text to headers and checklist items only.

    Fenced code blocks whose first non-empty line starts with 'python ' are
    stripped (they are command examples). All other code blocks (e.g. the
    subagent prompt template in developer.md) are kept intact so that a
    developer reading compact mode can still spawn subagents correctly.
    Single implementation shared by move_card.py, role_prompt.py and hooks.py.
    """
    out: list[str] = []
    in_fence = False
    fence_lines: list[str] = []
    fence_is_python: bool | None = None  # None = unknown yet (no non-empty line seen)

    for line in text.splitlines():
        if line.startswith("```"):
            if not in_fence:
                # Opening fence — buffer it; we don't know yet if it's python
                in_fence = True
                fence_lines = [line]
                fence_is_python = None
            else:
                # Closing fence
                in_fence = False
                fence_lines.append(line)
                if not fence_is_python:
                    # Keep the whole block (non-python or empty block)
                    out.extend(fence_lines)
                fence_lines = []
                fence_is_python = None
            continue

        if in_fence:
            fence_lines.append(line)
            if fence_is_python is None:
                stripped = line.strip()
                if stripped:
                    fence_is_python = stripped.startswith("python ")
            continue

        # Outside fences: drop bare python command lines
        stripped = line.strip()
        if stripped.startswith("python ") or stripped.startswith("`python"):
            continue
        out.append(line)

    # Unclosed fence at EOF — keep it (it's content, not a command block)
    if fence_lines:
        if not fence_is_python:
            out.extend(fence_lines)

    return "\n".join(out)


def normalize_column(value: str) -> str:
    """Normalize a user/CLI column argument to the canonical board column name."""
    raw = (value or "").strip().upper()
    return COLUMN_ALIASES.get(raw, raw)


def role_for_column(column, card_title=None):
    """Role slug for the column. For IN PROGRESS with `RESEARCH:` in the title → researcher."""
    column = normalize_column(column)
    if (column == "IN PROGRESS" and card_title
            and card_title.strip().upper().startswith("RESEARCH:")):
        return "researcher"
    return COLUMN_TO_ROLE.get(column)


def _strip_section(text: str, title: str) -> str:
    """Removes the `## <title>` section up to the next `## ` or the end."""
    lines = text.split("\n")
    out: list[str] = []
    skip = False
    for line in lines:
        if line.strip() == f"## {title}":
            skip = True
            continue
        if skip and line.startswith("## "):
            skip = False
        if not skip:
            out.append(line)
    return "\n".join(out)


def role_checklist(column, card_title=None):
    """(display_name, role_slug, text) for printing the target column's role checklist."""
    role = role_for_column(column, card_title)
    if not role:
        return (None, None, None)
    f = AGENTS_DIR / f"{role}.md"
    if not f.is_file():
        return (None, role, None)
    text = f.read_text(encoding="utf-8")
    m = re.search(r"^#\s+(.+)$", text, re.M)
    name = re.split(r"\s+[—–-]\s+", m.group(1), maxsplit=1)[0].strip() if m else role
    trimmed = _strip_section(text, "Method").rstrip()
    trimmed += f"\n\nℹ Full role file (the \"Method\" section and more): agents/{role}.md"
    return (name, role, trimmed)


_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, None: 3}
_NEXT_TASK_COLUMNS = ["REWORK", "TODO", "BACKLOG"]
_TITLE_RE = re.compile(r"\[\[[^\]|]+\|([^\]]*)\]\]")


def find_next_task(tasks: Path) -> dict | None:
    """Scans REWORK→TODO→BACKLOG across all boards, returns the card with the highest priority."""
    for col in _NEXT_TASK_COLUMNS:
        candidates = []
        for board in find_boards(tasks):
            text = board.read_text(encoding="utf-8", errors="replace")
            cols, _ = parse_board(text)
            for block in cols.get(col, []):
                mm = WIKILINK_RE.search(block[0])
                if not mm:
                    continue
                slug = mm.group(1).strip()
                tm = _TITLE_RE.search(block[0])
                title = tm.group(1).strip() if tm else slug
                tag_line = next((l for l in block if l.startswith("\t")), "")
                priority = parse_tag_line(tag_line).get("priority")
                candidates.append({"slug": slug, "title": title,
                                    "column": col, "priority": priority,
                                    "board": board.stem})
        if candidates:
            candidates.sort(key=lambda c: _PRIORITY_ORDER.get(c["priority"], 3))
            return candidates[0]
    return None


_SUBAGENT_HINT = (
    "\n⚡ SUBAGENT (§13): task is in TODO — call the Agent tool with the prompt from"
    " agents/subagent-runner.md. Do NOT take IN PROGRESS yourself."
)


def format_next_task(task: dict | None, script_prefix: str = "<SCRIPT_PREFIX>/") -> str:
    """Formats the next-task output for injection into the agent's stdout."""
    if task is None:
        return "📭 Queue is empty — no tasks in REWORK/TODO/BACKLOG."
    col = task["column"]
    pri_emoji = {"high": "🟥", "medium": "🟨", "low": "🟩"}.get(task["priority"], "  ")
    slug, title, board = task["slug"], task["title"], task["board"]
    if col == "REWORK":
        action = "enter the developer role (move_card not needed)"
        hint = ""
    elif col == "TODO":
        action = f'python {script_prefix}kanban.py move "." {slug} IN_PROGRESS  → developer'
        hint = _SUBAGENT_HINT
    else:  # BACKLOG
        action = (f"enter the analyst role (agents/analyst.md): create the spec, fill in the DoD;\n"
                  f"   then: python {script_prefix}kanban.py move \".\" {slug} TODO")
        hint = ""
    return (f"\n=== NEXT TASK ({board}) ===\n"
            f"{pri_emoji} {col} · [[{slug}|{title}]]\n"
            f"↳ {action}{hint}\n")
