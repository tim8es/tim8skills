#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lint_board.py — Obsidian Kanban workspace linter (REPORT-ONLY MODE).

Checks rules from SKILL.md:
  §6  — Kanban board format (frontmatter, tags line, settings block, checkboxes);
  §8  — required YAML fields and valid values in specs/*.md;
  §10 — orphan / reverse-orphan / stale / dependency + status↔column desync;
        lost-DONE safeguard: doneAt≠null, but the card is outside the DONE column -> WARN
        (a false/racy move dropped a completed card; status↔column sync
        silently reconciles this desync, so detection relies on the un-clearable doneAt);
        required sections (DoD, Changelog) -> WARN; `| agent |` signature -> WARN;
        semantic-drift -> WARN (the last history entry signals stage completion,
        but the status was not advanced: e.g. "Review passed" while status=review);
        Output / Artifacts -> ERROR if the result link is not in wikilink format
        `[[name|Title]]` (§2); exception — external resources (PR/URL).

Source check (research artifacts tagged `исследования`):
  When status==review, the linter finds the artifact via the spec's `## Output / Artifacts`
  section and checks its tag: the gate only fires if the artifact has the `исследования`
  tag in the frontmatter (`tags`). Non-research artifacts (audit, concept, process docs) are skipped.
  For a research artifact, checks the `## Sources` section:
  • The section must be present — otherwise ERROR.
  • Each source line (starts with `-`) must contain a URL (http/https)
    or an explicit document name in parentheses — otherwise WARN for each source without a URL.

Gates when status==review (ERROR, only at this point -> done specs are not re-checked):
  • DoD and Review Checklist are filled in (≥1 checked item with text) — for all itemTypes;
  • Test Checklist is filled in — only for task/subtask (an epic has no functional test).

The script WRITES NOTHING. Use sync_properties.py for auto-fixing.

Usage:
    python scripts/lint_board.py <WORKSPACE_ROOT>            # whole workspace
    python scripts/lint_board.py <WORKSPACE_ROOT>/tasks      # a path to tasks/ is also allowed
    python scripts/lint_board.py <WORKSPACE_ROOT> --strict   # WARN also causes exit 1

Exit codes: 0 — no errors; 1 — has ERROR (or WARN with --strict).
"""

from __future__ import annotations

import sys

# Windows: force UTF-8 so ✗/✅/▲ don't fail with UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import datetime as dt
import re
import urllib.request
import urllib.error
from pathlib import Path

from lint_board_rules import (
    CARD_LINE_RE,
    CARD_RE,
    COLUMN_ORDER,
    COLUMN_TO_STATUS,
    COLUMN_TO_TIMESTAMP,
    DATE_RE,
    DONE_CHAIN_BASE,
    DONE_CHAIN_FINALS,
    FLOWID_RE,
    ITEMTYPE_UNASSIGNED_OK_STATUS,
    NON_RESEARCH_PREFIX_RE,
    PROCESS_GATE_START,
    REMINDER_RE,
    REQUIRED_FIELDS,
    RESEARCH_TITLE_RE,
    STALE_DAYS,
    TAG_SEQUENCE,
    TODO_PLUS_COLUMNS,
    VALID_ITEMTYPE,
    VALID_OWNER,
    VALID_PRIORITY,
    VALID_STATUS,
    WIKILINK_RE,
)

# --- Reference tables from SKILL.md -------------------------------------------------


class Report:
    """Accumulates findings by severity level."""

    def __init__(self) -> None:
        self.items: list[tuple[str, str, str]] = []  # (severity, scope, message)

    def error(self, scope: str, msg: str) -> None:
        self.items.append(("ERROR", scope, msg))

    def warn(self, scope: str, msg: str) -> None:
        self.items.append(("WARN", scope, msg))

    @property
    def errors(self) -> int:
        return sum(1 for s, _, _ in self.items if s == "ERROR")

    @property
    def warns(self) -> int:
        return sum(1 for s, _, _ in self.items if s == "WARN")


def parse_yaml_list(val: str) -> list[str]:
    """Parse inline YAML list string '[a, b]' → ['a', 'b']. Empty/null → []."""
    val = (val or "").strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        return [s.strip() for s in inner.split(",") if s.strip()] if inner else []
    return []


# --- Parsing -----------------------------------------------------------------

def parse_frontmatter(text: str) -> dict | None:
    """Minimal parser for flat YAML frontmatter. None if there is no block."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # normalize CRLF/CR → LF
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end].strip("\n")
    data: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        data[key.strip()] = val.strip()
    return data


def parse_board(text: str) -> dict[str, str]:
    """slug -> column. Takes the first wikilink in each card line."""
    slug_to_column: dict[str, str] = {}
    for slug, col, _title in iter_board_cards(text):
        slug_to_column[slug] = col
    return slug_to_column


def iter_board_cards(text: str):
    """Yield (slug, column, display_title) for wikilink cards."""
    current = None
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m and m.group(1).strip() in COLUMN_TO_STATUS:
            current = m.group(1).strip()
            continue
        if current and CARD_RE.match(line):
            link = WIKILINK_RE.search(line)
            if link:
                raw = link.group(0).strip("[]")
                parts = raw.split("|", 1)
                title = parts[1].strip() if len(parts) == 2 else parts[0].strip()
                yield link.group(1).strip(), current, title


# --- Board checks (§6) -----------------------------------------------------

def lint_board_file(path: Path, text: str, rep: Report) -> dict[str, str]:
    scope = path.name
    lines = text.splitlines()

    # frontmatter: only kanban-plugin: board
    fm = parse_frontmatter(text)
    if fm is None:
        rep.error(scope, "no `kanban-plugin: board` frontmatter block")
    else:
        extra = [k for k in fm if k != "kanban-plugin"]
        if fm.get("kanban-plugin") != "board":
            rep.error(scope, "frontmatter must contain `kanban-plugin: board`")
        if extra:
            rep.error(scope, f"extra fields in board frontmatter: {', '.join(extra)}")

    # settings block and list-collapse length matching the number of columns (COLUMN_ORDER)
    if "%% kanban:settings" not in text:
        rep.error(scope, "missing `%% kanban:settings %%` block")
    else:
        lc = re.search(r'"list-collapse":\s*\[([^\]]*)\]', text)
        if lc:
            n = len([x for x in lc.group(1).split(",") if x.strip()])
            if n != len(COLUMN_ORDER):
                rep.error(scope, f"list-collapse has {n} values, expected {len(COLUMN_ORDER)}")

    # all COLUMN_ORDER columns are present
    headers = [m.group(1).strip() for m in
               (re.match(r"^##\s+(.+?)\s*$", ln) for ln in lines) if m]
    for col in COLUMN_ORDER:
        if col not in headers:
            rep.error(scope, f"missing column `## {col}`")

    # card line -> tags line with a tab + tag order
    for i, line in enumerate(lines):
        if CARD_RE.match(line):
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if not nxt.startswith("\t"):
                rep.warn(scope, f"card without a tab-prefixed tags line: {line.strip()[:60]}")
            else:
                present = [t for t in TAG_SEQUENCE if t in nxt]
                positions = [nxt.index(t) for t in present]
                if positions != sorted(positions):
                    rep.warn(scope, f"emoji tag order is broken: {nxt.strip()[:60]}")

    # reverse check: the tags line (tab + emoji-date-tag) must come RIGHT AFTER
    # the card line. An orphaned tags line (card removed/not finished) is
    # §6 format garbage that the direct check above doesn't catch. -> WARN.
    for i, line in enumerate(lines):
        if line.startswith("\t") and any(t in line for t in TAG_SEQUENCE):
            prev = lines[i - 1] if i > 0 else ""
            if not CARD_LINE_RE.match(prev):
                rep.warn(scope, f"tags line with no card above it (orphan): {line.strip()[:60]}")

    # §4 + user rule: EVERY card must have a wikilink to a spec (and
    # go through the analyst). A plain-text card without `[[...]]` is invisible to
    # parse_board/gates, isn't tracked, and falls out of the role cycle. -> WARN.
    for line in lines:
        if CARD_LINE_RE.match(line) and not WIKILINK_RE.search(line):
            rep.warn(scope, f"card without a wikilink — add [[spec|Title]] (§4): "
                            f"{line.strip()[:60]}")

    # Research routing: research-like work should enter the researcher role via RESEARCH:.
    for slug, col, title in iter_board_cards(text):
        normalized_title = (title or "").strip()
        if col in ("BACKLOG", "ICEBOX", "DONE"):
            continue
        if NON_RESEARCH_PREFIX_RE.match(normalized_title):
            continue
        if normalized_title and RESEARCH_TITLE_RE.search(normalized_title) and not normalized_title.upper().startswith("RESEARCH:"):
            rep.warn(scope, f"research-like card `[[{slug}]]` ({col}) without the `RESEARCH:` prefix — "
                            "recovery: rename the card to `RESEARCH: ...` so IN PROGRESS routes to the researcher role")

    board = parse_board(text)

    # §DONE-overflow: WARN when >10 completed tasks — archiving recommended
    # Archive boards (*-archive.md) are not checked; their DONE grows by definition.
    if not path.stem.endswith("-archive"):
        DONE_THRESHOLD = 10
        done_count = sum(1 for st in board.values() if st == "DONE")
        if done_count > DONE_THRESHOLD:
            rep.warn(scope, f"the DONE column has {done_count} tasks (>{DONE_THRESHOLD}) — "
                            f"archiving recommended: "
                            f"python <SCRIPT_PREFIX>/kanban.py archive \".\" {path.stem}")

    return board


# --- Spec checks (§8) ----------------------------------------------

def lint_spec_file(path: Path, text: str, rep: Report) -> dict | None:
    scope = f"specs/{path.name}"
    fm = parse_frontmatter(text)
    if fm is None:
        rep.error(scope, "no YAML frontmatter")
        return None

    for f in REQUIRED_FIELDS:
        if f not in fm:
            rep.error(scope, f"missing required field `{f}`")

    if fm.get("flowId") and not FLOWID_RE.match(fm["flowId"]):
        rep.error(scope, f"flowId must be in the format project/type/slug: `{fm['flowId']}`")
    if fm.get("status") and fm["status"] not in VALID_STATUS:
        rep.error(scope, f"invalid status: `{fm['status']}`")
    if fm.get("itemType") and fm["itemType"] not in VALID_ITEMTYPE:
        rep.error(scope, f"invalid itemType: `{fm['itemType']}`")
    # `unassigned` is only for an unrefined BACKLOG/ICEBOX idea; further along the
    # flow the analyst must assign task/epic (agents/analyst.md). If the card is
    # already outside backlog/icebox and the type is still unassigned — this is a skipped step.
    if fm.get("itemType") == "unassigned" and fm.get("status") not in ITEMTYPE_UNASSIGNED_OK_STATUS:
        rep.error(scope, "itemType `unassigned` outside BACKLOG/ICEBOX — the analyst must assign task/epic before moving to TODO")
    if fm.get("owner") and fm["owner"] not in VALID_OWNER:
        rep.error(scope, f"invalid owner: `{fm['owner']}`")
    # `null` is a valid literal for "priority not set" (a card from the dashboard without
    # an emoji priority on the board; see sync_properties.py normalize_fields, which
    # normalizes the dashboard's incoming `none` to this same sentinel), consistent with
    # the other optional fields (reminder, etc.).
    if fm.get("priority") and fm["priority"] != "null" and fm["priority"] not in VALID_PRIORITY:
        rep.error(scope, f"invalid priority: `{fm['priority']}`")
    for d in ("createdAt", "updatedAt"):
        if fm.get(d) and not DATE_RE.match(fm[d]):
            rep.error(scope, f"field `{d}` is not in YYYY-MM-DD HH:MM[:SS] format: `{fm[d]}`")

    # reminder — optional; if given, validate the format
    reminder = fm.get("reminder", "")
    if reminder and reminder != "null" and not REMINDER_RE.match(reminder):
        rep.error(scope, f"invalid `reminder` format: `{reminder}` "
                         f"— valid: YYYY-MM-DD | weekly:mon | monthly:15 | daily | null")

    return fm


# --- Cross-checks (§10) ----------------------------------------------------

# §8/§9: universally required sections (missing -> WARN). Only what's needed
# from the moment of creation: the goal (DoD) and the log (Changelog). Checklists (Review, Test)
# are NOT included — the review gate ensures their presence and completeness exactly when
# they're needed, otherwise backlog/legacy specs would drown in premature warnings.
BASE_REQUIRED_SECTIONS = ["Definition of Done", "Changelog"]
# RU aliases for backward-compat with existing specs
_REQUIRED_SECTION_ALIASES: dict[str, list[str]] = {
    "Definition of Done": ["Definition of Done (DoD)"],
    "Changelog": ["История изменений"],
}
# Statuses in which in-progress-like work can go "stale"
STALE_STATUSES = ("in-progress", "rejected", "rework", "review")

# Semantic drift: a stage-completion marker in the LAST history entry while the status has
# not yet been advanced. Conservative: only explicit phrasing, to avoid noise on intermediate entries.
SEMANTIC_DRIFT_MARKERS = {
    "review": re.compile(r"ревью\s+(?:пройден|одобрен)", re.IGNORECASE),
    "testing": re.compile(r"(?:все\s+тесты\s+прошл|тесты\s+пройден)", re.IGNORECASE),
}


def check_checklist_gap(body: str, title: str, scope: str, rep: Report) -> None:
    """ERROR if the gate section contains no CHECKED item with text.

    Applied to DoD and Test Checklist only when status==review — at the
    transition point to done. Empty `- [ ]` items with no text don't count. N/A: a task with
    no functional test sets `- [x] N/A — reason`, and the checked item passes.
    """
    sec = extract_section(body, title, *_REQUIRED_SECTION_ALIASES.get(title, []))
    # [ \t]* (not \s*): \s includes \n, and an empty `- [ ]` would swallow the next line
    items = re.findall(r"- \[([ xX])\][ \t]*(.*)", sec)
    done = [t for mark, t in items if mark.lower() == "x" and t.strip()]
    if not done:
        rep.error(scope, f"in review, but \"{title}\" is not filled in "
                         f"(no checked item with text)")


def _enforce_done_chain_for(fm: dict) -> bool:
    """Only enforce the full-flow history gate for new process-era specs.

    Older DONE specs predate the strict workflow and would drown useful lint output.
    Missing/invalid createdAt stays opt-in for tests and freshly generated partial specs.
    """
    created = (fm.get("createdAt") or "").strip()
    if not created:
        return True
    try:
        return dt.datetime.strptime(created[:10], "%Y-%m-%d").date() >= PROCESS_GATE_START
    except ValueError:
        return True


def check_semantic_drift(status: str, hist: str, scope: str, rep: Report) -> None:
    """WARN if the LAST history entry signals stage completion, but the status hasn't advanced.

    Catches a stuck transition (observation #1): a task in `review` with an entry "Review passed",
    but not moved to `done`. Conservative — only explicit markers in the last line,
    to avoid noise on intermediate entries.
    """
    marker = SEMANTIC_DRIFT_MARKERS.get(status)
    if not marker:
        return
    lines = [l for l in hist.splitlines() if l.strip()]
    if lines and marker.search(lines[-1]):
        rep.warn(scope, f"the last history entry signals stage completion, "
                        f"but status is still `{status}` — advance the task or clarify the entry")


def related_links(body: str) -> set[str]:
    """Return explicit `## Related` wikilinks.

    Ordinary wikilinks in descriptions/comments are mentions, not a relationship
    contract. `## Related` is intentional and must be reciprocal.
    """
    sec = extract_section(body, "Related", "Связанные", "Связи")
    return {slug.strip() for slug in WIKILINK_RE.findall(sec) if slug.strip()}


def epic_task_links(body: str) -> set[str]:
    """Return wikilinks from an epic `## Tasks` section.

    Scoped `--slug` checks must load these child specs; otherwise an epic checks
    itself against an incomplete spec map and reports real child tasks as
    missing.
    """
    sec = extract_section(body, "Tasks", "Задачи")
    return {slug.strip() for slug in WIKILINK_RE.findall(sec) if slug.strip()}


def dependency_section_links(body: str) -> tuple[set[str], set[str]]:
    """Return prose `## Dependencies` depends-on and blocks wikilinks.

    YAML `dependsOn` / `blocks` is the canonical machine contract. This parser is
    only a guard for drift in human-readable dependency sections so active specs
    cannot claim a blocking relation that scripts and dashboards do not see.
    """
    deps: set[str] = set()
    blocks: set[str] = set()
    sec = extract_section(body, "Dependencies", "Зависимости")
    for raw in sec.splitlines():
        links = {slug.strip() for slug in WIKILINK_RE.findall(raw) if slug.strip()}
        if not links:
            continue
        line = raw.lower()
        if "depends on" in line or "зависит" in line:
            deps.update(links)
        elif "blocks" in line or "блок" in line:
            blocks.update(links)
    return deps, blocks


def check_epic_tasks_section(slug: str, fm: dict, body: str,
                             specs: dict[str, dict], rep: Report) -> None:
    """Validate that epic `## Tasks` points at real child specs.

    BACKLOG/ICEBOX epics may still be under discussion, so plain prose is a WARN.
    Once the epic leaves intake, prose-only task bullets are an ERROR: the role
    loop needs real task cards/specs, not a checklist hidden inside the epic.
    """
    if fm.get("itemType") != "epic":
        return

    scope = f"specs/{slug}.md"
    status = fm.get("status")
    tasks_section = extract_section(body, "Tasks", "Задачи")
    has_child_link = False
    for raw in tasks_section.splitlines():
        line = raw.strip()
        if not line.startswith("-"):
            continue
        item = re.sub(r"^-\s*(\[[ xX]\]\s*)?", "", line).strip()
        if not item or item == "—":
            continue

        links = [target.strip() for target in WIKILINK_RE.findall(item) if target.strip()]
        if not links:
            msg = (
                "the epic has a plain-text item in `## Tasks` instead of a wikilink to a "
                f"child spec: `{item[:80]}` — create the task via "
                "`kanban.py new-task ... --epic <epic-slug> --card` and replace "
                "the item with [[child-slug|Title]]"
            )
            if status in ("backlog", "icebox"):
                rep.warn(scope, msg)
            else:
                rep.error(scope, msg)
            continue

        has_child_link = True
        for target in links:
            if target not in specs:
                rep.error(scope, f"`## Tasks` links to `[[{target}]]`, but the spec was not found")
            elif specs[target].get("parentId") != slug:
                rep.warn(scope, f"`## Tasks` links to `[[{target}]]`, but parentId is not `{slug}`")

    # User directive 2026-07-09: an epic ALWAYS contains decomposed child
    # tasks; if decomposition isn't needed, it's a regular task, not an epic. An epic without
    # a single child wikilink in `## Tasks` (empty section or prose only) violates this.
    # During intake (BACKLOG/ICEBOX) decomposition may not be done yet — WARN there.
    if not has_child_link:
        msg = (
            "epic without decomposition: `## Tasks` contains no child task "
            "(wikilink). Either decompose via "
            "`kanban.py new-task ... --epic <epic-slug> --card`, or, if decomposition "
            "isn't needed, change `itemType` to `task` (non-composite work is a task, "
            "not an epic)."
        )
        if status in ("backlog", "icebox"):
            rep.warn(scope, msg)
        else:
            rep.error(scope, msg)


def check_artifact_slug_collisions(tasks_dir: Path, specs: dict[str, dict], rep: Report) -> None:
    """Artifact wikilinks use shortest-path slugs, so artifact slugs must be globally unique."""
    artifacts_dir = tasks_dir / "artifacts"
    if not artifacts_dir.is_dir():
        return
    for md in sorted(artifacts_dir.glob("*.md")):
        if md.stem in specs:
            status = specs[md.stem].get("status")
            message = (
                f"artifact slug `{md.stem}` duplicates `tasks/specs/{md.stem}.md`; "
                "use a unique artifact slug and update `## Output / Artifacts` wikilinks"
            )
            if status in ("done", "icebox"):
                rep.warn(f"artifacts/{md.name}", message)
            else:
                rep.error(f"artifacts/{md.name}", message)


def cross_checks(board: dict[str, str], specs: dict[str, dict],
                 spec_bodies: dict[str, str], rep: Report,
                 tasks_dir: Path | None = None, *, check_urls: bool = False) -> None:
    today = dt.date.today()
    related = {slug: related_links(body) for slug, body in spec_bodies.items()}
    if tasks_dir:
        check_artifact_slug_collisions(tasks_dir, specs, rep)

    # Orphan: BACKLOG/ICEBOX ideas may be lightweight; TODO+ must have a spec for the role loop.
    for slug, col in board.items():
        if slug not in specs:
            msg = (f"orphan link `[[{slug}]]` ({col}) with no specs/ file — "
                   "recovery: create the spec via `kanban.py new-task` or move the card back to BACKLOG")
            if col in TODO_PLUS_COLUMNS:
                rep.error("board", msg)
            else:
                rep.warn("board", msg)

    for slug, fm in specs.items():
        scope = f"specs/{slug}.md"
        col = board.get(slug)
        body = spec_bodies.get(slug, "")
        status = fm.get("status")
        itemtype = fm.get("itemType")
        is_task = itemtype in ("task", "subtask")

        # Reverse orphan: a spec with no card on any board -> WARN
        if col is None:
            rep.warn(scope, "spec has no card on any board — "
                            "add a card to the board or remove the spec")

        # Universally required sections (§8/§9) -> WARN. Checklists are checked by the review gate.
        for title in BASE_REQUIRED_SECTIONS:
            aliases = _REQUIRED_SECTION_ALIASES.get(title, [])
            if f"## {title}" not in body and not any(f"## {a}" in body for a in aliases):
                rep.warn(scope, f"missing required section `## {title}`")

        # Output / Artifacts: wikilink-only for active specs (§2).
        # done/icebox are excluded — legacy links in closed specs are not fixed retroactively.
        if status not in ("done", "icebox"):
            check_output_wikilinks(body, scope, rep)

        # §9: the `## Comments` section (trace of role self-review) is required for ACTIVE specs.
        # Archived (done/icebox) specs are legacy from before the comments system, not flagged, so as not to
        # flood the archive with noise. Catches accidental heading removal in a live cycle.
        if status not in ("done", "icebox") and "## Comments" not in body and "## Комментарии" not in body:
            rep.warn(scope, "missing required section `## Comments`")

        # Service sections: EN-primary (Comments, Changelog). RU — backward-compat.
        # Mixed RU+EN in one spec — WARN (migrate: run new-task or update manually).
        _RU_SERVICE_HDRS = {"Комментарии", "История изменений"}
        _EN_SERVICE_HDRS = {"Comments", "History", "Changelog", "Change Log"}
        body_headers = {ln[3:].strip() for ln in body.splitlines()
                        if ln.startswith("## ")}
        if body_headers & _RU_SERVICE_HDRS and body_headers & _EN_SERVICE_HDRS:
            rep.warn(scope, "mixed RU+EN service sections — use EN (Comments, Changelog)")

        # status <-> column desync
        if col and status and status != COLUMN_TO_STATUS[col]:
            rep.warn(scope, f"status `{status}` ≠ column `{col}` "
                            f"(expected `{COLUMN_TO_STATUS[col]}`) — run sync_properties.py")

        # Lost-DONE safeguard (§8 doneAt invariant): doneAt records the FACT of reaching
        # DONE and is not cleared by move_card on exit (DONE is terminal in ALLOWED_EXITS).
        # If doneAt is set but the card is not in DONE — a false/racy move likely
        # dropped a completed card. status↔column sync silently reconciles such a desync
        # (e.g. rework/REWORK looks consistent), hiding the loss. -> WARN.
        doneat = (fm.get("doneAt") or "").strip()
        if doneat and doneat != "null" and col is not None and col != "DONE":
            rep.warn(scope, f"doneAt={doneat}, but the card is in column `{col}` (not DONE) — "
                            "a lost DONE is possible (false/racy move): check "
                            "## Changelog for `move DONE → ...` without justification and move "
                            "the card back to DONE if the work is complete")

        # Stale: in-progress/review for longer than STALE_DAYS
        if status in STALE_STATUSES and fm.get("updatedAt"):
            try:
                d = dt.datetime.strptime(fm["updatedAt"][:10], "%Y-%m-%d").date()
                if (today - d).days > STALE_DAYS:
                    rep.warn(scope, f"stale: {status}, updatedAt {fm['updatedAt']} "
                                    f"(> {STALE_DAYS} days)")
            except ValueError:
                pass

        hist = extract_section(body, "Changelog", "История изменений")

        # Gates on review (ERROR): DoD and Review Checklist — for everyone (including the epic:
        # its Review Checklist confirms completion as intended); Test Checklist —
        # only task/subtask, when the task went through TESTING. A direct
        # IN PROGRESS/REWORK -> IN REVIEW is an explicit no-QA path for text,
        # research, and mechanical edits; there the Test Checklist doesn't gate review.
        if status == "review":
            check_checklist_gap(body, "Definition of Done", scope, rep)
            check_checklist_gap(body, "Review Checklist", scope, rep)
            if is_task:
                no_qa_review = (
                    "IN PROGRESS → IN REVIEW" in hist or
                    "REWORK → IN REVIEW" in hist
                )
                if not no_qa_review:
                    check_checklist_gap(body, "Test Checklist", scope, rep)
                if tasks_dir:
                    check_artifact_sources(body, tasks_dir, scope, rep, check_urls=check_urls)

        # Dependency: ready/backlog, but the dependency is not done -> WARN/ERROR
        dep_list = parse_yaml_list(fm.get("dependsOn", "[]"))
        block_list = parse_yaml_list(fm.get("blocks", "[]"))
        prose_deps, prose_blocks = dependency_section_links(body)
        relation_is_legacy = status in ("done", "icebox")

        if not relation_is_legacy:
            missing_yaml_deps = sorted(prose_deps - set(dep_list))
            for dep in missing_yaml_deps:
                msg = (
                    f"`## Dependencies` contains Depends on `[[{dep}]]`, but YAML "
                    f"`dependsOn` doesn't contain it — sync the metadata or "
                    "move the relation to `## Related` if it isn't blocking"
                )
                rep.error(scope, msg)

            missing_yaml_blocks = sorted(prose_blocks - set(block_list))
            for blocked in missing_yaml_blocks:
                msg = (
                    f"`## Dependencies` contains Blocks `[[{blocked}]]`, but YAML "
                    f"`blocks` doesn't contain it — sync the metadata or "
                    "move the relation to `## Related` if it isn't blocking"
                )
                rep.error(scope, msg)

        if status in ("ready", "backlog"):
            for dep in dep_list:
                if dep not in specs:
                    rep.error(scope, f"dependsOn `{dep}` — spec not found")
                elif specs[dep].get("status") != "done":
                    rep.warn(scope, f"in {status}, but dependsOn `{dep}` "
                                    f"is not done (status: {specs[dep].get('status')})")
            # backward-compat: WARN if prose has deps but YAML dependsOn is empty
            if not dep_list:
                deps_block = extract_section(body, "Dependencies", "Зависимости")
                for ln in deps_block.splitlines():
                    if "Зависит от" in ln and WIKILINK_RE.search(ln):
                        rep.warn(scope, "dependsOn is not set in YAML, but ## Зависимости "
                                        "contains a wikilink — run sync_properties.py --slug")
                        break

        for dep in dep_list:
            if dep not in specs:
                if status not in ("ready", "backlog"):
                    rep.error(scope, f"dependsOn `{dep}` — spec not found")
                continue
            dep_blocks = parse_yaml_list(specs[dep].get("blocks", "[]"))
            if slug not in dep_blocks:
                msg = (
                    f"dependsOn `{dep}` is not mirrored: `{dep}` must have "
                    f"`blocks: [..., {slug}, ...]` or the relation should not be blocking"
                )
                if relation_is_legacy:
                    rep.warn(scope, msg)
                else:
                    rep.error(scope, msg)

        for blocked in block_list:
            if blocked not in specs:
                rep.error(scope, f"blocks `{blocked}` — spec not found")
                continue
            blocked_deps = parse_yaml_list(specs[blocked].get("dependsOn", "[]"))
            if slug not in blocked_deps:
                msg = (
                    f"blocks `{blocked}` is not mirrored: `{blocked}` must have "
                    f"`dependsOn: [..., {slug}, ...]` or the relation should not be blocking"
                )
                if relation_is_legacy:
                    rep.warn(scope, msg)
                else:
                    rep.error(scope, msg)

        # `| agent |` signature in history -> WARN (§8: owner must be a concrete role)
        if re.search(r"\|\s*agent\s*\|", hist):
            rep.warn(scope, "the Changelog has a `| agent |` signature — "
                            "replace it with a concrete role (analyst/developer/...)")

        check_epic_tasks_section(slug, fm, body, specs, rep)

        # Explicit `## Related` links are non-blocking, but must be real and
        # bidirectional so agents do not rely on conversational memory.
        for target in sorted(related.get(slug, set())):
            if target == slug:
                rep.warn(scope, "## Related contains a link to itself")
            elif target not in specs:
                rep.error(scope, f"## Related links to `{target}`, but the spec was not found")
            elif slug not in related.get(target, set()):
                rep.error(scope, f"## Related `{target}` has no reciprocal link back to `{slug}`")

        # Semantic drift: the last history entry signals stage completion -> WARN
        check_semantic_drift(status, hist, scope, rep)

        if status == "done" and _enforce_done_chain_for(fm):
            if "IN PROGRESS → IN REVIEW" in hist or "REWORK → IN REVIEW" in hist:
                base_chain = ["BACKLOG → TODO", "TODO → IN PROGRESS"]
                if "REWORK → IN REVIEW" in hist:
                    base_chain += ["REJECTED → REWORK", "REWORK → IN REVIEW"]
                else:
                    base_chain += ["IN PROGRESS → IN REVIEW"]
            else:
                base_chain = DONE_CHAIN_BASE
            missing_base = [step for step in base_chain if step not in hist]
            has_valid_final = any(all(s in hist for s in finals) for finals in DONE_CHAIN_FINALS)
            if missing_base or not has_valid_final:
                missing = missing_base + ([] if has_valid_final else ["IN REVIEW → DONE (or IN REVIEW → UAT → DONE)"])
                rep.warn(scope, "DONE without a full history chain: "
                                f"missing {', '.join(missing)} — recovery: verify the task went through the full flow; "
                                "for legacy duplicates, add a documenting comment")

    # Epic lifecycle: children vs epic status (§4 SKILL.md)
    children_by_epic: dict[str, list[str]] = {}
    for s, f in specs.items():
        pid = f.get("parentId", "").strip()
        if pid and pid != "null" and pid in specs and specs[pid].get("itemType") == "epic":
            children_by_epic.setdefault(pid, []).append(s)
    for epic_slug, children in children_by_epic.items():
        epic_fm = specs[epic_slug]
        epic_status = epic_fm.get("status")
        epic_scope = f"specs/{epic_slug}.md"
        undone = [c for c in children if specs[c].get("status") != "done"]
        if epic_status == "done" and undone:
            rep.error(epic_scope,
                      f"epic is done, but {len(undone)} child tasks are not complete: "
                      f"{', '.join(f'[[{c}]]' for c in undone[:3])}"
                      + (" …" if len(undone) > 3 else ""))
        elif not undone and epic_status not in ("done", "icebox"):
            rep.warn(epic_scope,
                     f"all {len(children)} child tasks are done, but the epic is not closed "
                     f"(status: {epic_status}) — the documenter should move it to IN REVIEW")


def check_url(url: str, timeout: int = 5) -> tuple[bool, str]:
    """HEAD request to the URL. Returns (ok, description). Falls back to GET on 405."""
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "lint_board/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        if e.code == 405:  # HEAD not supported — try GET
            try:
                req2 = urllib.request.Request(url, method="GET",
                                              headers={"User-Agent": "lint_board/1.0"})
                with urllib.request.urlopen(req2, timeout=timeout) as r:
                    return True, f"HTTP {r.status}"
            except urllib.error.HTTPError as e2:
                return False, f"HTTP {e2.code}"
            except Exception as e2:
                return False, str(e2)
        return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def check_artifact_sources(spec_body: str, tasks_dir: Path, scope: str, rep: Report,
                           *, check_urls: bool = False) -> None:
    """For research artifacts: finds the artifact via wikilinks in Output / Artifacts
    and checks for the presence of the ## Sources section.

    The gate applies ONLY to artifacts tagged `исследования` (frontmatter `tags`).
    Non-research artifacts (audit, concept, process doc) are skipped — they legitimately have no
    external sources. There is no RESEARCH marker in the task spec (it's only in the card's
    display title), so the artifact's own tag is used as the signal.

    Logic:
    - Looks for wikilinks [[slug]] / [[slug|Title]] in the Output / Artifacts section.
    - Resolves slug → tasks/artifacts/<slug>.md (shortest path convention §2).
    - Skips an artifact without the `исследования` tag.
    - For a research artifact, checks the `## Источники` section:
        • no section -> ERROR
        • a source line without a URL (http/https) -> WARN
        • URL unreachable (only when check_urls=True) -> ERROR/WARN
    - If the wikilink doesn't resolve into tasks/artifacts/ — stays silent (not an artifact file).
    - If the Output section is missing or empty — stays silent (not every task has an artifact).
    """
    output_section = extract_section(spec_body, "Output / Artifacts", "Output / Артефакты")
    if not output_section.strip():
        return

    links = WIKILINK_RE.findall(output_section)  # list of slugs
    if not links:
        return

    artifacts_dir = tasks_dir / "artifacts"
    for slug in links:
        art_path = artifacts_dir / f"{slug}.md"
        if not art_path.is_file():
            continue  # wikilink not in artifacts/ — do not check sources
        art_text = art_path.read_text(encoding="utf-8")
        # ## Источники gate — only for research artifacts (tag `исследования`).
        # There's no RESEARCH marker in the task spec (it's only in the card's display title),
        # so the artifact's own tag is used as the signal. Non-research artifacts (audit, concept,
        # process doc) legitimately have no external sources and don't need the section.
        art_fm = parse_frontmatter(art_text) or {}
        if "исследования" not in parse_yaml_list(art_fm.get("tags", "[]")):
            continue
        sources_section = extract_section(art_text, "Источники")
        if not sources_section.strip():
            rep.error(scope, f"artifact `{slug}.md`: missing `## Источники` section — "
                             "add sources or redo the research")
            continue
        source_lines = [l.strip() for l in sources_section.splitlines()
                        if l.strip().startswith("-")]
        for line in source_lines:
            urls = re.findall(r"https?://[^\s\)\]\"']+", line)
            if not urls:
                rep.warn(scope, f"artifact `{slug}.md`: source without a URL — `{line[:80]}`")
                continue
            if check_urls:
                for url in urls:
                    ok, detail = check_url(url)
                    if not ok:
                        # timeout / connection error — network or anti-bot, not necessarily a 404 -> WARN
                        # an explicit HTTP 4xx/5xx — likely a real problem -> ERROR
                        if re.search(r"HTTP [45]\d\d", detail):
                            rep.error(scope, f"artifact `{slug}.md`: URL unreachable ({detail}) — `{url}`")
                        else:
                            rep.warn(scope, f"artifact `{slug}.md`: URL not verified ({detail}) — `{url}`")


# Output / Artifacts: a link to a result in storage — wikilink only (§2).
# Exception — external resources (PR, URL): a markdown link to http(s) or a bare URL.
OUTPUT_FILE_RE = re.compile(
    r"[\w\-./\\]+\.(?:md|txt|csv|tsv|xlsx?|pdf|docx?|pptx?|json|ya?ml|png|jpe?g|svg|html?|py|tsx?|jsx|js)\b",
    re.IGNORECASE,
)
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# Exception for a deliverable outside the tasks store (skill/repo source): a wikilink to it
# is not applicable. The explicit line marker `вне воркспейса` removes the wikilink requirement and
# keeps the exact file link (path/extension are allowed next to the marker).
# This is a deliberate opt-out: without the marker, any non-wikilink storage artifact is still ERROR.
SOURCE_MARKER_RE = re.compile(r"вне\s+воркспейса", re.IGNORECASE)


def check_output_wikilinks(body: str, scope: str, rep: Report) -> None:
    """ERROR if a link in `## Output / Artifacts` is not in wikilink format.

    Rule: all links to artifacts in storage must be `[[name|Title]]` only (§2).
    A plain path (`projects/.../file.md`) or a markdown link to a local file is forbidden.
    Exception — external resources: a markdown link to http(s) or a bare URL (PR, dashboard).
    Exception — a deliverable outside the store (skill/repo source): an item with the
    `вне воркспейса` marker is skipped (wikilink not applicable), the exact link is kept.
    """
    sec = extract_section(body, "Output / Artifacts", "Output / Артефакты")
    for raw in sec.splitlines():
        line = raw.strip()
        if not line.startswith("-"):
            continue
        item = re.sub(r"^-\s*(\[[ x]\]\s*)?", "", line)   # strip the bullet/checkbox
        item = re.sub(r"<!--.*?-->", "", item).strip()     # strip inline comments
        if not item:
            continue
        if SOURCE_MARKER_RE.search(item):
            continue                                       # deliverable outside the store (marker) — ok
        if WIKILINK_RE.search(item):
            continue                                       # already a wikilink — ok
        md = MD_LINK_RE.search(item)
        if md:                                             # markdown link
            if md.group(1).strip().lower().startswith(("http://", "https://")):
                continue                                   # external resource — ok
            rep.error(scope, f"in \"Output / Artifacts\" a local markdown link instead of "
                             f"a wikilink: `{item[:80]}` — use [[name|Title]] (§2)")
            continue
        if re.search(r"https?://", item):
            continue                                       # bare external URL — ok
        if OUTPUT_FILE_RE.search(item) or "/" in item or "\\" in item:
            rep.error(scope, f"in \"Output / Artifacts\" a link not in wikilink format: "
                             f"`{item[:80]}` — use [[name|Title]] (§2); "
                             f"markdown/URL are allowed only for external resources")


def extract_section(body: str, title: str, *aliases: str) -> str:
    """Returns the text of the `## <title> ...` section up to the next `## `.
    `aliases` — additional section names (for backward-compat with RU headings)."""
    lines = body.splitlines()
    candidates = (title,) + aliases
    out, capture = [], False
    for ln in lines:
        if ln.startswith("## "):
            heading_text = ln[3:].strip().lower()
            capture = any(c.lower() == heading_text for c in candidates)
            continue
        if capture:
            out.append(ln)
    return "\n".join(out)


# --- Entry point -------------------------------------------------------------

def resolve_tasks_dir(root: Path) -> Path:
    return root if root.name == "tasks" else root / "tasks"


def main() -> int:
    # __doc__ as description + RawDescription => `--help` prints the full list of rules
    # and gates: the script is self-documenting, no need to duplicate rules in SKILL.md.
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("--strict", action="store_true",
                    help="exit with code 1 even if there are only WARNs")
    ap.add_argument("--slug", metavar="SLUG",
                    help="check only this spec + its card on the board; "
                         "other specs and board-checks are skipped")
    ap.add_argument("--check-urls", action="store_true",
                    help="check URL reachability in RESEARCH task artifacts "
                         "(makes HTTP requests; disabled by default)")
    args = ap.parse_args()

    tasks = resolve_tasks_dir(Path(args.workspace).expanduser())
    if not tasks.is_dir():
        print(f"✗ tasks/ folder not found: {tasks}", file=sys.stderr)
        return 2

    slug_filter: str | None = args.slug.strip() if args.slug else None

    rep = Report()
    board: dict[str, str] = {}
    board_count: int = 0
    specs: dict[str, dict] = {}
    spec_bodies: dict[str, str] = {}

    specs_dir = tasks / "specs"

    # When --slug is given, try to load only the board matching the spec's project.
    # Fall back to full glob if spec not found or derived board file not found.
    _single_board_loaded = False
    if slug_filter:
        spec_path = specs_dir / f"{slug_filter}.md"
        if spec_path.is_file():
            try:
                import re as _re
                _spec_text = spec_path.read_text(encoding="utf-8")
                _fm_match = _re.match(r"^---\s*\n(.*?)\n---", _spec_text, _re.DOTALL)
                _flow_id = None
                if _fm_match:
                    for _line in _fm_match.group(1).splitlines():
                        if _line.startswith("flowId:"):
                            _flow_id = _line.split(":", 1)[1].strip()
                            break
                if _flow_id:
                    _project = _flow_id.split("/")[0]
                    _board_file = tasks / f"{_project}.md"
                    if _board_file.is_file():
                        _board_text = _board_file.read_text(encoding="utf-8")
                        if "kanban-plugin: board" in _board_text:
                            board_count += 1
                            board.update(parse_board(_board_text))
                            # Also scan archive if exists
                            _arc_file = tasks / f"{_project}-archive.md"
                            if _arc_file.is_file():
                                _arc_text = _arc_file.read_text(encoding="utf-8", errors="replace")
                                if "kanban-plugin: board" in _arc_text:
                                    for _s in parse_board(_arc_text):
                                        if _s not in board:
                                            board[_s] = "DONE"
                            _single_board_loaded = True
                    if not _single_board_loaded:
                        print(f"WARN: board file for project '{_project}' not found; falling back to full glob",
                              file=sys.stderr)
            except Exception:
                pass  # fall through to full glob

        if not _single_board_loaded and not spec_path.is_file():
            print(f"WARN: spec file not found for slug '{slug_filter}'; falling back to full glob",
                  file=sys.stderr)

    if not _single_board_loaded:
        for md in sorted(tasks.glob("*.md")):
            if md.name == "SKILL.md" or md.stem.endswith("-archive"):
                continue
            text = md.read_text(encoding="utf-8")
            if "kanban-plugin: board" in text:
                board_count += 1
                # With --slug: skip board-level checks (format, columns, settings) —
                # they only apply to a full workspace scan. Cards are always read (needed for cross-checks).
                if slug_filter:
                    board.update(parse_board(text))
                else:
                    board.update(lint_board_file(md, text, rep))

        # Archived board slugs → suppress orphan WARN for specs whose cards moved to archive.
        # Archive boards are not linted (format checks skipped) — only card slugs are collected.
        for arc in sorted(tasks.glob("*-archive.md")):
            arc_text = arc.read_text(encoding="utf-8", errors="replace")
            if "kanban-plugin: board" in arc_text:
                for slug in parse_board(arc_text):
                    if slug not in board:
                        board[slug] = "DONE"  # archived; treated as done for orphan check

    scoped_slugs = [slug_filter] if slug_filter else []
    if specs_dir.is_dir():
        if slug_filter:
            candidate_slugs = []
            seen_slugs = set()
            queue = [slug_filter]
            while queue:
                slug = queue.pop(0)
                if slug in seen_slugs:
                    continue
                seen_slugs.add(slug)
                candidate_slugs.append(slug)
                md = specs_dir / f"{slug}.md"
                if not md.is_file():
                    continue
                text = md.read_text(encoding="utf-8")
                for related_slug in sorted(related_links(text)):
                    if related_slug not in seen_slugs:
                        queue.append(related_slug)
                fm = parse_frontmatter(text) or {}
                dep_slugs = set(parse_yaml_list(fm.get("dependsOn", "[]")))
                dep_slugs.update(parse_yaml_list(fm.get("blocks", "[]")))
                prose_deps, prose_blocks = dependency_section_links(text)
                dep_slugs.update(prose_deps)
                dep_slugs.update(prose_blocks)
                for dep_slug in sorted(dep_slugs):
                    if dep_slug not in seen_slugs:
                        queue.append(dep_slug)
                if fm.get("itemType") == "epic":
                    for child_slug in sorted(epic_task_links(text)):
                        if child_slug not in seen_slugs:
                            queue.append(child_slug)
            candidates = [specs_dir / f"{slug}.md" for slug in candidate_slugs]
            scoped_slugs = candidate_slugs
        else:
            candidates = sorted(specs_dir.glob("*.md"))
        for md in candidates:
            if not md.is_file():
                print(f"✗ Spec not found: {md}", file=sys.stderr)
                return 2
            text = md.read_text(encoding="utf-8")
            fm = lint_spec_file(md, text, rep)
            if fm is not None:
                specs[md.stem] = fm
                spec_bodies[md.stem] = text

    # With --slug: pass cross_checks a board narrowed to the checked closure:
    # the main slug + explicit ## Related slugs. This removes orphan noise from other
    # cards, while still checking bidirectional links without false orphan WARNs.
    cross_board = {slug: board[slug] for slug in scoped_slugs if slug in board} if slug_filter else board
    cross_board = cross_board if cross_board else (
        {} if slug_filter else board
    )
    cross_checks(cross_board, specs, spec_bodies, rep, tasks_dir=tasks,
                 check_urls=args.check_urls)

    # --- report output ---
    REMINDER = (
        "  ⓘ Role cycle (SKILL.md §9):\n"
        "    1) BEFORE work — read agents/<role>.md (current role's checklist);\n"
        "    2) BEFORE every transition and on YAML changes — run check.py --slug\n"
        "       and fix your findings before handing off. After comments/prose edits\n"
        "       a separate check.py is not required."
    )
    slug_info = f" [slug={slug_filter}]" if slug_filter else ""
    print(f"\n  Obsidian Kanban linter — {tasks}{slug_info}")
    print(f"  Boards: {board_count} · cards: {len(board)} · specs: {len(specs)}\n")
    if not rep.items:
        print("  ✅ No violations found.\n")
        return 0
    for sev, scope, msg in sorted(rep.items, key=lambda x: (x[0] != "ERROR", x[1])):
        mark = "✗" if sev == "ERROR" else "▲"
        print(f"  {mark} [{sev:5}] {scope}: {msg}")
    print(f"\n  Total: {rep.errors} ERROR · {rep.warns} WARN\n")
    # §9 banner — only on ERROR (where "fix your findings" is actionable); duplicates SKILL.md,
    # so it's not printed in the clean case or when there are only WARNs (token savings).
    if rep.errors:
        print(REMINDER + "\n")

    if rep.errors or (args.strict and rep.warns):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
