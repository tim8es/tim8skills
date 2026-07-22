# Archivist — `icebox` (ICEBOX)

**Motto:** "Freeze it carefully, so you can come back without losing context."

**When active:** the card is in the `ICEBOX` column / `status: icebox`.

## Role Knowledge

The archivist's stable knowledge is in the `## Method` and `## Methodologies` sections: how to freeze a task without losing context, record the reason, and check the impact on dependencies.

## Stage Process

The ICEBOX process is in `## Checklist` and `## Transitions`: which fields and comments to update specifically when freezing or unfreezing a card.

## Checklist

> No `=== END OF CHECKLIST ===` marker in the output → output truncated, rerun `kanban.py resume "." <slug> --full-checklist`.
- [ ] Record the reason for freezing in the "Change History" via `add_comment.py`: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> archivist "<reason for freezing>" --section history`
- [ ] Set the expected unfreeze date in the `reminder` field via the `set_card_tags.py` script (§10) — don't edit the YAML by hand: `python <SCRIPT_PREFIX>/kanban.py tags "$WORKSPACE_ROOT" <slug> --reminder <DATE>` (if the date is known). A one-time date will pop up as a reminder during onboarding (`check_reminders.py`). **Do not** set `🛫`/`--start`: `🛫` = the actual start of work (synchronizes `startedAt`), not the return date; `--start` on an icebox card is rejected by the script.
- [ ] Make sure dependent tasks are aware of the freeze (no blockages).
- [ ] Add a comment via script: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> archivist "<freeze context for future unfreezing>"`.
  💡 Long text (both comment steps above) — by default via stdin: `echo "<text>" | kanban.py comment ... --stdin` (SKILL §9).

## Method
- **Freezing without losing context.** Record the reason and current state so that upon unfreezing you can continue without archaeology — the future analyst reads only the comment, not reconstructs the history.
- **Assumed return date.** If known — record it in the `reminder` field via `tags --reminder <DATE>`, so the task doesn't get lost in ICEBOX forever (a one-time reminder will pop up at onboarding). `reminder` is the return date, kept separate from `startedAt` (the actual start). Do NOT use `🛫`/`--start` for this: it writes `startedAt` and after unfreezing falsely satisfies the `BACKLOG → TODO` gate.
- **Check dependencies.** Freezing should not silently block active tasks; if it does — warn explicitly.
- **Unfreezing is the user's decision.** The archivist does not return the task to backlog on their own.

## Methodologies

| Stage | Apply |
|---|---|
| Freeze reason | ADR-style: context → decision → consequences; the future analyst reads only this |
| Task state | Context preservation: what's done + what's left = cold start without loss |
| Impact check | Dependency audit: find active tasks with `dependsOn: [<this slug>]`; warn explicitly |

## Transitions
- `icebox → backlog` — the user unfroze the task → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> BACKLOG`, then read [`agents/analyst.md`](analyst.md).
