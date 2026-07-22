"""hooks.py — lifecycle hooks for the autonomous kanban loop.

Hooks are deterministic runtime helpers around state transitions. They validate and
print instruction packets; they do not mutate board/spec files. All mutations still
belong to explicit kanban commands (`move`, `update`, `comment`, `tags`, ...).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import kanban_utils as ku

ALLOWED_EXITS = {
    "BACKLOG": {"TODO", "ICEBOX"},
    "ICEBOX": {"BACKLOG"},
    "TODO": {"IN PROGRESS", "BACKLOG"},
    "IN PROGRESS": {"TESTING", "IN REVIEW", "BLOCKED"},
    "BLOCKED": {"IN PROGRESS", "REWORK", "ICEBOX"},
    "TESTING": {"IN REVIEW", "IN PROGRESS"},
    "IN REVIEW": {"DONE", "REJECTED", "UAT"},
    "UAT": {"DONE", "REJECTED"},
    "REJECTED": {"REWORK"},
    "REWORK": {"TESTING", "IN REVIEW", "BLOCKED"},
    "DONE": set(),
}

TODO_PLUS = {"TODO", "IN PROGRESS", "BLOCKED", "TESTING", "IN REVIEW", "UAT", "REJECTED", "REWORK", "DONE"}


@dataclass(frozen=True)
class HookResult:
    ok: bool
    event: str
    message: str = ""
    recovery: str = ""

    def render(self) -> str:
        status = "OK" if self.ok else "BLOCKED"
        parts = [f"=== HOOK {self.event}: {status} ==="]
        if self.message:
            parts.append(self.message)
        if self.recovery:
            parts.append(f"Recovery: {self.recovery}")
        return "\n".join(parts)


def _spec_path(tasks: Path, slug: str) -> Path:
    return tasks / "specs" / f"{slug}.md"


def _frontmatter_value(text: str, key: str) -> str | None:
    m = re.search(rf"^{re.escape(key)}:\s*(.+)$", text, re.M)
    return m.group(1).strip() if m else None


# RU aliases for backward-compat with existing specs (mirrors check_item.py/lint_board.py)
_SECTION_ALIASES: dict[str, list[str]] = {
    "Subtasks": ["Подзадачи"],
    "Test Checklist": ["Тестовый чеклист"],
    "Review Checklist": ["Чеклист ревью"],
    "Comments": ["Комментарии"],
    "Output / Artifacts": ["Output / Артефакты"],
    "Changelog": ["История изменений"],
}


def _section_body(text: str, heading: str) -> str:
    for cand in [heading] + _SECTION_ALIASES.get(heading, []):
        pattern = rf"^## {re.escape(cand)}\n(.*?)(?=^## |\Z)"
        m = re.search(pattern, text, re.M | re.S)
        if m:
            return m.group(1).strip()
    return ""


def _checklist_counts(text: str, heading: str) -> tuple[int, int]:
    body = _section_body(text, heading)
    if not body:
        return (0, 0)
    items = re.findall(r"^\s*- \[([ xX])\]", body, re.M)
    done = sum(1 for x in items if x.lower() == "x")
    return done, len(items)


def _attention_comments(text: str) -> list[str]:
    body = _section_body(text, "Comments") or _section_body(text, "Комментарии")
    if not body:
        return []
    return [line for line in body.splitlines() if "!!!ВНИМАНИЕ!!!" in line]


def _planner_comment_present(text: str) -> bool:
    body = _section_body(text, "Comments") or _section_body(text, "Комментарии")
    if not body:
        return False
    return any("| planner |" in line for line in body.splitlines())


def _output_links(text: str, limit: int = 5) -> list[str]:
    body = _section_body(text, "Output / Artifacts") or _section_body(text, "Output / Артефакты")
    if not body:
        return []
    links = []
    for line in body.splitlines():
        item = line.strip()
        if item.startswith("- "):
            item = item[2:].strip()
        if not item:
            continue
        links.append(item)
        if len(links) >= limit:
            break
    return links


def _next_allowed_action(slug: str, column: str) -> str:
    allowed = sorted(ALLOWED_EXITS.get(column, set()))
    if not allowed:
        return "terminal state; no workflow transition is allowed"
    commands = []
    for target in allowed:
        alias = target.replace(" ", "_")
        commands.append(f"kanban.py move \".\" {slug} {alias}")
    return " | ".join(commands)


# C6 (ADR-001): checklist-completion gate. Maps a (source, target) transition to the
# checklist heading that must be closed in the SOURCE column's spec before the card is
# allowed to leave it, plus the minimum required. `None` minimum means "no gate" (not
# in this dict at all has the same effect — see _checklist_gate_requirement below).
# Calibrated conservatively: only the transitions in this dict are gated, everything else
# (including all rollback targets BLOCKED/BACKLOG/REJECTED/REWORK) is not.
# Canonical description (thresholds, empty-checklist rule): references/workflow-contract.md
# §C6 — keep this dict in sync with that table, do not restate thresholds elsewhere.
_CHECKLIST_GATES = {
    ("TESTING", "IN REVIEW"): ("Test Checklist", "min", 1),
    ("IN REVIEW", "DONE"): ("Review Checklist", "all", None),
    ("UAT", "DONE"): ("Review Checklist", "all", None),
}


def _checklist_gate_requirement(source: str, target: str):
    """Return (heading, mode, minimum) for a gated transition, or None if not gated."""
    return _CHECKLIST_GATES.get((source, target))


def before_move(tasks: Path, slug: str, source: str, target: str, title: str | None = None) -> HookResult:
    """Validate a transition before board/spec mutation.

    This hook is intentionally side-effect free. It returns a recovery packet for
    illegal transitions, missing TODO+ specs, a missing startedAt on BACKLOG->TODO
    (the analyst has no inbound move to stamp it), a missing planner comment on
    TODO->IN PROGRESS (the planner role has no inbound move to stamp it either), and
    (C6) incomplete role checklists on gated transitions (TESTING->IN REVIEW,
    IN REVIEW->DONE, UAT->DONE).

    Canonical description of every gate (all 5 transitions, exact thresholds, recovery):
    references/workflow-contract.md §C6 + Process Gates. This docstring/code stays in sync
    with that contract; thresholds are not restated in SKILL.md §9 (pointer only).
    """
    allowed = ALLOWED_EXITS.get(source, set())
    if target not in allowed:
        return HookResult(
            ok=False,
            event="before_move",
            message=f"Cannot move {source} -> {target}: transition is not allowed by workflow-contract.md.",
            recovery=f"Use one of: {', '.join(sorted(allowed)) or 'terminal state'}; or document a new transition in workflow-contract.md first.",
        )
    spec = _spec_path(tasks, slug)
    if target in TODO_PLUS and not spec.is_file():
        return HookResult(
            ok=False,
            event="before_move",
            message=f"Cannot move {source} -> {target}: tasks/specs/{slug}.md is missing.",
            recovery=f"python .agents/skills/obsidian-kanban/scripts/kanban.py new-task \".\" {slug} \"<title>\" --owner user --board <board.md>",
        )

    # Read the spec once here (read-once): the missing-spec gate above guarantees the
    # file exists for any TODO_PLUS target, so both the startedAt gate and the C6 gate
    # below reuse this single read instead of reading the spec twice.
    spec_text = spec.read_text(encoding="utf-8", errors="replace") if spec.is_file() else ""

    # startedAt gate: the analyst role has no inbound `move`, so a card can reach TODO
    # without startedAt ever being stamped. Deterministically catch that here — but only
    # for target == "TODO" (leave ICEBOX freezes and rollback targets untouched).
    if target == "TODO":
        started = _frontmatter_value(spec_text, "startedAt")
        if started is None or started.strip() == "" or started.strip().lower() == "null":
            return HookResult(
                ok=False,
                event="before_move",
                message=(
                    f"Cannot move {source} -> {target}: startedAt is not set — "
                    "analyst must stamp work start before handing off to TODO."
                ),
                recovery=(
                    f"Run: kanban.py tags \".\" {slug} --start today "
                    "(stamps startedAt at the moment analyst work begins), then retry the move."
                ),
            )

    # planner gate: TODO -> IN PROGRESS is the developer's own transition (no inbound
    # hook stamps planner involvement), so a card can skip the planner role entirely and
    # go straight from TODO to development. Deterministically catch that here — only for
    # this exact transition; the TODO -> BACKLOG rollback is intentionally left untouched.
    if source == "TODO" and target == "IN PROGRESS":
        if not _planner_comment_present(spec_text):
            return HookResult(
                ok=False,
                event="before_move",
                message=(
                    f"Cannot move {source} -> {target}: no planner comment in ## Comments — "
                    "planner role checklist was not executed."
                ),
                recovery=(
                    f"Run: kanban.py comment \".\" {slug} planner \"<estimate, priority order>\" "
                    "(see agents/planner.md), then retry the move."
                ),
            )

    gate = _checklist_gate_requirement(source, target)
    if gate is not None and spec.is_file():
        heading, mode, minimum = gate
        text = spec_text
        done, total = _checklist_counts(text, heading)
        if mode == "min":
            required = minimum
        else:  # "all": require every item closed, but an empty checklist is not a blocker
            required = total
        if total > 0 and done < required:
            missing = required - done
            return HookResult(
                ok=False,
                event="before_move",
                message=(
                    f"Cannot move {source} -> {target}: {heading} {done}/{total} done "
                    f"(need {required}/{total}) — {missing} item(s) still unchecked."
                ),
                recovery=(
                    f"{heading}: {done}/{total} done — close the remaining {missing} item(s) "
                    f"(kanban.py check-item \".\" {slug} <section> <N>) before moving to {target}."
                ),
            )

    return HookResult(ok=True, event="before_move", message=f"{source} -> {target} allowed")


def _role_checklist_block(column: str, title: str | None) -> str:
    """Render the full (compact) role checklist text for a column, or '' if none.

    Reuses kanban_utils.role_checklist (same source move_card.py's
    print_role_checklist reads from) and the single compact_text implementation
    (workflow.compact_text, exposed via kanban_utils) that move_card.py and
    role_prompt.py apply by default per A3/rii-output-hardening — no separate
    compaction logic here (B4, ADR-001).
    """
    name, role, text = ku.role_checklist(column, title)
    if text is None:
        return ""
    text = ku.compact_text(text)
    return f"--- ROLE CHECKLIST: {name} ({column}) ---\n{text.rstrip()}\n--- END ROLE CHECKLIST ---"


def resume_packet(tasks: Path, slug: str, column: str, title: str | None = None, role: str | None = None,
                   full: bool = False) -> str:
    """Build a context packet for the current task state.

    full=False (default): compact packet with checklist COUNTERS only (DoD/Test/
    Review done/total) — used by after_move, where the role checklist was already
    printed once by move_card.py in the same output and repeating it would just
    bloat the transition's stdout.
    full=True: additionally includes the FULL TEXT of the current column's role
    checklist (compact-filtered, no python-command blocks) — used by on_resume/
    resume.py and role_prompt.py's explicit pull path, so an agent that lost stdout
    (post-compact, session resume) can recover the complete checklist from a single
    read-only call, without a separate Read of agents/<role>.md (B4, ADR-001 pull-
    first contract, SKILL.md §9).
    """
    spec = _spec_path(tasks, slug)
    spec_text = spec.read_text(encoding="utf-8", errors="replace") if spec.is_file() else ""
    step = _frontmatter_value(spec_text, "step") if spec_text else None
    status = _frontmatter_value(spec_text, "status") if spec_text else None
    dod = _checklist_counts(spec_text, "Definition of Done (DoD)") if spec_text else (0, 0)
    test = _checklist_counts(spec_text, "Test Checklist") if spec_text else (0, 0)
    review = _checklist_counts(spec_text, "Review Checklist") if spec_text else (0, 0)
    attention = _attention_comments(spec_text) if spec_text else []
    latest_attention = attention[-1] if attention else "none"
    outputs = _output_links(spec_text) if spec_text else []
    output_line = "; ".join(outputs) if outputs else "none"
    next_action = _next_allowed_action(slug, column)
    parts = [
        "\n=== RESUME PACKET ===",
        f"Task: [[{slug}|{title or slug}]]",
        f"Column/status: {column}/{status or 'unknown'}",
        f"Role: {role or 'unknown'}",
        f"Step: {step or 'null'}",
        f"Attention: {latest_attention}",
        f"Checklists: DoD {dod[0]}/{dod[1]} · Test {test[0]}/{test[1]} · Review {review[0]}/{review[1]}",
        f"Output: {output_line}",
        f"Next allowed action: {next_action}",
    ]
    if full:
        block = _role_checklist_block(column, title)
        if block:
            parts.append(block)
    parts.append("Gate: follow the role checklist and run `kanban.py check` before transition.\n")
    return "\n".join(parts)


def after_move(tasks: Path, slug: str, source: str, target: str, title: str | None = None, role: str | None = None) -> str:
    """Return the post-transition packet printed after the role checklist.

    Kept compact (full=False): move_card.py already printed the target column's
    role checklist just above this packet in the same stdout — repeating the full
    text here would duplicate it in every transition's output (A3 compact budget).
    """
    return resume_packet(tasks, slug, target, title=title, role=role, full=False)


def on_resume(tasks: Path, slug: str, column: str, title: str | None = None, role: str | None = None) -> str:
    """Explicit pull path (resume.py / role_prompt.py). Always full: this is the
    call an agent makes specifically because it lacks the checklist from stdout
    (lost context, session resume) — the pull-first contract (SKILL.md §9) requires
    it to be a complete substitute for the push (move) output."""
    return resume_packet(tasks, slug, column, title=title, role=role, full=True)
