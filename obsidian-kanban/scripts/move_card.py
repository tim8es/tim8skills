#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""move_card.py — deterministic card transfer between board columns.

Replaces manual string editing of the board — a source of errors (phantom columns, duplicates,
broken indentation). Moves card <slug> to column <COLUMN>: moves its tags
line together with it, sets the checkbox (`[x]` in DONE, otherwise `[ ]`), when moved to DONE
stamps the completion date `✅ <date+time>` onto the tags line (idempotently), syncs
`status` in specs/<slug>.md, and rebuilds the board in the canonical format (§6).

After a successful move, prints to stdout the checklist for the TARGET column's role
(=== ROLE: <name> (<column>) === + a trimmed role checklist with the `## Method` section
removed, with a pointer to the full agents/<role>.md file) — role instructions arrive in the
agent's context automatically, without a separate file read (§9: hard stop = execute the printed
checklist). For IN PROGRESS, the `RESEARCH:` prefix in the card title routes to
researcher.md instead of developer.md. Column↔role mapping is a single dictionary,
workflow.COLUMN_TO_ROLE. A missing role file — WARN to stderr, the move is not broken.
`--dry-run` simulates the move without writing.

Format rules and COLUMN_TO_STATUS are reused from lint_board.py (single source).
The `owner` field holds the task's author and is not changed on transitions.

Usage:
    python scripts/move_card.py <WORKSPACE_ROOT> <slug> <COLUMN> [--dry-run]
    COLUMN: BACKLOG | ICEBOX | TODO | IN PROGRESS | BLOCKED | TESTING | IN REVIEW | UAT | REJECTED | REWORK | DONE
    Shell-safe aliases (workflow.COLUMN_ALIASES): IN_PROGRESS, IN-PROGRESS, IN_REVIEW, IN-REVIEW, INREVIEW

Exit codes: 0 — move done/simulated; 1 — card not found / unknown column.
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import argparse
import datetime as dt
import re
from pathlib import Path

import lint_board as lb  # same scripts/ folder -> shared COLUMN_TO_STATUS, CARD_RE, WIKILINK_RE
import add_comment as acm  # reuse insert_into_section / sort_section for auto-logging transitions
import kanban_utils as ku
import hooks

COLUMN_TO_STATUS = lb.COLUMN_TO_STATUS
COLUMN_ORDER = lb.COLUMN_ORDER
CARD_RE = lb.CARD_RE
WIKILINK_RE = lb.WIKILINK_RE
parse_board = ku.parse_board
emit_board = ku.emit_board

_PLACEHOLDER = "<SCRIPT_PREFIX>/"
_CANONICAL = "obsidian-kanban/scripts/"


def _substitute_script_prefix(text: str, prefix: str) -> str:
    # ORDER MATTERS: resolve the legacy literal FIRST. Otherwise the `<SCRIPT_PREFIX>/`
    # placeholder would first become, e.g., `skills/obsidian-kanban/scripts/`, and the next
    # legacy substitution would re-match the `obsidian-kanban/scripts/` substring INSIDE the
    # result → a doubled prefix `skills/skills/...`. On a canonical file this step is a no-op (no literal present).
    if prefix != _CANONICAL:
        text = text.replace(_CANONICAL, prefix)
    return text.replace(_PLACEHOLDER, prefix)


# Timestamp fields for transitions after an explicit start.
# `startedAt` is set by the analyst via `kanban.py tags --start today`, and is not
# derived from moving the card between columns.
# Canon is lint_board_rules.COLUMN_TO_TIMESTAMP (re-exported via ku); there is no local copy.
COLUMN_TO_TIMESTAMP = ku.COLUMN_TO_TIMESTAMP


def transition_actor(src_col: str, card_title: str | None = None) -> str:
    """Actor label for an automatic transition changelog entry.

    The source-column role is the role that is allowed to initiate the move, so
    it is more informative than the previous generic `move` actor while keeping
    the existing changelog row shape intact.
    """
    return ku.role_for_column(src_col, card_title) or "move"


