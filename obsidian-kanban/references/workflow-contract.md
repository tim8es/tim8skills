# Workflow Contract — автономный kanban loop

Этот файл — компактный runtime-контракт state machine для `obsidian-kanban`.
Он не заменяет role-файлы и SKILL.md: контракт определяет переходы, gates и hooks,
а подробные инструкции роли остаются в `agents/<role>.md`.

## Инварианты

- Каждая карточка в `TODO+` обязана иметь спеку в `tasks/specs/<slug>.md`.
- Полный основной путь задачи: `BACKLOG -> TODO -> IN PROGRESS -> TESTING -> IN REVIEW -> DONE`.
- Для задач без отдельной QA-ценности (исследования, тексты, механические doc-only/contract правки) допустим явный no-QA переход `IN PROGRESS -> IN REVIEW` или `REWORK -> IN REVIEW`; ревью всё равно обязательно.
- Остальные колонки нельзя пропускать; fast-lane может сокращать работу внутри роли, но не обходить gates.
- `move_card.py` — единственная штатная точка перехода для Obsidian-доски.
- Перед переходами в `TESTING`, `IN REVIEW`, `DONE` обязателен `kanban.py check "." --slug <slug>`.
- `owner` хранит автора задачи, не текущего исполнителя; переходы его не меняют.
- `step` меняется только через `kanban.py step` или `kanban.py update`.
- Комментарии роли пишутся только через `kanban.py comment` / `kanban.py update`.
- `!!!ВНИМАНИЕ!!!` in comments must be read upon entering a role.

## Checklist-Completion Gate (C6)

`hooks.before_move` reads the SOURCE column's spec and enforces a minimum checklist
completion before allowing three specific transitions (`_CHECKLIST_GATES` in `hooks.py`).
Calibrated conservatively — only these three, everything else (including all rollback
targets: `BLOCKED`, `BACKLOG`, `REJECTED`, `REWORK`) stays ungated because their
checklists are naturally still open.

| Transition | Gated section | Requirement |
|---|---|---|
| `TESTING -> IN REVIEW` | `Test Checklist` | at least 1 item `[x]` (complements, does not duplicate, the existing lint gate "≥1 [x] before DONE" — this fires earlier, at move time) |
| `IN REVIEW -> DONE` | `Review Checklist` | all items `[x]` (if the checklist has 0 items, not gated — nothing to check) |
| `UAT -> DONE` | `Review Checklist` | all items `[x]` (same rule as `IN REVIEW -> DONE`) |

On failure, `before_move` returns `HookResult(ok=False, ...)` naming the exact heading
and how many items are missing (e.g. `Review Checklist: 2/5 done — 3 item(s) still
unchecked`). `move_card.py` prints `hook_result.render()` to stderr and exits 1 before
any board/spec mutation — no change needed in the caller, the gate lives entirely in
`before_move`.

## State Machine

