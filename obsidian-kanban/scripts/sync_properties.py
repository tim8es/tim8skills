#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_properties.py — full normalization of YAML properties in specs/*.md notes.

What it does (per SKILL.md §8 and §5):
  1. Guarantees the presence of all required fields; adds missing ones with defaults.
  2. Brings field order to the canonical one.
  3. Validates/normalizes enum fields (status, itemType, owner, priority) to lowercase.
  4. Syncs `status` with the board column the card actually sits in (the column is the source of truth).
  5. Normalizes createdAt/updatedAt dates (canonical format — `YYYY-MM-DD HH:MM:SS`,
     as written by now_stamp/hist_stamp; date-only `YYYY-MM-DD` is padded to `00:00`).
  6. If anything changed, sets `updatedAt = <current time>`.

UNLIKE lint_board.py, this script WRITES files. --dry-run mode is off by default.

Usage:
    python scripts/sync_properties.py <WORKSPACE_ROOT> --slug <slug>   # single spec (role cycle §9)
    python scripts/sync_properties.py <WORKSPACE_ROOT> --all           # whole workspace (one-off cleanup)
    python scripts/sync_properties.py <WORKSPACE_ROOT> --slug <slug> --dry-run  # show the diff, don't write

Without --slug and without --all, the script exits with an error — a full scan updates updatedAt for all files.

No dependencies (stdlib). Frontmatter is parsed as flat YAML.
"""

from __future__ import annotations

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import contextlib
import re
from pathlib import Path

import kanban_utils as ku  # board_lock
import lint_board as lb  # resolve_tasks_dir (single resolver for tasks/)

# Validation tables (COLUMN_TO_STATUS, VALID_STATUS/ITEMTYPE/OWNER/PRIORITY) are the
# canonical ones from lint_board (re-exported from lint_board_rules) — referenced as
# lb.* so sync accepts exactly what lint accepts, with no duplicated copy to drift.
# STATUS→timestamp-field mapping for backfilling a null timestamp if an interrupted move
# didn't set it. Derived from the lint_board_rules canon (COLUMN_TO_STATUS + COLUMN_TO_TIMESTAMP):
# normalize_fields receives board_status (a STATUS, not a column name — parse_board maps
# column→status), so it's keyed by status, not by column. The map used to be column-keyed
# and reviewAt was never backfilled ("review" ≠ "IN REVIEW"); testingAt/doneAt only matched
# lexically. The reference for correct column-based keying is move_card.sync_spec_status (dst_col).
_STATUS_TO_TIMESTAMP = {lb.COLUMN_TO_STATUS[col]: field
                        for col, field in lb.COLUMN_TO_TIMESTAMP.items()}

# canonical order and defaults
FIELD_ORDER = ["flowId", "itemType", "status", "parentId", "step",
               "owner", "priority", "createdAt", "updatedAt", "reminder",
               "startedAt", "testingAt", "reviewAt", "doneAt",
               "dependsOn", "blocks"]
DEFAULTS = {
    "itemType": "task", "status": "backlog", "parentId": "null", "step": "null",
    "owner": "analyst", "priority": "medium",
    "startedAt": "null", "testingAt": "null", "reviewAt": "null", "doneAt": "null",
    "dependsOn": "[]", "blocks": "[]",
}

# Wikilink / card-line regexes reuse the lint_board canon (lb.WIKILINK_RE / lb.CARD_RE)
# — single source of truth, no local copy to drift. lb.WIKILINK_RE.group(1) is the slug
# (class [^\]|] excludes ] and |, so it captures the same slug the former local greedy
# and lazy copies did); the canon's alt-text handling is strictly more robust.
DATE_FULL = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?$")
DATE_ONLY = re.compile(r"^(\d{4}-\d{2}-\d{2})$")
PRIORITY_EMOJI = {"🟥": "high", "🟨": "medium", "🟩": "low"}


def _extract_section(body: str, title: str) -> str:
    """Return text content of `## title` section (until next ## or end)."""
    lines = body.splitlines()
    start = next((i for i, l in enumerate(lines) if l.strip() == f"## {title}"), None)
    if start is None:
        return ""
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
               len(lines))
    return "\n".join(lines[start + 1:end])


def migrate_deps_from_prose(fm: dict, body: str) -> list[str]:
    """One-time migration: if dependsOn/blocks are empty, parse ## Dependencies prose.

    Updates fm in-place. Returns list of change descriptions (empty = nothing done)."""
    if fm.get("dependsOn", "[]") not in ("[]", "", None, "null") or \
       fm.get("blocks", "[]") not in ("[]", "", None, "null"):
        return []  # already set — never overwrite

    deps_text = _extract_section(body, "Dependencies") or _extract_section(body, "Зависимости")
    if not deps_text:
        return []

    depends_slugs, blocks_slugs = [], []
    for ln in deps_text.splitlines():
        # accumulate (don't overwrite): "Depends on" / "Blocks" can span
        # several prose lines; dedup while preserving order.
        if "Зависит от" in ln:
            depends_slugs += [s for s in lb.WIKILINK_RE.findall(ln) if s not in depends_slugs]
        elif "Блокирует" in ln:
            blocks_slugs += [s for s in lb.WIKILINK_RE.findall(ln) if s not in blocks_slugs]

    changes = []
    if depends_slugs:
        fm["dependsOn"] = "[" + ", ".join(depends_slugs) + "]"
        changes.append(f"+ dependsOn: {fm['dependsOn']} (migrated from prose)")
    if blocks_slugs:
        fm["blocks"] = "[" + ", ".join(blocks_slugs) + "]"
        changes.append(f"+ blocks: {fm['blocks']} (migrated from prose)")
    return changes