def card_slug(block) -> str | None:
    if not block or not CARD_RE.match(block[0]):
        return None
    mm = WIKILINK_RE.search(block[0])
    return mm.group(1).strip() if mm else None


_TITLE_RE = re.compile(r"\[\[[^\]|]+\|((?:(?!\]\]).)*)\]\]")


def card_title(block) -> str | None:
    """Card display title from the wikilink `[[slug|Title]]` (for RESEARCH: detection)."""
    if not block:
        return None
    m = _TITLE_RE.search(block[0])
    return m.group(1).strip() if m else None


# Single compaction implementation lives in workflow.compact_text (leaf module),
# exposed via kanban_utils. Aliased here so the historical `_compact_text` name and
# the compact behaviour stay identical across move_card / role_prompt / hooks.
_compact_text = ku.compact_text


def print_role_checklist(column: str, title: str | None, workspace: "Path | None" = None,
                         compact: bool = False):
    """Prints the target column's role checklist to stdout — the instructions arrive in the
    agent's context automatically (§9: hard stop = execute the printed checklist).
    workspace is passed to compute the actual SCRIPT_PREFIX (§10, §1).
    compact=True — print only headings and checklist lines, without command blocks.
    A missing role file — WARN, the move is not broken."""
    name, role, text = ku.role_checklist(column, title)
    if text is None:
        if role:
            print(f"▲ WARN: role file agents/{role}.md not found — "
                  f"read the role checklist for {column} manually.", file=sys.stderr)
        return
    print(f"\n=== РОЛЬ: {name} ({column}) ===")
    if workspace is not None:
        prefix = ku.detect_script_prefix(workspace)
        print(f"⚙️  SCRIPT_PREFIX: {prefix}  (use it in the commands below)")
        text = _substitute_script_prefix(text, prefix)
    if compact:
        text = _compact_text(text)
    print("Hard stop (§9): execute this checklist in full before doing anything else.\n")
    print(text.rstrip())
    print("\n=== КОНЕЦ ЧЕКЛИСТА ===")


def set_checkbox(block, done: bool):
    block = list(block)
    block[0] = re.sub(r"^(\s*- \[)[ xX](\])",
                      lambda m: m.group(1) + ("x" if done else " ") + m.group(2),
                      block[0], count=1)
    return block


def sort_done(cols):
    """Sorts the DONE column by completion date ✅ (newest first). No date — goes last.
    The key is the canonical ku.done_sort_key (board_io); there is no local copy of the regex/function."""
    cols["DONE"] = sorted(cols["DONE"], key=ku.done_sort_key, reverse=True)


def stamp_done(block):
    """Stamps the completion date+time `✅ YYYY-MM-DD HH:mm` on the tags line when moved to DONE.
    Idempotent: if `✅` is already present, it doesn't duplicate it. If there's no tags line, it creates one.
    The time lets sort_done() correctly sort several cards within the same day.
    `✅` is the last tag in the canonical order §7."""
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    block = list(block)
    tag_idx = next((i for i, l in enumerate(block) if l.startswith("\t")), None)
    if tag_idx is None:
        block.append(f"\t✅ {now}")
    elif "✅" not in block[tag_idx]:
        block[tag_idx] = block[tag_idx].rstrip() + f" ✅ {now}"
    return block


