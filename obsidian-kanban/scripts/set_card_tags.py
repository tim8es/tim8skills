#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""set_card_tags.py — deterministic editing of a card's emoji tags line on the board.

Closes out the last "manual" operation on the board: the analyst records `🛫`, the planner
sets `⏳`, and manual editing of the tags line was a §6/§7 format risk. The script rebuilds
the tags line of an existing card
in the CANONICAL order §7 (`➕ → 🛫 → 📅 → ⏳ → priority → 🔁 → ✅`), preserving unspecified tags
and overwriting the ones given, then rebuilds the board in the canonical format (§6).
An explicit `--start` also syncs YAML `startedAt` in specs/<slug>.md: `today` sets
the exact time of the first work start, and an existing non-null value is not overwritten.
`--start` with an explicit date (not `none`) is rejected for a card with `status: icebox`:
for a frozen task, `🛫`/`startedAt` = the actual work start, not the return date;
use `--reminder` for the expected unfreeze date. `--start none` is allowed for icebox
(to remove an erroneous `🛫`).

`--reminder` mutates ONLY the YAML `reminder` field in specs/<slug>.md (a one-off return date
from ICEBOX / reminder; surfaced by `check_reminders.py` during onboarding). `reminder` is not
a board emoji tag — `--reminder` does not touch the card's tags line. Unlike `startedAt`,
`reminder` may be freely overwritten/shifted (no preserve logic). `none` clears it to `null`.

`--title` — canonical card rename: changes the alias in the wikilink
`[[slug|Title]]` on the first line of the board card IN PLACE (column, position in
the column, and the tags line are untouched), synchronously updates the spec H1 (`# 📋 <Title>`)
and `updatedAt`, adds an entry to `## Changelog`. Does not change the slug (spec file name) —
only the display title. Replaces the remove-card + add-card + tags --start chain,
which lost the column position and creation date on a late rename.

Format, board parser, and serializer are reused from move_card.py / add_card.py /
lint_board.py (single source of truth). No dependencies (stdlib).

Usage:
    python scripts/set_card_tags.py <WORKSPACE_ROOT> <slug> [options]

Options (a value of `none` or `-` removes the tag; `today` for dates = today):
    --created <DATE>          creation date ➕
    --start <DATE|today>      start date 🛫 (rejected for icebox, except none)
    --reminder <DATE|none>    the spec's YAML reminder (return date from ICEBOX / reminder;
                              not a board emoji tag; none → null)
    --due <DATE|today>        deadline 📅
    --estimate <Nh|Nd>        duration estimate ⏳
    --done <DATE|today>       completion date ✅
    --priority high|medium|low|none  priority 🟥/🟨/🟩 (none removes it)
    --recurring / --no-recurring  repeat 🔁
    --title "<Title>"         canonical rename: board card alias
                               + spec H1 + Changelog (does not change the slug/spec file)
    --board <name.md>         board file name, if there are several
    --dry-run                 show the result without writing

Exit codes: 0 — applied/simulated; 1 — card/board not found, ambiguity.
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import datetime as dt
import re
from pathlib import Path

import lint_board as lb   # resolve_tasks_dir
import move_card as mc    # parse_board / emit_board / card_slug / card_title
import add_card as ac     # slug_on_board
import add_comment as acm  # insert_into_section / sort_section (Changelog entry)
import kanban_utils as ku  # resolve_board

CLEAR = {"none", "-", ""}

parse_tag_line = ku.parse_tag_line
build_tag_line = ku.build_tag_line

# `[[slug|Title]]` — replaces only the alias text between `|` and `]]`, preserving the slug and
# brackets. The format is guaranteed by add_card.py (all cards are created with an alias).
_CARD_TITLE_RE = re.compile(r"(\[\[[^\]|]+\|)((?:(?!\]\]).)*)(\]\])")
# Fallback for a hypothetical card without an alias `[[slug]]` (add_card.py doesn't create one,
# but we guard against manual edits/an old board) — appends an alias.
_CARD_NO_ALIAS_RE = re.compile(r"\[\[([^\]|]+)\]\]")
# Spec H1: `# <emoji> <Title>` (emoji = itemType marker §4, e.g. 📋/🗃️/✅).
_H1_RE = re.compile(r"^(#\s*\S+\s+).*$", re.M)


