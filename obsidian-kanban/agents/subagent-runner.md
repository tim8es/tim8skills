# Role: SubagentRunner — launching subagents on tasks

This role is activated by the `/launch-agents --task <slug>` command or when the main agent decides to delegate a task to a subagent (criteria below).

---

## When to delegate a task to a subagent

**Delegate by default** if the task meets ALL the criteria below. This is the default mode, not the exception: all the per-task "scaffolding" (role checklists, spec churn, lint, re-dumping files) then lives in the subagent's context, and the main agent pays ~1 line of summary instead of hundreds of lines of scaffolding. Running a task inline in the main context is a deliberate choice for the cases in the exceptions list, not the default.

| Criterion | Check |
|---|---|
| Task is in TODO or beyond | `status: ready` — the analyst has already done the analysis |
| DoD filled in and specific | Each item is verifiable without a dialogue with the user |
| No unclosed dependencies | `dependsOn` — all `done` or `null` |
| Doesn't require a human decision | No blockers like "need to ask", "need access" |
| Changes — files only | Doesn't require authenticated network requests |

Work inline (don't delegate):
- Task is in BACKLOG (requires the analyst — dialogue with the user)
- Task is BLOCKED
- Task touches several epics at once

---

## Prompt for the task subagent

```
WORKSPACE_ROOT: <absolute path to the workspace>
TASK_SLUG: <task slug>
SKILL_PATH: <absolute path to the obsidian-kanban skill's SKILL.md>
SCRIPT_PREFIX: <SCRIPT_PREFIX — filled in by the caller agent from ONBOARDING.md>
CURRENT_DATE: <YYYY-MM-DD>

You are an AI agent managing Obsidian Kanban tasks. Today's date: CURRENT_DATE.
Use CURRENT_DATE for all time fields.

Run scripts from the project root: python <SCRIPT_PREFIX>/<script>.py (not cd, not an absolute path).

1. Read ONBOARDING.md (<SKILL_PATH>/../ONBOARDING.md) — SCRIPT_PREFIX and paths.
   Read the task's spec (step 2), determine the status → read agents/<role>.md for that status.
   Read SKILL.md only in a non-standard situation (unfamiliar column, rule conflict) —
   and only the needed §N, not the whole file.
2. Read the task's specification: <WORKSPACE_ROOT>/tasks/specs/<TASK_SLUG>.md
3. Determine the task's current status and the corresponding role (§5 of SKILL.md → column↔role table).
4. Move the task through all remaining roles up to DONE:
   - The role's checklist arrives in `move_card.py`'s stdout automatically (a trimmed version without "Method") — a separate Read of agents/<role>.md is only needed when resuming without stdout. Read the spec once per role, then mutate only via scripts (read-once).
   - Move cards via <SCRIPT_PREFIX>/kanban.py move (not manually)
   - check.py — only before transitions and when spec YAML fields change (§9): python <SCRIPT_PREFIX>/kanban.py check <WORKSPACE_ROOT> --slug <TASK_SLUG>
   - Add comments via <SCRIPT_PREFIX>/kanban.py comment (don't edit sections by hand)
5. If you hit a blocker — move it to BLOCKED, describe the blocker in a comment, finish.
6. Return the result: "DONE: <TASK_SLUG>" or "BLOCKED: <TASK_SLUG> — <reason>".
```

---

## Launching several tasks in parallel

If there are several independent tasks in TODO — launch subagents in parallel (all `Agent` tool calls in one response block). Subagents safely compete: `move_card.py` reads the file before writing, conflicts are excluded for different tasks.

Don't run tasks in parallel that use the same artifact file as output.

---

## Constraints

| Risk | Mitigation |
|---|---|
| Concurrent edits to the same file | Don't run tasks with the same output file in parallel |
| Task requires dialogue with the user | Move it to BLOCKED with a description of the blocker |
| Subagent didn't find the task in TODO | Check the status; if BACKLOG — don't take it, finish |
| Subagent's context overflowed | Finish in BLOCKED, hand off to the main agent |
| A nested role subagent (tester/reviewer, see "Role Subagents" in `agents/developer.md`) launched in the background | Inside an already-delegated subagent, call nested role subagents only synchronously (foreground) — the subagent doesn't get an async wakeup when a background child completes and hangs waiting; found in dogfooding on 2026-07-04 (a dashboard export task got stuck in TESTING) |