def split_frontmatter(text: str) -> tuple[dict | None, str, str]:
    """Returns (fields, raw_fm_block, body). fields=None if there is no block."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # normalize CRLF/CR → LF
    if not text.startswith("---"):
        return None, "", text
    end = text.find("\n---", 3)
    if end == -1:
        return None, "", text
    raw = text[3:end].strip("\n")
    body = text[end + 4:]  # after "\n---"
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip()
    return fields, raw, body


def normalize_date(val: str) -> str:
    if not val or val == "null":
        return val
    if DATE_FULL.match(val):
        return val
    m = DATE_ONLY.match(val)
    if m:
        return f"{m.group(1)} 00:00"
    return val  # unknown format left as-is — the linter will complain


def parse_board(text: str) -> dict[str, str]:
    """slug → status. Adapter over lint_board.parse_board (slug → column):
    maps each card's board column to the canonical status via COLUMN_TO_STATUS,
    so board card-scanning has a single implementation (lint_board)."""
    return {slug: lb.COLUMN_TO_STATUS[col]
            for slug, col in lb.parse_board(text).items()
            if col in lb.COLUMN_TO_STATUS}


def parse_board_priority(text: str) -> dict[str, str]:
    """slug → 'high'|'medium'|'low' from the card's emoji tags line on the board.
    The tags line starts with '\t' and comes right after the card line.
    Source of truth for priority — the board emoji (analogous to status → board column)."""
    slug_to_priority: dict[str, str] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if lb.CARD_RE.match(line):
            link = lb.WIKILINK_RE.search(line)
            if not link:
                continue
            slug = link.group(1).strip()
            # the next line is the tags line (starts with \t)
            if i + 1 < len(lines) and lines[i + 1].startswith("\t"):
                tag_line = lines[i + 1]
                for emoji, pri in PRIORITY_EMOJI.items():
                    if emoji in tag_line:
                        slug_to_priority[slug] = pri
                        break
    return slug_to_priority


def normalize_fields(fm: dict[str, str], slug: str, project: str,
                     board_status: str | None, sync_status: bool,
                     board_priority: str | None = None) -> tuple[dict, list[str]]:
    changes: list[str] = []
    out = dict(fm)

    # defaults for missing fields
    for f, default in DEFAULTS.items():
        if f not in out or out[f] == "":
            out[f] = default
            changes.append(f"+ {f}: {default}")

    # flowId — §8: exactly 3 parts: project/itemType/slug
    if not out.get("flowId"):
        item = out.get("itemType", "task")
        out["flowId"] = f"{project}/{item}/{slug}"
        changes.append(f"+ flowId: {out['flowId']}")

    # enum lowercase + validation
    for field, valid in (("status", lb.VALID_STATUS), ("itemType", lb.VALID_ITEMTYPE),
                         ("owner", lb.VALID_OWNER), ("priority", lb.VALID_PRIORITY)):
        if field in out and out[field] not in (None, "", "null"):
            low = out[field].lower()
            if low != out[field]:
                changes.append(f"~ {field}: {out[field]} → {low}")
                out[field] = low
            # `priority: none` from the dashboard (quick card creation) means
            # "priority not set" — equivalent to `tags --priority none`, which
            # removes the tag on the board. Normalize to the literal null sentinel (like
            # startedAt/testingAt/…) instead of a linter ERROR state; see lint_board.py's
            # `priority` check, which explicitly allows `null`.
            if field == "priority" and out[field] == "none":
                changes.append("~ priority: none → null (priority not set)")
                out[field] = "null"
                continue
            if out[field] not in valid:
                changes.append(f"! {field}: invalid value `{out[field]}` (left as-is)")

    # sync status with the board column
    if sync_status and board_status and out.get("status") != board_status:
        # Lost-DONE safeguard: a downgrade from `done` with a non-empty doneAt is a strong sign
        # of a false/racy move that dropped a completed card. The column is the source
        # of truth, so status is synced regardless, but NOT silently: print a loud
        # warning instead of a silent overwrite (see warn-doneat-not-in-done-column).
        if (out.get("status") == "done" and board_status != "done"
                and (out.get("doneAt") or "").strip() not in ("", "null")):
            changes.append(
                f"! POSSIBLE LOST DONE: status `done` (doneAt={out.get('doneAt')}) "
                f"is being downgraded to `{board_status}` by the board column — check ## Changelog "
                "for a false/racy move; if DONE is correct, move the card back to DONE"
            )
        changes.append(f"~ status: {out.get('status')} → {board_status} (by board column)")
        out["status"] = board_status

    # backfill the transition timestamp if an interrupted move left it null.
    # board_status is a STATUS (not a column name), so keying is by status (see _STATUS_TO_TIMESTAMP).
    ts_field = _STATUS_TO_TIMESTAMP.get(board_status or "")
    if sync_status and ts_field and out.get(ts_field) in (None, "", "null"):
        out[ts_field] = ku.now_stamp()
        changes.append(
            f"+ {ts_field}: {out[ts_field]} (backfill — the card is on the board in {board_status}, "
            "but the transition timestamp was missing; set to the current sync time, "
            "since the exact transition time cannot be recovered)"
        )

    # sync priority with the board emoji tag (the board emoji is the single source of truth)
    if board_priority and out.get("priority") != board_priority:
        changes.append(f"~ priority: {out.get('priority')} → {board_priority} (by board emoji)")
        out["priority"] = board_priority

    # dates
    for d in ("createdAt", "updatedAt"):
        if out.get(d):
            norm = normalize_date(out[d])
            if norm != out[d]:
                changes.append(f"~ {d}: {out[d]} → {norm}")
                out[d] = norm
    if not out.get("createdAt"):
        out["createdAt"] = ku.now_stamp()
        changes.append(f"+ createdAt: {out['createdAt']}")

    # if anything changed — bump updatedAt
    if changes:
        new_ts = ku.now_stamp()
        if out.get("updatedAt") != new_ts:
            out["updatedAt"] = new_ts
            changes.append(f"~ updatedAt → {new_ts}")

    return out, changes


def render_frontmatter(fm: dict[str, str]) -> str:
    ordered = [(k, fm[k]) for k in FIELD_ORDER if k in fm]
    extras = [(k, v) for k, v in fm.items() if k not in FIELD_ORDER]
    lines = [f"{k}: {v}" for k, v in ordered + extras]
    return "---\n" + "\n".join(lines) + "\n---"


def main() -> int:
    ap = argparse.ArgumentParser(description="Normalize YAML properties in specs/*.md.")
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("--slug", help="process only this spec (for the role cycle §9)")
    ap.add_argument("--all", dest="all_specs", action="store_true",
                    help="process all specs in the workspace (requires explicit opt-in to avoid an accidental mass updatedAt update)")
    ap.add_argument("--dry-run", action="store_true", help="show changes without writing")
    ap.add_argument("--no-status", action="store_true", help="do not sync status with the board")
    args = ap.parse_args()

    if not args.slug and not args.all_specs:
        print(
            "✗ Provide --slug <slug> for a single spec or --all for the whole workspace.\n"
            "  A full scan updates updatedAt for all files — use it deliberately.",
            file=sys.stderr,
        )
        return 2

    root = Path(args.workspace).expanduser()
    tasks = lb.resolve_tasks_dir(root)
    specs_dir = tasks / "specs"
    if not specs_dir.is_dir():
        print(f"✗ specs/ folder not found: {specs_dir}", file=sys.stderr)
        return 2

    # collect statuses and priorities from the boards
    board_status: dict[str, str] = {}
    board_priority: dict[str, str] = {}
    for md in sorted(tasks.glob("*.md")):
        if md.name == "SKILL.md" or md.stem.endswith("-archive"):
            continue
        txt = md.read_text(encoding="utf-8", errors="replace")
        if "kanban-plugin: board" in txt:
            board_status.update(parse_board(txt))
            board_priority.update(parse_board_priority(txt))

    total_changed = 0
    slug_filter = args.slug.strip() if args.slug else None
    print(f"\n  Property normalization — {specs_dir}"
          f"{f'  [slug={slug_filter}]' if slug_filter else ''}"
          f"{'  [DRY-RUN]' if args.dry_run else ''}\n")

    candidates = (
        [specs_dir / f"{slug_filter}.md"] if slug_filter
        else sorted(specs_dir.glob("*.md"))
    )

    lock_ctx = ku.board_lock(tasks) if not args.dry_run else contextlib.nullcontext()
    with lock_ctx:
        for md in candidates:
            if not md.is_file():
                print(f"  ✗ spec not found: {md.name}", file=sys.stderr)
                continue
            text = md.read_text(encoding="utf-8", errors="replace")
            fm, _, body = split_frontmatter(text)
            if fm is None:
                print(f"  ▲ {md.name}: no frontmatter — skipping")
                continue
            project = (fm.get("flowId") or "project/x").split("/")[0]
            migration_changes = migrate_deps_from_prose(fm, body)
            new_fm, norm_changes = normalize_fields(
                fm, md.stem, project, board_status.get(md.stem), not args.no_status,
                board_priority.get(md.stem))
            changes = migration_changes + norm_changes
            if not changes:
                continue
            total_changed += 1
            print(f"  ● {md.name}")
            for c in changes:
                print(f"      {c}")
            if not args.dry_run:
                ku._fsync_write(md, render_frontmatter(new_fm) + body)

    verb = "would need changes" if args.dry_run else "updated"
    print(f"\n  Files {verb}: {total_changed}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
