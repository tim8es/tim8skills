#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""update.py — batch of spec mutations in a SINGLE call under a SINGLE lock.

Applies several spec changes (step + checkboxes + comment) as one transaction:
one board_lock acquisition, one read, one write, one updatedAt bump. Removes the overhead
of N separate commands in the role cycle (§9) — the agent closes out a role with one command.

Architecturally, this is a composition of pure transform factories (`set_step`/`check_item`/`add_comment`)
over `kanban_utils.mutate_spec`; exactly the same logic as the standalone commands (DRY, no duplication).

Usage (via the dispatcher):
    python <SCRIPT_PREFIX>/kanban.py update "." <slug> [options]

Options (at least one mutation is required):
    --item-type <value>          set YAML itemType (epic|task|subtask|unassigned)
    --step <value>               set YAML step (value `null` resets it)
    --clear-step                 reset step to null
    --dod <all|N,N,...>          check Definition of Done items
    --subtasks <all|N,N,...>     check Subtasks
    --test <all|N,N,...>         check Test Checklist
    --review <all|N,N,...>       check Review Checklist
    --uncheck                    uncheck (for the sections above) instead of checking
    --comment "<text>"           append a comment to `## Comments`; `-` reads the text from stdin
    --as <role>                  comment author role (required with --comment)
    --attention                  !!!ВНИМАНИЕ!!! prefix on the comment
    --dry-run                    show the result without writing

Example (closing out the developer role with one command instead of four):
    python <SCRIPT_PREFIX>/kanban.py update "." my-task --dod all --subtasks all \\
        --comment "what was implemented" --as developer

Application order: itemType → step → checkboxes (dod, subtasks, test, review) → comment.
Exit codes: 0 — applied/simulated; 1 — no operations / spec not found /
invalid role or indices / domain error (no field/section, index out of range).
"""
from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import argparse

import lint_board as lb       # VALID_OWNER, VALID_ITEMTYPE
import kanban_utils as ku      # mutate_spec, MutationError
import set_step                # make_step_transform
import set_item_type           # make_item_type_transform
import check_item              # make_check_transform, SECTION_TITLES
import add_comment             # make_comment_transform

# CLI flag -> check_item.SECTION_TITLES key (order = checkbox application order)
_SECTION_FLAGS = ["dod", "subtasks", "test", "review"]


def _parse_indices(spec: str, label: str):
    """'all' → (None, True); '1,3' → ([1,3], False). Otherwise MutationError."""
    if spec.strip().lower() == "all":
        return None, True
    try:
        idx = [int(x) for x in spec.split(",") if x.strip()]
    except ValueError:
        raise ku.MutationError(
            f"✗ {label}: expected 'all' or comma-separated indices, got {spec!r}")
    if not idx:
        raise ku.MutationError(f"✗ {label}: empty index list")
    return idx, False


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("workspace", help="WORKSPACE_ROOT or path to tasks/")
    ap.add_argument("slug", help="spec slug (without [[]])")
    ap.add_argument("--item-type", dest="item_type", default=None,
                    help="set itemType (epic|task|subtask|unassigned)")
    ap.add_argument("--step", default=None, help="set step (null resets it)")
    ap.add_argument("--clear-step", action="store_true", help="reset step to null")
    ap.add_argument("--dod", default=None, help="check DoD: all|N,N")
    ap.add_argument("--subtasks", default=None, help="check Subtasks: all|N,N")
    ap.add_argument("--test", default=None, help="check Test Checklist: all|N,N")
    ap.add_argument("--review", default=None, help="check Review Checklist: all|N,N")
    ap.add_argument("--uncheck", action="store_true", help="uncheck instead of check")
    ap.add_argument("--comment", default=None, help="comment text for ## Comments")
    ap.add_argument("--as", dest="role", default=None, help="comment author role")
    ap.add_argument("--attention", action="store_true", help="!!!ВНИМАНИЕ!!! prefix")
    ap.add_argument("--dry-run", action="store_true", help="show the result without writing")
    args = ap.parse_args()

    transforms = []

    # 1) itemType (value validated before acquiring the lock — invalid → 1)
    if args.item_type is not None:
        try:
            transforms.append(
                set_item_type.make_item_type_transform(args.slug, args.item_type))
        except ku.MutationError as e:
            print(str(e), file=sys.stderr)
            return 1

    # 2) step
    if args.clear_step or (args.step is not None and args.step.strip().lower() == "null"):
        transforms.append(set_step.make_step_transform(args.slug, "null"))
    elif args.step is not None:
        transforms.append(set_step.make_step_transform(args.slug, args.step))

    # 3) checkboxes (in fixed section order)
    try:
        for flag in _SECTION_FLAGS:
            val = getattr(args, flag)
            if val is None:
                continue
            indices, all_ = _parse_indices(val, f"--{flag}")
            transforms.append(check_item.make_check_transform(
                args.slug, check_item.SECTION_TITLES[flag], indices or [], all_, args.uncheck))
    except ku.MutationError as e:
        print(str(e), file=sys.stderr)
        return 1

    # 4) comment
    if args.comment is not None:
        if args.comment == "-":
            if hasattr(sys.stdin, "reconfigure"):
                sys.stdin.reconfigure(encoding="utf-8", errors="replace")
            args.comment = sys.stdin.read().strip()
            if not args.comment:
                print("✗ --comment - : empty stdin", file=sys.stderr)
                return 1
        if not args.role:
            print("✗ --comment requires --as <role>", file=sys.stderr)
            return 1
        if args.role not in lb.VALID_OWNER:
            print(f"✗ Invalid role: {args.role!r}. "
                  f"Valid: {', '.join(sorted(lb.VALID_OWNER))}", file=sys.stderr)
            return 1
        transforms.append(add_comment.make_comment_transform(
            args.slug, args.role, args.comment, "comments", args.attention))

    if not transforms:
        print("✗ No operation given "
              "(--item-type/--step/--clear-step/--dod/--subtasks/--test/--review/--comment)",
              file=sys.stderr)
        return 1

    def combined(text):
        msgs = []
        for t in transforms:
            text, m = t(text)
            msgs.append(m)
        return text, " · ".join(msgs)

    rc, msg = ku.mutate_spec(args.workspace, args.slug, combined, dry_run=args.dry_run)
    print(msg, file=sys.stderr if rc else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main())