| Column | Status | Role | Role attachment | Entry packet | Required gates before exit | Allowed exits | Recovery |
|---|---|---|---|---|---|---|---|
| `BACKLOG` | `backlog` | analyst | `agents/analyst.md` | Problem statement, context, existing spec/card, user request | Spec exists; DoD and Test Checklist are concrete; output target clear | `TODO`, `ICEBOX` | Missing scope -> ask user or keep in BACKLOG; too large -> decompose into 3-7 tasks |
| `ICEBOX` | `icebox` | archivist | `agents/archivist.md` | Freeze reason, original context, reminder if needed | Reason recorded; no active dependency is blocked silently | `BACKLOG` | If still actionable -> move BACKLOG with reason |
| `TODO` | `ready` | planner | `agents/planner.md` | DoD, dependencies, priority, estimate, owner | `dependsOn` satisfied; DoD filled; estimate set; owner valid | `IN PROGRESS`, `BACKLOG` | Unmet dependencies or empty DoD -> BACKLOG with planner comment |
| `IN PROGRESS` | `in-progress` | developer | `agents/developer.md` | Step, DoD, subtasks, output, attention comments | Artifact/output exists; at least one DoD checked; developer comment; `check --slug` clean | `TESTING`, `IN REVIEW`, `BLOCKED` | Cannot continue -> BLOCKED; failed implementation -> stay IN PROGRESS with step/comment |
| `IN PROGRESS` for `RESEARCH:` | `in-progress` | researcher | `agents/researcher.md` | Research questions, source requirements, output artifact | Sources checked or access limitation stated; artifact has `## Источники`; `check --slug` clean | `TESTING`, `IN REVIEW`, `BLOCKED` | Source unavailable -> record limitation; if core source required -> BLOCKED |
| `BLOCKED` | `blocked` | communicator | `agents/communicator.md` | Blocker, needed decision/access/data, last working state | Blocker clearly stated; user/external ask recorded | `IN PROGRESS`, `REWORK`, `ICEBOX` | Missing decision -> stay BLOCKED; long freeze -> ICEBOX with reason |
| `TESTING` | `testing` | tester | `agents/tester.md` | Output links, Test Checklist, pending manual checks | Tests executed factually; pending browser checks marked; `check --slug` clean | `IN REVIEW`, `IN PROGRESS` | Test failed -> comment with `--attention`, move IN PROGRESS |
| `IN REVIEW` | `review` | reviewer | `agents/reviewer.md` | Spec, output, DoD, test result, review checklist | Output format valid; DoD/subtasks/test done; Review Checklist checked; task check clean; full lint has 0 ERROR | `DONE`, `UAT`, `REJECTED` | Quality issue -> comment with `--attention`, move REJECTED; needs user sign-off -> move UAT |
| `UAT` | `uat` | user (human) | `agents/uat.md` | Output links, reviewer approval, what to verify | User manually moves to DONE or REJECTED; agent only notifies | `DONE`, `REJECTED` | No response -> remind user; stale >2 days -> attention comment |
| `REJECTED` | `rejected` | debugger | `agents/debugger.md` | Reviewer or user rejection reason, failing evidence, expected behavior | Root cause/fix plan recorded with `--attention` | `REWORK` | Not enough info -> BLOCKED or stay REJECTED with specific ask |
| `REWORK` | `rework` | developer | `agents/developer.md` | Debugger fix plan, rejected evidence, prior output | Fix completed; regression covered; `check --slug` clean | `TESTING`, `IN REVIEW`, `BLOCKED` | Fix cannot proceed -> BLOCKED with blocker details |
| `DONE` | `done` | documenter | `agents/documenter.md` | Final output, review result, dependencies, pending manual checks | Done status/card checkbox set by move; closing comment added; parent/dependency checks done | terminal | If parent epic now complete -> move epic IN REVIEW; if DONE overflow -> suggest archive |

## Hook Events

| Event | Runs in | Purpose | Must not do |
|---|---|---|---|
| `before_move` | before board/spec write | Validate transition, process gates, task-specific clean check, checklist-completion gate (C6) | Hidden board/spec mutations |
| `after_move` | after successful move | Print role checklist, resume packet, next allowed commands | Skip role checklist |
| `on_resume` | explicit resume/loop tick | Rebuild compact context: column, role, step, attention comments, checklist state | Rewrite files |

## Hook Packets

### Resume Packet

```text
Task: <slug> — <title>
Column/status: <COLUMN>/<status>
Role: <role> -> agents/<role>.md
Step: <step|null>
Attention comments: <latest !!!ВНИМАНИЕ!!! or none>
Open checklists: DoD <n/m>, Test <n/m>, Review <n/m>
Output: <wikilinks / outside-workspace markers>
Blocking dependencies: <list or none>
Next allowed action: <command or stay/recover>
```

### Recovery Packet

```text
Cannot move <SOURCE> -> <TARGET>.
Gate: <gate name>
Reason: <specific failing condition>
Recovery: <exact command or edit target>
Next allowed action: stay in <SOURCE> until recovery passes.
```

## Process Gates

