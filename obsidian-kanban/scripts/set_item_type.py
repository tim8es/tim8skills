#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""set_item_type.py — safe setting of the YAML `itemType:` field in a spec.

`itemType:` — the card's type in the hierarchy (`epic`/`task`/`subtask`, §4). The dashboard creates
cards with `itemType: unassigned`; the analyst must assign the real type before moving
to TODO (the linter forbids `unassigned` outside BACKLOG/ICEBOX, §8). This used to be the last
frontmatter edit that had to be done manually (`Edit`), against the "deterministic
mutations via script" rule. The script reads the file at execution time and writes
under `board_lock` — there is no race with `move_card` (which rewrites the frontmatter), just like `set_step`.

Replaces only the `itemType:` line in the frontmatter (`count=1`, multiline `^…$`) and
bumps `updatedAt`. Other text is untouched. The value is validated against `lb.VALID_ITEMTYPE`
(DRY — the list is not hardcoded). No dependencies outside stdlib/the skill.

Usage:
    python scripts/set_item_type.py <WORKSPACE_ROOT> <slug> <value> [options]

Examples:
    python scripts/set_item_type.py "." my-task task
    python scripts/set_item_type.py "." my-epic epic
    python scripts/set_item_type.py "." my-task subtask

Options:
    --dry-run    show the result without writing

Exit codes: 0 — set/simulated; 1 — spec not found / no itemType field /
invalid value (not in VALID_ITEMTYPE).
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse
import re

import lint_board as lb        # VALID_ITEMTYPE
import kanban_utils as ku      # mutate_spec, MutationError

ITEMTYPE_RE = re.compile(r"^(itemType:\s*).*$", re.M)


def make_item_type_transform(slug: str, value: str):
    """Factory for transform(text)->(new_text, msg) for the `itemType` field. Reused by the
    standalone command and the `update` composite (DRY — a single mutation implementation).

    The value is validated against `lb.VALID_ITEMTYPE`; invalid → MutationError with the list."""
    if value not in lb.VALID_ITEMTYPE:
        raise ku.MutationError(
            f"✗ Invalid itemType: {value!r}. "
            f"Valid: {', '.join(sorted(lb.VALID_ITEMTYPE))}")

    def transform(text):
        if not ITEMTYPE_RE.search(text):
            raise ku.MutationError("✗ The spec has no `itemType:` field in the frontmatter")
        # lambda substitution: consistent with set_step (no backref needed in the replacement string).
        new_text = ITEMTYPE_RE.sub(lambda m: m.group(1) + value, text, count=1)
        return new_text, f"{slug}: itemType → {value}"
    return transform


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("slug", help="spec slug (without [[]])")
    ap.add_argument("value", help=f"new itemType ({'/'.join(sorted(lb.VALID_ITEMTYPE))})")
    ap.add_argument("--dry-run", action="store_true", help="show the result without writing")
    args = ap.parse_args()

    try:
        transform = make_item_type_transform(args.slug, args.value)
    except ku.MutationError as e:
        print(str(e), file=sys.stderr)
        return 1

    rc, msg = ku.mutate_spec(args.workspace, args.slug, transform, dry_run=args.dry_run)
    print(msg, file=sys.stderr if rc else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main())
