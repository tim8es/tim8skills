"""spec_mutations.py — spec scaffolding and mutations (YAML frontmatter, sections).

Exported by kanban_utils.py (backward-compat facade).
"""
from __future__ import annotations

import contextlib
import datetime as dt
import re
from pathlib import Path

import lint_board as lb
from board_io import MutationError, _fsync_write, board_lock  # noqa: F401 (MutationError re-exported)

_UPDATED_RE = re.compile(r"^(updatedAt:\s*).*$", re.M)

# itemType emoji for the spec H1 heading (§4)
_ITEM_EMOJI = {"epic": "🗃️", "task": "📋", "subtask": "✅"}
_TASK_REVIEW_CHECKLIST = (
    "## Review Checklist\n"
    "- [ ] Artifact or code exists at the expected path\n"
    "- [ ] All DoD items are completed\n"
    "- [ ] No regressions in adjacent functionality\n"
    "- [ ] Documentation or task notes are updated when applicable\n\n"
)


def now_stamp() -> str:
    """Current system time in the canonical `YYYY-MM-DD HH:MM:SS` format (§8)."""
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Timestamp for `## Changelog` entries — identical in format to now_stamp,
# kept as an alias for readability at Changelog call sites.
hist_stamp = now_stamp


def bump_updated_at(text: str) -> str:
    """Sets updatedAt = the current system time (first occurrence in the frontmatter)."""
    return _UPDATED_RE.sub(lambda m: m.group(1) + now_stamp(), text, count=1)


def mutate_spec(workspace, slug: str, transform, *, bump: bool = True,
                dry_run: bool = False) -> tuple[int, str]:
    """Shared envelope for mutating the spec specs/<slug>.md. Returns (rc, final message).

    transform(text) -> (new_text, inner_msg): a pure function describing exactly the mutation.
    A domain error is signaled via `raise MutationError(msg, rc)`.
    """
    tasks = lb.resolve_tasks_dir(Path(workspace).expanduser())
    spec = tasks / "specs" / f"{slug}.md"
    if not spec.is_file():
        return 1, f"✗ Spec not found: {spec}"

    lock = board_lock(tasks) if not dry_run else contextlib.nullcontext()
    with lock:
        text = spec.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        try:
            new_text, inner = transform(text)
        except MutationError as e:
            return e.rc, str(e)
        if bump:
            new_text = bump_updated_at(new_text)
        if not new_text.endswith("\n"):
            new_text += "\n"
        if dry_run:
            return 0, f"[dry-run] {inner}"
        _fsync_write(spec, new_text)
    return 0, f"✅ {inner}"


def _task_body(name: str, item_type: str, now: str) -> str:
    emoji = _ITEM_EMOJI.get(item_type, "📋")
    return (
        f"# {emoji} {name}\n\n"
        "## Description\n\n\n"
        "## Definition of Done (DoD)\n- [ ] \n\n"
        "## Subtasks\n- [ ] \n\n"
        "## Technical Details\n\n\n"
        "## Output / Artifacts\n- \n\n"
        "## Test Checklist\n- [ ] \n\n" +
        _TASK_REVIEW_CHECKLIST +
        "## Dependencies\n- Depends on: —\n- Blocks: —\n\n"
        f"## Changelog\n\n{hist_stamp()} | analyst | Task created\n\n"
        "## Comments\n"
    )


def _epic_body(name: str, now: str) -> str:
    return (
        f"# 🗃️ {name}\n\n"
        "## Goal\n\n\n"
        "## Context\n\n\n"
        "## Definition of Done (DoD)\n- [ ] \n- [ ] \n\n"
        "## Tasks\n- [ ] \n\n"
        "## Dependencies\n- Blocks: —\n- Depends on: —\n\n"
        "## Risks\n\n\n"
        "## Review Checklist\n- [ ] All tasks from Tasks section are done\n\n"
        f"## Changelog\n\n{hist_stamp()} | analyst | Epic created\n\n"
        "## Comments\n"
    )


def build_spec_text(item_type: str, slug: str, name: str, project: str,
                    priority: str = "medium", parent=None, now=None,
                    column: str = "BACKLOG", owner: str = "analyst") -> str:
    """Full spec text (frontmatter + canonical sections) for task/subtask/epic."""
    import sync_properties as sp  # lazy import
    from board_io import COLUMN_TO_STATUS  # noqa: PLC0415
    now = now or now_stamp()
    col_upper = column.upper().replace("-", " ").replace("_", " ")
    status = COLUMN_TO_STATUS.get(col_upper, "backlog")
    fm = {
        "flowId": f"{project}/{item_type}/{slug}",
        "itemType": item_type,
        "status": status,
        "parentId": parent or "null",
        "step": "null",
        "owner": owner,
        "priority": priority,
        "createdAt": now,
        "updatedAt": now,
        "reminder": "null",
        "startedAt": "null",
        "testingAt": "null",
        "reviewAt": "null",
        "doneAt": "null",
        "dependsOn": "[]",
        "blocks": "[]",
    }
    front = sp.render_frontmatter(fm)
    body = _epic_body(name, now) if item_type == "epic" else _task_body(name, item_type, now)
    return front + "\n\n" + body


def scaffold_spec(tasks, item_type: str, slug: str, name: str, *,
                  priority: str = "medium", parent=None, board_hint=None,
                  card: bool = False, column: str = "BACKLOG", owner: str = "analyst",
                  dry_run: bool = False) -> tuple:
    """Creates the spec specs/<slug>.md from the template. Returns (rc, message)."""
    from board_io import resolve_single_board
    board_file, err = resolve_single_board(tasks, board_hint)
    if err:
        return 1, err
    project = board_file.stem
    specs_dir = tasks / "specs"
    spec_path = specs_dir / f"{slug}.md"
    if spec_path.exists():
        return 1, (f"✗ Spec already exists: specs/{slug}.md — choose a different slug "
                   f"or edit the existing one.")

    warn = ""
    if parent and not (specs_dir / f"{parent}.md").exists():
        warn = f"▲ parentId `{parent}` not found in specs/ — check --epic.\n"

    text = build_spec_text(item_type, slug, name, project,
                           priority=priority, parent=parent, column=column, owner=owner)

    if dry_run:
        out = [f"{warn}[dry-run] + spec specs/{slug}.md "
               f"(project={project}, itemType={item_type}, priority={priority})"]
        if card:
            out.append(f"[dry-run] + card [[{slug}]] → {column} ({board_file.name})")
        out.append("--- frontmatter + sections ---")
        out.append(text)
        return 0, "\n".join(out)

    specs_dir.mkdir(parents=True, exist_ok=True)
    _fsync_write(spec_path, text)
    out = [f"{warn}✅ Spec created: specs/{slug}.md "
           f"(project={project}, itemType={item_type})"]
    if card:
        import add_card as ac  # lazy import
        rc, cmsg = ac.add_card_to_board(
            tasks, slug, name, column=column, board_hint=board_file.name)
        out.append(cmsg)
        if rc:
            return rc, "\n".join(out)
    return 0, "\n".join(out)
