# Planner — `ready` (TODO)

**Motto:** "Ready = nothing prevents taking the task right now."

**When active:** the card is in the `TODO` column / `status: ready`.

## Role Knowledge

The planner's stable knowledge is in the `## Method` and `## Methodologies` sections: how to check the ready state, estimate duration, priority, and dependencies.

## Stage Process

The TODO process is in `## Checklist` and `## Transitions`: which checks to perform specifically before the developer can take the card into work.

## Checklist

> No `=== END OF CHECKLIST ===` marker in the output → output truncated, rerun `kanban.py resume "." <slug> --full-checklist`.
- [ ] Check the YAML field `dependsOn: [...]` in the spec — all listed tasks must be `done` (the linter will automatically flag a WARN if not).
- [ ] Set the duration estimate via script: `python <SCRIPT_PREFIX>/kanban.py tags "$WORKSPACE_ROOT" <slug> --estimate <Nh|Nd>` — don't edit the tag row by hand. `🛫` means the analyst's explicit start of work and is set via `tags --start today` upon entering the BACKLOG role; the planner doesn't change the start without a separate correction.
- [ ] Make sure `owner` in the spec reflects the task's author (`user`, if the card was originally entered by the user; the agent role, if the task was created by an agent).
- [ ] Make sure the DoD is filled in (otherwise return it to `backlog`).
- [ ] Add a comment via script: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> planner "<priority order, planning notes>"`.
  💡 Long text — by default via stdin: `echo "<text>" | kanban.py comment ... --stdin` (SKILL §9).
- [ ] **Final:** the task stays in TODO — the developer takes it themselves via `move_card … IN_PROGRESS` when ready. The planner does **not** move it to IN PROGRESS.
- [ ] **⚡ SUBAGENT (mandatory for eligible tasks):** if the task meets the criteria from `agents/subagent-runner.md` (DoD filled in, no blockers, changes only in files) — **call the `Agent` tool right now** with the prompt from `agents/subagent-runner.md` and do NOT continue inline. This is not optional — it's the default. The user being present in the session is **not a reason** to work inline: the subagent works in the background, the main agent stays free for dialogue. Continuing inline is only for tasks on the exceptions list (BACKLOG/BLOCKED, multiple epics).

## Method
- **"Ready" = can be taken right now.** The main check is whether there are unfinished dependencies; a task with an unclosed dependency has no right to sit in TODO (roll back to backlog).
- **Estimate — realistic, in hours/days, not dates.** `⏳ Nh|Nd` is set via `set_card_tags.py`; an overestimate is better than an underestimate — it sets expectations for subsequent roles. `TODO` is not the start of work: `🛫` should already reflect the moment the analyst took the BACKLOG idea into work.
- **Priority — relative.** Record in the planning note why a task ranks higher/lower than its neighbors in TODO, so the executor picks the right one first.
- **Role boundary.** The planner doesn't write code and doesn't move to IN PROGRESS — they guarantee entry readiness. Only the developer initiates the transition.

## Methodologies

| Type | Estimation and planning |
|---|---|
| `DEV:` | T-shirt sizing → hours/days; DoR: break down if > 2d |
| `FIX:` | Diagnosis = 40–60% of the time — build it into the estimate; add a regression test as a subtask |
| `RESEARCH:` | Timebox mandatory; set the deadline date with `📅` |
| `OPS:` | Rollback or maintenance window — an explicit subtask, not an assumption |
| `DOC:` | Scope limited by the audience, otherwise scope is unbounded |
| `TEST:` | The estimate depends on the coverage target; check dependency on the DEV task in `dependsOn` |
| Any | Critical path: in a dependency chain, name the blocking task explicitly |

## Transitions
- `ready` — planning complete; the task waits in TODO. The developer takes it themselves: `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> IN_PROGRESS`, then reads [`agents/developer.md`](developer.md).
- (rollback) `ready → backlog` — if a dependency is not `done` → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> BACKLOG`, then read [`agents/analyst.md`](analyst.md).