def sync_spec_status(specs_dir: Path, slug: str, status: str, dry: bool,
                     src_col: str | None = None, dst_col: str | None = None,
                     card_title: str | None = None):
    f = specs_dir / f"{slug}.md"
    if not f.is_file():
        return None
    txt = f.read_text(encoding="utf-8")
    new = re.sub(r"^(status:\s*).*$", rf"\g<1>{status}", txt, count=1, flags=re.M)
    stamp = ku.now_stamp()
    new = re.sub(r"^(updatedAt:\s*).*$", rf"\g<1>{stamp}", new, count=1, flags=re.M)
    # timestamp field on first entry into the status (idempotent: doesn't overwrite an already-set value)
    if dst_col and dst_col in COLUMN_TO_TIMESTAMP:
        ts_field = COLUMN_TO_TIMESTAMP[dst_col]
        existing = re.search(rf"^{ts_field}:\s*(.+)$", new, re.M)
        if existing and existing.group(1).strip() in ("null", ""):
            # the field exists but is null — set the value
            new = re.sub(rf"^({ts_field}:\s*).*$", rf"\g<1>{stamp}", new, count=1, flags=re.M)
        elif not existing:
            # field doesn't exist at all — add it after updatedAt
            new = re.sub(r"^(updatedAt:.+)$", rf"\1\n{ts_field}: {stamp}", new, count=1, flags=re.M)
    # auto-log the transition into the Changelog (deterministic event log)
    if src_col and dst_col:
        entry = f"{ku.hist_stamp()} | {transition_actor(src_col, card_title)} | {src_col} → {dst_col}"
        new = acm.insert_into_section(new, "Changelog", entry)
        new = acm.sort_section(new, "Changelog")
    if new != txt and not dry:
        # The same hardened writer as the board (_write_board_verified): transient-OSError
        # retry + best-effort fsync. A bare write_text used to raise a traceback on an Obsidian lock/transient
        # Windows OSError AFTER the card move was already confirmed → board↔spec desync (RES-001).
        ku._fsync_write(f, new)
    # warn if moving to REWORK and Test/Review Checklist still has [x] from previous iteration
    if dst_col == "REWORK" and not dry:
        lines_new = new.split("\n")
        checked = 0
        in_target = False
        for line in lines_new:
            if re.match(r"^## (Test Checklist|Review Checklist|Тестовый чеклист|Чеклист ревью)", line):
                in_target = True
            elif line.startswith("## "):
                in_target = False
            if in_target and re.match(r"^\s*-\s+\[x\]", line):
                checked += 1
        if checked > 0:
            print(f"⚠️  WARN: {checked} Test/Review Checklist item(s) remain [x] from previous "
                  f"iteration — tester must re-verify all before accepting")
    return new != txt


