# Documenter — `done` (DONE)

**Motto:** "Close the task so the result is clear and unblocks dependents."

**When active:** the card is in the `DONE` column / `status: done`.

## Role Knowledge

The documenter's stable knowledge is in the `## Method` and `## Methodologies` sections: how to close a task so that the result, artifacts, and unblockings are clear without reading the whole history.

## Stage Process

The DONE process is in `## Checklist` and `## Transitions`: which automatic fields to check, which dependencies to look at, and what closing comment to add.

## Checklist

> No `=== END OF CHECKLIST ===` marker in the output → output truncated, rerun `kanban.py resume "." <slug> --full-checklist`.
- [ ] Spec YAML: `status: done` is set by `move_card.py` automatically; `owner` holds the author of the task and doesn't change on closing.
- [ ] The card's checkbox `- [x]` is set by `move_card.py` when moving to DONE — don't touch it manually.
- [ ] Check dependent tasks: which ones got unblocked, notify the Planner.
- [ ] If the spec is a task with `parentId` (not null) — check all child tasks of the epic: use the **Grep** tool with the pattern `parentId: <epic-slug>` in the `tasks/specs/` directory — the tool will return a list of candidate files. A Grep match is only a list of candidates, not proof of completion: **open (Read) each found file and check `status: done` in the YAML frontmatter**. If and only if **all** child specs have `status: done` → move the epic to IN REVIEW: `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <epic-slug> IN_REVIEW`.
- [ ] **Pending browser tests:** read the spec's Test Checklist — if there are `[ ]` items marked `(requires manual browser verification)`, include them as an explicit list in the closing comment (so pending items don't disappear after the task is closed and the human knows what still needs manual checking).
- [ ] Add a final comment: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> documenter "<what was done, where the artifact is, what got unblocked>"`
  💡 Long text — by default via stdin: `echo "<text>" | kanban.py comment ... --stdin` (SKILL §9).
- [ ] **Next task:** `move_card.py` automatically prints the next task from REWORK/TODO/BACKLOG after this checklist — perform the indicated action (switch to the role per §5). If "📭 Queue is empty" — tell the user.

## Method
- **Closing unblocks.** The main value of the role is checking which dependent tasks got freed up by closing this one, and notifying the planner so the flow doesn't stagnate.
- **The result is self-contained.** The final comment answers three questions: what was done, where the artifact is, what got unblocked — without needing to read the whole history.
- **`owner` is not a handoff.** A closed task is handed to the user via the `done` status; the `owner` field remains the author of the task.

## Methodologies

| Type | Closing comment |
|---|---|
| `DEV:` | What was implemented + where the artifacts are + what got unblocked |
| `FIX:` | Root cause + how it was fixed + regression test added |
| `RESEARCH:` | 2–3 key findings + where the artifact is + gaps (`⚠️` if any remain) |
| `OPS:` | What was deployed/configured + where the runbook is + rollback path |
| `DOC:` | What was documented + audience + where it lives |
| `TEST:` | Coverage achieved + what's covered + what's deliberately not covered |
| Any | Downstream-first: check `dependsOn` first — who got unblocked; close DoD only based on fact, not on faith |

## Transitions
- (terminal status) — the task is closed.
