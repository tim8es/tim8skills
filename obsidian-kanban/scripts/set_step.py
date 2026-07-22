#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""set_step.py — safe setting of the YAML `step:` field in a spec.

`step:` — a developer progress marker (resume point after an interruption, §8/§9).
`step` and `itemType` (see `set_item_type.py`) are frontmatter fields that used to
be edited manually; now both are set via script;
a manual `Edit` right after `move_card.py` used to break on a race ("file modified since read"),
since move_card rewrites the frontmatter. The script reads the file at execution time and
writes under `board_lock` — no race. Consistent with the "deterministic mutations
via script, not by hand" principle.

Replaces only the `step:` line in the frontmatter (`count=1`, multiline `^…$`) and bumps
`updatedAt`. Other text is untouched. No dependencies (stdlib).

Usage:
    python scripts/set_step.py <WORKSPACE_ROOT> <slug> <value> [options]

Examples:
    python scripts/set_step.py "." my-task step-1
    python scripts/set_step.py "." my-task "step-3 (refactor ready)"
    python scripts/set_step.py "." my-task null        # reset (== --clear)
    python scripts/set_step.py "." my-task --clear

Options:
    --clear      set `step: null` (value is then optional)
    --dry-run    show the result without writing

Exit codes: 0 — set/simulated; 1 — spec not found / no step field / no value given.
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

STEP_RE = re.compile(r"^(step:\s*).*$", re.M)


def make_step_transform(slug: str, value: str):
    """Factory for transform(text)->(new_text, msg) for the `step` field. Reused by the
    standalone command and the `update` composite (DRY — a single mutation implementation)."""
    def transform(text):
        if not STEP_RE.search(text):
            raise ku.MutationError("✗ The spec has no `step:` field in the frontmatter")
        # lambda substitution: the value may contain spaces/parentheses/backslashes —
        # a backref in the replacement string would mangle them.
        new_text = STEP_RE.sub(lambda m: m.group(1) + value, text, count=1)
        return new_text, f"{slug}: step → {value}"
    return transform


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("slug", help="spec slug (without [[]])")
    ap.add_argument("value", nargs="?", default=None,
                    help="new step value (e.g. step-2); 'null' or --clear reset it")
    ap.add_argument("--clear", action="store_true", help="set step: null")
    ap.add_argument("--dry-run", action="store_true", help="show the result without writing")
    args = ap.parse_args()

    # value: --clear or 'null' → null; otherwise value is required
    if args.clear or (args.value is not None and args.value.strip().lower() == "null"):
        value = "null"
    elif args.value is None:
        print("✗ No step value given (provide <value> or --clear)", file=sys.stderr)
        return 1
    else:
        value = args.value

    rc, msg = ku.mutate_spec(args.workspace, args.slug,
                             make_step_transform(args.slug, value), dry_run=args.dry_run)
    print(msg, file=sys.stderr if rc else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main())
