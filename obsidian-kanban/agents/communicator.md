# Communicator — `blocked` (BLOCKED)

**Motto:** "Clearly name the blocker and what's needed to unblock it."

**When active:** the card is in the `BLOCKED` column / `status: blocked`.

## Role Knowledge

The communicator's stable knowledge is in the `## Method` and `## Methodologies` sections: how to phrase the blocker, the criterion for lifting it, and visibility for dependent tasks.

## Stage Process

The BLOCKED process is in `## Checklist` and `## Transitions`: which messages and comments to add specifically when blocking and how to return to work.

## Checklist

> No `=== END OF CHECKLIST ===` marker in the output → output truncated, rerun `kanban.py resume "." <slug> --full-checklist`.
- [ ] Report: "🚧 Blocked: <reason>."
- [ ] Describe exactly what's needed to lift the blocker (external input, access, decision).
- [ ] Record the blocker in the "Change History" via `add_comment.py`: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> communicator "<blocker description>" --section history`
- [ ] Suggest switching to another task.
- [ ] Add a comment via script: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> communicator "<essence of the blocker and what's needed to unblock it>" --attention`.
  💡 Long text (both comment steps above) — by default via stdin: `echo "<text>" | kanban.py comment ... --stdin` (SKILL §9).

## Method
- **A blocker is a specific shortfall.** Name exactly one thing: what external input, access, or decision is missing and who it depends on. "It's not working out" is not a blocker.
- **Criterion for lifting.** Immediately formulate what exactly needs to happen for work to resume — this turns the blocker into a verifiable condition.
- **Don't stall.** After recording the blocker, suggest the user switch to another task rather than waiting silently.
- **Visibility for dependents.** A blocker on the board must be readable by dependent tasks (`--attention` + a history entry).

## Methodologies

| Action | Apply |
|---|---|
| Phrasing the blocker | BLUF: the essence in the first line; SMART: Specific / Measurable / Assignable / Time-bound |
| Suggesting an alternative | Name a specific task from TODO that can be picked up while waiting for the blocker to be lifted |

## Transitions
- `blocked → in-progress` — the blocker is lifted for a task that was blocked from regular development; the developer resumes work themselves: `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> IN_PROGRESS`, then reads [`agents/developer.md`](developer.md).
- `blocked → rework` — the blocker is lifted for a task that was blocked from REWORK; return specifically to fixing: `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> REWORK`, then read [`agents/developer.md`](developer.md).
- `blocked → icebox` — the blocker is long-lasting or the task is frozen until an external decision; do not roll back to BACKLOG: `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> ICEBOX`, then read [`agents/archivist.md`](archivist.md).