def set_card_title_line(line: str, new_title: str) -> str:
    """Replaces the card alias in the wikilink of the block's first line, without touching slug/checkbox."""
    new_line, n = _CARD_TITLE_RE.subn(lambda m: m.group(1) + new_title + m.group(3), line, count=1)
    if n:
        return new_line
    return _CARD_NO_ALIAS_RE.sub(lambda m: f"[[{m.group(1)}|{new_title}]]", line, count=1)


def sync_spec_title(tasks: Path, slug: str, old_title: str | None, new_title: str,
                    *, dry_run: bool = False) -> str | None:
    """Synchronize spec H1 heading + `## Changelog` entry for `--title` retitle.

    H1 keeps the itemType emoji prefix (`# 📋 <title>`) intact — only the title text
    after it is replaced. Does not touch slug/filename: retitle is display-name only.
    """
    spec = tasks / "specs" / f"{slug}.md"
    if not spec.is_file():
        return None
    text = spec.read_text(encoding="utf-8")
    new_text, n = _H1_RE.subn(lambda m: m.group(1) + new_title, text, count=1)
    if not n or new_text == text:
        return None

    stamp = ku.now_stamp()
    new_text = re.sub(r"^(updatedAt:\s*).*$", rf"\g<1>{stamp}", new_text, count=1, flags=re.M)
    old_display = old_title or "?"
    entry = f"{stamp} | tags | retitle: «{old_display}» → «{new_title}»"
    new_text = acm.insert_into_section(new_text, "Changelog", entry)
    new_text = acm.sort_section(new_text, "Changelog")

    if not dry_run:
        spec.write_text(new_text, encoding="utf-8", newline="\n")
    return f"{slug}: title → {new_title}"


def _date_val(v: str) -> str:
    return dt.date.today().isoformat() if v.strip().lower() == "today" else v.strip()


def apply_overrides(tags: dict, args) -> dict:
    out = dict(tags)

    def set_or_clear(key, raw, transform=lambda x: x):
        if raw is None:
            return
        if raw.strip().lower() in CLEAR:
            out.pop(key, None)
        else:
            out[key] = transform(raw)

    set_or_clear("created", args.created, _date_val)
    set_or_clear("start", args.start, _date_val)
    set_or_clear("due", args.due, _date_val)
    set_or_clear("estimate", args.estimate, lambda x: x.strip())
    set_or_clear("done", args.done, _date_val)

    if args.priority is not None:
        if args.priority == "none":
            out.pop("priority", None)
        else:
            out["priority"] = args.priority
    if args.recurring:
        out["recurring"] = True
    if args.no_recurring:
        out.pop("recurring", None)
    return out


def sync_spec_started_at(tasks: Path, slug: str, raw_start: str | None, *, dry_run: bool = False) -> str | None:
    """Synchronize YAML `startedAt` for explicit start-tag changes.

    The board tag stores a date (`🛫 YYYY-MM-DD`); the spec stores the precise
    first-start timestamp. Existing non-null values are preserved so a later tag
    cleanup cannot rewrite the historical start moment.
    """
    if raw_start is None:
        return None
    spec = tasks / "specs" / f"{slug}.md"
    if not spec.is_file():
        return None

    raw = raw_start.strip()
    clear = raw.lower() in CLEAR
    text = spec.read_text(encoding="utf-8")
    existing = re.search(r"^startedAt:\s*(.*)$", text, re.M)
    current = existing.group(1).strip() if existing else ""

    if clear:
        value = "null"
    elif current and current != "null":
        return None
    elif raw.lower() == "today":
        value = ku.now_stamp()
    else:
        value = _date_val(raw)

    if existing:
        new = re.sub(r"^(startedAt:\s*).*$", rf"\g<1>{value}", text, count=1, flags=re.M)
    else:
        new = re.sub(r"^(updatedAt:.+)$", rf"\1\nstartedAt: {value}", text, count=1, flags=re.M)
        if new == text:
            new = text.rstrip() + f"\nstartedAt: {value}\n"

    if new == text:
        return None

    stamp = ku.now_stamp()
    new = re.sub(r"^(updatedAt:\s*).*$", rf"\g<1>{stamp}", new, count=1, flags=re.M)
    if not dry_run:
        spec.write_text(new, encoding="utf-8", newline="\n")
    return f"{slug}: startedAt → {value}"


