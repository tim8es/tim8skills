#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_item.py — check/uncheck checkboxes in spec sections (DoD/Subtasks/Test/Review).

Checkboxes are the last spec mutation that used to be edited manually with `Edit`. Manual editing
(a) violates the "deterministic mutations via script" principle; (b) after any script mutation of
the file, `Edit` fails with "file modified since read" → an extra re-Read. The script toggles `- [ ]`↔`- [x]`
by index or `--all` under `board_lock`, and the agent doesn't need to hold/re-read the whole spec.

ONLY checkbox lines of the target section (`- [ ] ` / `- [x] `) are counted, 1-based, in
order of appearance. Other text (nested lists, paragraphs) is left untouched. Bumps `updatedAt`.

Usage:
    python scripts/check_item.py <WORKSPACE_ROOT> <slug> <section> [indices...] [options]

section: dod | subtasks | test | review  (aliases: definition→dod, подзадачи→subtasks,
         tests→test, reviews→review)

Examples:
    python scripts/check_item.py "." my-task dod 1 3        # check DoD items 1 and 3
    python scripts/check_item.py "." my-task test --all     # check all Test Checklist items
    python scripts/check_item.py "." my-task dod 2 --uncheck # uncheck item 2

Options:
    --all        apply to all checkboxes in the section (indices not needed)
    --uncheck    uncheck (`[x]`→`[ ]`) instead of checking
    --dry-run    show the result without writing

Exit codes: 0 — applied/simulated; 1 — spec/section not found, no checkboxes,
index out of range, neither indices nor --all given.
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import re

import kanban_utils as ku  # mutate_spec, MutationError

SECTION_TITLES = {
    "dod": "Definition of Done (DoD)",
    "definition": "Definition of Done (DoD)",
    "subtasks": "Subtasks",
    "подзадачи": "Subtasks",
    "test": "Test Checklist",
    "tests": "Test Checklist",
    "review": "Review Checklist",
    "reviews": "Review Checklist",
}
# RU aliases for backward-compat with existing specs
_SECTION_ALIASES: dict[str, list[str]] = {
    "Subtasks": ["Подзадачи"],
}
CHECKBOX_RE = re.compile(r"^(\s*- \[)([ xX])(\] )")


def section_bounds(lines: list[str], title: str):
    """(start, end) line indices of the `## <title>` section body (from the line after the heading to
    the next `## ` or the end). Supports RU aliases for backward-compat."""
    candidates = [title] + _SECTION_ALIASES.get(title, [])
    header = None
    for cand in candidates:
        idx = next((i for i, l in enumerate(lines) if l.strip() == f"## {cand}"), None)
        if idx is not None:
            header = idx
            break
    if header is None:
        return None
    end = next((k for k in range(header + 1, len(lines)) if lines[k].startswith("## ")),
               len(lines))
    return (header + 1, end)


def make_check_transform(slug: str, title: str, indices, all_: bool, uncheck: bool = False):
    """Factory for transform(text)->(new_text, msg) to check/uncheck section checkboxes.
    Reused by the standalone command and the `update` composite (DRY)."""
    mark = " " if uncheck else "x"
    verb = "unchecked" if uncheck else "checked"

    def transform(text):
        lines = text.split("\n")
        bounds = section_bounds(lines, title)
        if bounds is None:
            raise ku.MutationError(f"✗ The spec has no `## {title}` section")
        start, end = bounds
        cb = [i for i in range(start, end) if CHECKBOX_RE.match(lines[i])]
        if not cb:
            raise ku.MutationError(f"✗ Section `## {title}` has no checkboxes")
        targets = list(range(1, len(cb) + 1)) if all_ else list(indices)
        bad = [n for n in targets if n < 1 or n > len(cb)]
        if bad:
            raise ku.MutationError(f"✗ Index(es) out of range 1..{len(cb)}: {bad}")
        for n in targets:
            lines[cb[n - 1]] = CHECKBOX_RE.sub(rf"\g<1>{mark}\g<3>", lines[cb[n - 1]], count=1)
        return "\n".join(lines), f"{slug}/{title}: {verb} {sorted(set(targets))} of {len(cb)}"
    return transform


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("slug", help="spec slug (without [[]])")
    ap.add_argument("section", help="section: dod | subtasks | test | review")
    ap.add_argument("indices", nargs="*", type=int, help="1-based checkbox indices")
    ap.add_argument("--all", action="store_true", help="all checkboxes in the section")
    ap.add_argument("--uncheck", action="store_true", help="uncheck instead of check")
    ap.add_argument("--dry-run", action="store_true", help="show the result without writing")
    args = ap.parse_args()

    key = args.section.strip().lower()
    title = SECTION_TITLES.get(key)
    if not title:
        print(f"✗ Unknown section: {args.section!r}. Valid: dod, subtasks, test, review",
              file=sys.stderr)
        return 1
    if not args.all and not args.indices:
        print("✗ Provide checkbox indices or --all", file=sys.stderr)
        return 1

    rc, msg = ku.mutate_spec(
        args.workspace, args.slug,
        make_check_transform(args.slug, title, args.indices, args.all, args.uncheck),
        dry_run=args.dry_run)
    print(msg, file=sys.stderr if rc else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main())