| Gate | Severity | Applies to | Rule | Recovery |
|---|---|---|---|---|
| `spec-required` | ERROR | `TODO+` | Card slug must have `tasks/specs/<slug>.md` | Create spec via `new-task` or move BACKLOG |
| `transition-allowed` | ERROR | all moves | Source/target pair must be in allowed exits | Use allowed next column or document exception |
| `pre-testing-check` | ERROR | move to `TESTING` | `check --slug` must pass | Fix task-specific errors |
| `pre-review-check` | ERROR | move to `IN REVIEW` | `check --slug` must pass; Test Checklist ready only for the `TESTING -> IN REVIEW` QA path | Fix tests/output or use explicit no-QA path from IN PROGRESS/REWORK |
| `pre-done-check` | ERROR | move to `DONE` | Review Checklist checked; `check --slug` passes | Complete review gate |
| `started-at-required` | ERROR | move `BACKLOG → TODO` | `startedAt` frontmatter must be stamped | Run `tags --start today` (analyst), then retry move |
| `planner-comment-required` | ERROR | move `TODO → IN PROGRESS` | `## Comments` must contain at least one `\| planner \|` line | Run `kanban.py comment ... planner "<...>"` (see `agents/planner.md`), then retry move |
| `research-routing` | WARN | `TODO+` | Title with `RESEARCH:`, `исследовать`, `research`, or URL should route to researcher | Add prefix or planner comment why developer route is intended |
| `history-chain` | WARN | `DONE` | Main-flow task should show required transition history | Add process note; investigate shortcut |
| `single-active-task` | WARN/ERROR by policy | `IN PROGRESS` | Agent should not hold multiple active tasks | Finish active task or explicitly block/suspend |

## Autoresearch-Style Improvement Loop

Autoresearch-style work is a pattern inside the normal kanban lifecycle, not a
replacement for it. Use it only when all five inputs are explicit:

1. **Hypothesis** — one sentence describing the workflow bottleneck or expected gain.
2. **Mutable surface** — the exact file(s) the experiment may edit.
3. **Metric** — an observable gate or proxy (`check --slug`, `test_kanban.py`, lint
   error count, command count, dashboard parity, or another concrete measure).
4. **Budget** — time/iteration limit; no indefinite loop hidden inside one role.
5. **Rollback/accept rule** — keep only changes that pass the metric and review;
   record discarded ideas in the task artifact/comment instead of leaving partial edits.

If any input is missing, use the ordinary kanban flow: one scoped card, smallest
change that addresses the observed issue, then TESTING and IN REVIEW. Do not add a
new runner, dependency, dynamic code injection, or parallel population search unless
three or more completed tasks show the same manual experiment bookkeeping pain.

## Recovery Examples

### TODO card has no spec

```text
Cannot move TODO -> IN_PROGRESS.
Gate: spec-required.
Reason: [[slug]] exists on board but tasks/specs/slug.md is missing.
Recovery: python .agents/skills/obsidian-kanban/scripts/kanban.py new-task "." <slug> "<title>" --owner user --board <board.md>
Next allowed action: run check --slug, then retry move.
```

### Review checklist is open

```text
Cannot move IN_REVIEW -> DONE.
Gate: pre-done-check.
Reason: Review Checklist has open items.
Recovery: python .agents/skills/obsidian-kanban/scripts/kanban.py check-item "." <slug> review --all
Next allowed action: python .agents/skills/obsidian-kanban/scripts/kanban.py check "." --slug <slug>
```

### Research-like task routed to developer

```text
Warning: task title looks research-like but does not start with RESEARCH:.
Recovery: rename/recreate with RESEARCH: prefix, or add planner comment explaining developer route.
Next allowed action: continue only after routing decision is explicit.
```

## Implementation Notes

- `workflow-contract.md` should be read by hook/runtime implementations, not copied into every role file.
- Hooks should prefer deterministic validation and stdout packets over mutation.
- Any mutation still goes through existing kanban commands (`move`, `update`, `comment`, `tags`, `check-item`).
- If a hook needs policy variation, default to strict for `ERROR` and informative for `WARN`.