def _write_board_verified(path: Path, content: str, slug: str, column: str, *, retries: int = 3) -> bool:
    """Writes board with fsync + verify-loop (Windows buffered-write guard).
    Re-reads and confirms card is in expected column; retries on mismatch.
    Returns True if the write was confirmed, False otherwise."""
    for attempt in range(retries):
        ku._fsync_write(path, content)  # shared writer: transient-OSError retry + best-effort fsync
        v_cols, _ = parse_board(path.read_text(encoding="utf-8"))
        if any(card_slug(b) == slug for b in v_cols.get(column, [])):
            return True
        if attempt < retries - 1:
            print(f"⚠️  WARN: write verify attempt {attempt + 1}/{retries} failed — retrying",
                  file=sys.stderr)
    print(f"⚠️  WARN: board write [{slug}] → {column} unconfirmed after {retries} attempts; "
          "run move again if board looks stale", file=sys.stderr)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("slug", help="card slug (without [[]])")
    ap.add_argument("column", help="target column, e.g. 'IN REVIEW'")
    ap.add_argument("--board", default=None, help="board file name, if there are several")
    ap.add_argument("--dry-run", action="store_true", help="show the result without writing")
    ap.add_argument("--full", action="store_true",
                    help="print the full text of the role checklist, including command blocks (by default only headings and checklist lines are printed)")
    args = ap.parse_args()
    compact = not args.full

    column = ku.normalize_column(args.column)
    if column not in COLUMN_TO_STATUS:
        print(f"✗ Unknown column: {args.column!r}. Valid: {', '.join(COLUMN_ORDER)}",
              file=sys.stderr)
        return 1

    workspace_root = Path(args.workspace).expanduser()
    tasks = lb.resolve_tasks_dir(workspace_root)
    if not tasks.is_dir():
        print(f"✗ tasks/ folder not found: {tasks}", file=sys.stderr)
        return 1

    # Resolve the board before locking: find_boards() excludes *-archive.md and detects duplicate slugs
    # on several active boards (→ a clear error requiring --board).
    board_file, err = ku.resolve_board_for_slug(tasks, args.slug, board_hint=args.board)
    if err:
        print(err, file=sys.stderr)
        return 1

    with ku.board_lock(tasks):
        target_done = column == "DONE"
        text = board_file.read_text(encoding="utf-8")
        cols, settings = parse_board(text)
        src_col = next((c for c in COLUMN_ORDER
                        for b in cols[c] if card_slug(b) == args.slug), None)
        if src_col is None:
            # Race: the card disappeared after resolve and before the lock (extremely rare)
            print(f"✗ Card [[{args.slug}]] not found on board {board_file.name}.",
                  file=sys.stderr)
            return 1

        block = next(b for b in cols[src_col] if card_slug(b) == args.slug)
        title = card_title(block)
        if src_col == column:
            print(f"ⓘ Card [[{args.slug}]] is already in column {column} — nothing to do.")
            return 0

        hook_result = hooks.before_move(tasks, args.slug, src_col, column, title=title)
        if not hook_result.ok:
            print(hook_result.render(), file=sys.stderr)
            return 1

        cols[src_col] = [b for b in cols[src_col] if card_slug(b) != args.slug]
        moved = set_checkbox(block, target_done)
        if target_done:
            moved = stamp_done(moved)
        cols[column].append(moved)
        sort_done(cols)
        new_board = emit_board(cols, settings)

        status = COLUMN_TO_STATUS[column]
        specs_dir = tasks / "specs"
        if args.dry_run:
            print(f"[dry-run] {args.slug}: {src_col} → {column}; "
                  f"spec status → {status}")
            print("--- board after the move (column fragment) ---")
            print("\n".join(["## " + column] + ["  " + l for b in cols[column] for l in b]))
            return 0

        board_confirmed = _write_board_verified(board_file, new_board, args.slug, column)
        if not board_confirmed:
            print(f"✗ ERROR: board write unconfirmed for {args.slug} → {column}; "
                  "spec NOT synced to avoid divergence — retry the move", file=sys.stderr)
            return 1
        try:
            synced = sync_spec_status(specs_dir, args.slug, status, dry=False,
                                      src_col=src_col, dst_col=column, card_title=title)
        except OSError as e:
            # The board has already been moved and verified; the spec didn't sync (Obsidian lock /
            # persistent OSError after retry). Don't crash with a traceback — a loud WARN with recovery
            # so the agent re-syncs the spec instead of leaving it silently desynced (RES-001).
            print(f"⚠️  WARN: card [{args.slug}] moved {src_col} → {column} on the board, "
                  f"but reading/writing the spec failed ({e}). The spec is NOT synced. "
                  f"Close the file in Obsidian and run: kanban.py check \".\" --slug {args.slug}",
                  file=sys.stderr)
            synced = False

        # Print the role checklist first (§9 self-heal on truncation — critical content first),
        # then the success line and resume_packet — they are less critical and can be lost on truncation.
        role = ku.role_for_column(column, title)
        print_role_checklist(column, title, workspace=workspace_root, compact=compact)
        msg = f"✅ {args.slug}: {src_col} → {column}"
        msg += f"; spec status → {status}" if synced else "; spec not found/already synced."
        print(msg)
        print(hooks.after_move(tasks, args.slug, src_col, column, title=title, role=role).rstrip())
        if column == "DONE":
            prefix = ku.detect_script_prefix(workspace_root)
            print(ku.format_next_task(ku.find_next_task(tasks), script_prefix=prefix))
        return 0


if __name__ == "__main__":
    sys.exit(main())
