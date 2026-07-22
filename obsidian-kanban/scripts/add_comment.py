#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""add_comment.py — safe append to a spec's `## Comments` / `## Changelog` section.

Replaces manual editing of these sections — a source of errors (with a combined
edit it's easy to delete the section heading, and the entry "falls through" into the
neighboring one). The script appends a
`YYYY-MM-DD HH:MM:SS | <role> | <text>` line at the END of the target section, without touching the rest.
If the section doesn't exist, it creates it at the end of the file (self-healing). Bumps `updatedAt` in the frontmatter.

The line format and roles (§8/§9) are aligned with lint_board (VALID_OWNER is the single source).
No dependencies (stdlib). Time is `dt.datetime.now()` (system timezone, MSK).

Usage:
    python scripts/add_comment.py <WORKSPACE_ROOT> <slug> <role> "<text>" [options]
    python scripts/add_comment.py <WORKSPACE_ROOT> <slug> <role> --stdin [options]  # no shell-mangling

Options:
    --stdin                      read the text from stdin (protects against quote/|/! mangling in the shell)
    --section comments|history   target section (default comments → `## Comments`)
    --attention                  add the `!!!ВНИМАНИЕ!!! ` prefix to the text
    --dry-run                    show the result without writing

Exit codes: 0 — added/simulated; 1 — spec not found / unknown role/section.
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")

import argparse
import re

import lint_board as lb  # single source of VALID_OWNER
import kanban_utils as ku  # mutate_spec, hist_stamp

SECTION_TITLES = {"comments": "Comments", "history": "Changelog"}
# RU aliases for backward-compat with existing specs that use Russian section headers
_SECTION_ALIASES: dict[str, list[str]] = {
    "Comments": ["Комментарии"],
    "Changelog": ["История изменений"],
}
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})? \|")  # HH:MM or HH:MM:SS


def insert_into_section(text: str, title: str, entry: str) -> str:
    """Inserts `entry` at the end of the `## <title>` section; creates the section at the end of the file if missing.
    Supports RU aliases for backward compatibility with older specs.
    Operates on LF; the caller normalizes line endings."""
    lines = text.split("\n")

    # Try primary EN title first, then RU aliases for backward-compat
    header = None
    for candidate in [title] + _SECTION_ALIASES.get(title, []):
        idx = next((i for i, l in enumerate(lines) if l.strip() == f"## {candidate}"), None)
        if idx is not None:
            header = idx
            break

    if header is None:
        # self-heal: no section — create it at the end of the file with an EN heading
        while lines and lines[-1].strip() == "":
            lines.pop()
        lines += ["", f"## {title}", "", entry]
        return "\n".join(lines) + "\n"

    # end of section — the next `## ` heading or end of file
    end = next((k for k in range(header + 1, len(lines)) if lines[k].startswith("## ")),
               len(lines))
    # dedup: don't insert if the exact entry is already present in the section
    body = lines[header + 1:end]
    if any(l.strip() == entry.strip() for l in body):
        return text
    # last non-empty line inside the section (or the heading itself, if the section is empty)
    last = header
    for k in range(header + 1, end):
        if lines[k].strip() != "":
            last = k

    if last == header:
        lines[header + 1:header + 1] = ["", entry]  # blank line after the heading + entry
    else:
        lines[last + 1:last + 1] = [entry, ""]
        # ensure blank line before next ## header (idempotent)
        after = last + 2
        if after < len(lines) and lines[after].startswith("## "):
            lines[after:after] = [""]
    return "\n".join(lines)


def sort_section(text: str, title: str) -> str:
    """Stably sorts timestamped lines of the `## <title>` section by the leading
    `YYYY-MM-DD HH:MM:SS` (newest first, descending). Supports RU aliases.
    If already sorted, returns the text unchanged."""
    lines = text.split("\n")
    header = None
    for candidate in [title] + _SECTION_ALIASES.get(title, []):
        idx = next((i for i, l in enumerate(lines) if l.strip() == f"## {candidate}"), None)
        if idx is not None:
            header = idx
            break
    if header is None:
        return text
    end = next((k for k in range(header + 1, len(lines)) if lines[k].startswith("## ")),
               len(lines))
    body = lines[header + 1:end]
    ts = [l for l in body if TS_RE.match(l)]
    others = [l for l in body if l.strip() != "" and not TS_RE.match(l)]
    ts_sorted = sorted(ts, key=lambda l: l.split(' | ', 1)[0].strip(), reverse=True)
    # interleave blank lines between entries for readability in raw text
    spaced: list[str] = []
    for i, entry in enumerate(ts_sorted):
        spaced.append(entry)
        if i < len(ts_sorted) - 1:
            spaced.append("")
    # trailing blank only when a next ## section follows (avoids extra blank at end of file)
    suffix = [""] if end < len(lines) else []
    new_body = [""] + others + spaced + suffix
    if lines[header + 1:end] == new_body:
        return text  # already in the desired shape — nothing to change
    lines[header + 1:end] = new_body
    return "\n".join(lines)


def make_comment_transform(slug: str, role: str, text: str,
                           section: str = "comments", attention: bool = False):
    """Factory for transform(text)->(new_text, msg) to append into `## Comments`/`## Changelog`.
    The timestamp is fixed when the factory is built. Reused standalone and by the `update` composite."""
    title = SECTION_TITLES[section]
    body = ("!!!ВНИМАНИЕ!!! " + text) if attention else text
    entry = f"{ku.hist_stamp()} | {role} | {body}"

    def transform(t):
        new_text = insert_into_section(t, title, entry)
        new_text = sort_section(new_text, title)
        return new_text, f"{slug}: entry added to `## {title}`"
    return transform


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("slug", help="spec slug (without [[]])")
    ap.add_argument("role", help="entry author role (analyst/developer/tester/...)")
    ap.add_argument("text", nargs="?", default=None,
                    help="entry text; omit when using --stdin")
    ap.add_argument("--stdin", action="store_true",
                    help="read the text from stdin (protects against shell-mangling of special characters)")
    ap.add_argument("--section", default="comments", choices=list(SECTION_TITLES),
                    help="target section: comments (default) or history")
    ap.add_argument("--attention", action="store_true",
                    help="add the !!!ВНИМАНИЕ!!! prefix")
    ap.add_argument("--dry-run", action="store_true", help="show the result without writing")
    args = ap.parse_args()

    if args.stdin or args.text == "-":
        text = sys.stdin.read().strip()
    elif args.text is not None:
        text = args.text
    else:
        print("✗ Provide the entry text as an argument or use --stdin.", file=sys.stderr)
        return 1

    if args.role not in lb.VALID_OWNER:
        print(f"✗ Invalid role: {args.role!r}. Valid: {', '.join(sorted(lb.VALID_OWNER))}",
              file=sys.stderr)
        return 1

    rc, msg = ku.mutate_spec(
        args.workspace, args.slug,
        make_comment_transform(args.slug, args.role, text, args.section, args.attention),
        dry_run=args.dry_run)
    print(msg, file=sys.stderr if rc else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main())