_REMINDER_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def sync_spec_reminder(tasks: Path, slug: str, raw_reminder: str | None, *, dry_run: bool = False) -> str | None:
    """Synchronize YAML `reminder` for `--reminder` changes.

    `reminder` is a spec-only field (not a board emoji tag), so this touches only
    specs/<slug>.md, never the board tag line. Unlike `startedAt`, an existing value
    may be freely overwritten/shifted (a return date can move), so there is no
    non-null-preserve guard. `none`/`-`/`` clears to `null`; an explicit value must be
    a `YYYY-MM-DD` one-shot date (`today` is meaningless for a return/reminder date and
    is not accepted). Invalid input aborts the process with exit 1.
    """
    if raw_reminder is None:
        return None
    spec = tasks / "specs" / f"{slug}.md"
    if not spec.is_file():
        return None

    raw = raw_reminder.strip()
    if raw.lower() in CLEAR:
        value = "null"
    elif _REMINDER_DATE_RE.match(raw):
        try:
            dt.date.fromisoformat(raw)
        except ValueError:
            print(f"✗ Invalid --reminder date: {raw!r} (expected YYYY-MM-DD or none)",
                  file=sys.stderr)
            sys.exit(1)
        value = raw
    else:
        print(f"✗ Invalid --reminder date: {raw!r} (expected YYYY-MM-DD or none)",
              file=sys.stderr)
        sys.exit(1)

    text = spec.read_text(encoding="utf-8")
    existing = re.search(r"^reminder:\s*(.*)$", text, re.M)
    if existing:
        new = re.sub(r"^(reminder:\s*).*$", rf"\g<1>{value}", text, count=1, flags=re.M)
    else:
        new = re.sub(r"^(updatedAt:.+)$", rf"\1\nreminder: {value}", text, count=1, flags=re.M)
        if new == text:
            new = text.rstrip() + f"\nreminder: {value}\n"

    if new == text:
        return None

    stamp = ku.now_stamp()
    new = re.sub(r"^(updatedAt:\s*).*$", rf"\g<1>{stamp}", new, count=1, flags=re.M)
    if not dry_run:
        spec.write_text(new, encoding="utf-8", newline="\n")
    return f"{slug}: reminder → {value}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("slug", help="card slug (without [[]])")
    ap.add_argument("--created", default=None, help="creation date ➕ (DATE|today|none)")
    ap.add_argument("--start", default=None, help="start date 🛫 (DATE|today|none)")
    ap.add_argument("--reminder", default=None,
                    help="the spec's YAML reminder: return date/reminder (DATE|none); "
                         "not a board emoji tag")
    ap.add_argument("--due", default=None, help="deadline 📅 (DATE|today|none)")
    ap.add_argument("--estimate", default=None, help="estimate ⏳ (e.g. 2h, 3d, none)")
    ap.add_argument("--done", default=None, help="completion date ✅ (DATE|today|none)")
    ap.add_argument("--priority", default=None, choices=["high", "medium", "low", "none"],
                    help="priority 🟥/🟨/🟩 (none removes it)")
    ap.add_argument("--recurring", action="store_true", help="add 🔁")
    ap.add_argument("--no-recurring", action="store_true", help="remove 🔁")
    ap.add_argument("--title", default=None,
                    help="new card title: board alias + spec H1 + Changelog "
                         "(does not change the slug/spec file)")
    ap.add_argument("--board", default=None, help="board file name, if there are several")
    ap.add_argument("--dry-run", action="store_true", help="show the result without writing")
    args = ap.parse_args()

    if args.title is not None and ("]]" in args.title or "|" in args.title):
        print(f"✗ --title cannot contain `|` or `]]` (breaks the board's wikilink format): "
              f"{args.title!r}", file=sys.stderr)
        return 1

    tasks = lb.resolve_tasks_dir(Path(args.workspace).expanduser())
    if not tasks.is_dir():
        print(f"✗ tasks/ folder not found: {tasks}", file=sys.stderr)
        return 1

    # Guard: `--start` with an explicit date on an icebox card is an anti-pattern. 🛫/startedAt =
    # the actual work start; use --reminder for the expected ICEBOX return date.
    # `--start none` (removing an erroneous 🛫) is allowed.
    if args.start is not None and args.start.strip().lower() not in CLEAR:
        spec = tasks / "specs" / f"{args.slug}.md"
        if spec.is_file():
            fm = lb.parse_frontmatter(spec.read_text(encoding="utf-8")) or {}
            if fm.get("status") == "icebox":
                print(f"✗ --start rejected for a card in ICEBOX (status: icebox): "
                      f"🛫/startedAt = actual work start, not a return date. "
                      f"Use --reminder <DATE> for the expected unfreeze date. "
                      f"(`--start none` is allowed — to remove an erroneous 🛫.)", file=sys.stderr)
                return 1

    # board resolution (via --board or auto-detect based on the card's presence) — single resolver (S6)
    board_file, err = ku.resolve_board_for_slug(tasks, args.slug, args.board)
    if err:
        print(err, file=sys.stderr)
        return 1

    old_title_holder: dict[str, str | None] = {}

    def transform(cols, settings):
        found_col = ac.slug_on_board(cols, args.slug)
        if not found_col:
            raise ku.MutationError(
                f"✗ Card [[{args.slug}]] not found on board {board_file.name}.")
        block = next(b for b in cols[found_col] if mc.card_slug(b) == args.slug)
        old_line = next((ln for ln in block[1:] if ln.startswith("\t")), "")
        new_line = build_tag_line(apply_overrides(parse_tag_line(old_line), args))
        new_first_line = block[0]
        title_msg = ""
        if args.title:
            old_title_holder["old"] = mc.card_title(block)
            new_first_line = set_card_title_line(block[0], args.title)
            title_msg = f"; title → {args.title}"
        new_block = [new_first_line] + ([new_line] if new_line else [])
        cols[found_col] = [new_block if mc.card_slug(b) == args.slug else b
                           for b in cols[found_col]]
        return cols, (f"{args.slug} ({found_col}): tags → {new_line.strip() or '(all removed)'}"
                     + title_msg)

    rc, msg = ku.mutate_board(tasks, board_file, transform, dry_run=args.dry_run)
    print(msg, file=sys.stderr if rc else sys.stdout)
    if rc == 0:
        started_msg = sync_spec_started_at(tasks, args.slug, args.start, dry_run=args.dry_run)
        if started_msg:
            prefix = "[dry-run] " if args.dry_run else "✅ "
            print(prefix + started_msg)
        reminder_msg = sync_spec_reminder(tasks, args.slug, args.reminder, dry_run=args.dry_run)
        if reminder_msg:
            prefix = "[dry-run] " if args.dry_run else "✅ "
            print(prefix + reminder_msg)
        if args.title:
            title_synced = sync_spec_title(tasks, args.slug, old_title_holder.get("old"),
                                           args.title, dry_run=args.dry_run)
            if title_synced:
                prefix = "[dry-run] " if args.dry_run else "✅ "
                print(prefix + title_synced)
    return rc


if __name__ == "__main__":
    sys.exit(main())
