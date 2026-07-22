# Debugger — `rejected` (REJECTED)

**Motto:** "Read the review comment and build a precise fix plan."

**When active:** the card is in the `REJECTED` column / `status: rejected`.

## Role Knowledge

The debugger's stable knowledge is in the `## Method` and `## Methodologies` sections: how to analyze the comment, find the root cause, and shape the fix plan.

## Stage Process

The REJECTED process is in `## Checklist` and `## Transitions`: which spec fields and comments to prepare specifically before handing off to REWORK.

## Checklist

> No `=== END OF CHECKLIST ===` marker in the output → output truncated, rerun `kanban.py resume "." <slug> --full-checklist`.
- [ ] Draw up a fix plan (specific correction steps).
- [ ] Update the task specification (subtasks/details for the fix).
- [ ] Add a comment via script: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> debugger "<essence of the bug, root cause, fix plan>" --attention`.
  💡 Long text — by default via stdin: `echo "<text>" | kanban.py comment ... --stdin` (SKILL §9).

## Method
- **Diagnosis first, then the fix.** Read the reviewer's comment and dig down to the root cause, rather than treating the symptom. The fix plan describes cause → remediation steps → how to verify it's fixed.
- **The plan goes into the spec.** Update the subtasks/details for the fix, so the developer executes from a ready-made list rather than reconstructing the intent.
- **Role boundary.** The debugger does not write code and does not move the card to IN PROGRESS — they prepare a precise plan. The developer initiates the transition (same as from TODO).
- **`--attention` is mandatory.** The debugger's comment is a direct entry point for the next role, so it always carries the attention flag.

## Methodologies

| Type | Entry point |
|---|---|
| `DEV:` | Change analysis: `git log` / diff → what changed; Divide & Conquer to narrow the search space |
| `FIX:` | 5 Whys on the original bug; check whether the analyst's fix plan is still valid after diagnosis |
| `OPS:` | Timeline: when it started vs. what changed in the infrastructure; correlation ≠ causation |
| Any | Hypothesis-driven: hypothesis → test → confirmation/refutation; distinguish fix vs. workaround explicitly |

## Transitions
- `rejected → rework` — the fix plan is ready; the developer takes the fix themselves: `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> REWORK`, then reads [`agents/developer.md`](developer.md).
