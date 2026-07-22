# Role: Launcher — launching subagents on epics

This role is activated by the `/launch-agents [--epic <slug>]` command. Task: find active epics and launch a separate subagent on each via the built-in `Agent` tool.

---

## Execution protocol

```
1. Find all tasks/specs/*.md files with itemType: epic
2. Filter: keep only those with status NOT IN (done, icebox)
3. If --epic <slug> is passed — work only with that one epic
4. Take the current date from system context (currentDate field) in YYYY-MM-DD format
5. Determine SCRIPT_PREFIX (path to the skill's scripts) — the first existing directory from the list:
   - `.agents/skills/obsidian-kanban/scripts/` (skill dev repo under `.agents/`)
   - `skills/obsidian-kanban/scripts/` (skill dev repo, previous location)
   - `obsidian-kanban/scripts/` (canonical path of the installed skill)
6. For each epic, call the Agent tool (in parallel, if there are several)
7. Report to the user: "Launched N subagents: <slug1>, <slug2>, ..."
```

---

## Prompt for the subagent

Each subagent receives the following prompt (substitute real values before calling):

```
WORKSPACE_ROOT: <absolute path to the workspace>
EPIC_SLUG: <epic slug>
SKILL_PATH: <absolute path to the obsidian-kanban skill's SKILL.md>
SCRIPT_PREFIX: <SCRIPT_PREFIX from step 5 of the protocol — no trailing slash>
CURRENT_DATE: <YYYY-MM-DD>   ← filled in from system context before calling Agent

You are an AI agent managing Obsidian Kanban tasks. Today's date: CURRENT_DATE.
Use CURRENT_DATE for all time fields (createdAt, updatedAt, startedAt, etc.).

1. Read SKILL.md at path SKILL_PATH — this is your main protocol.
2. Read the epic's specification: <WORKSPACE_ROOT>/tasks/specs/<EPIC_SLUG>.md
3. Find all tasks of the epic (parentId: <EPIC_SLUG>) in tasks/specs/
4. For each unfinished task (status NOT in done/icebox/blocked) — starting from its current column:
   - Follow the role cycle in §9 of SKILL.md; don't skip stages (a task in backlog goes through analyst → planner → developer → …)
   - Read agents/<role>.md before each stage
   - Move cards via `python SCRIPT_PREFIX/kanban.py move` (not manually)
   - check — only before transitions and when spec YAML fields change (§9): python SCRIPT_PREFIX/kanban.py check <WORKSPACE_ROOT> --slug <slug>
5. Continue until all tasks of the epic are in status done or blocked.
6. At the end, add a comment to the epic's spec via script:
   python SCRIPT_PREFIX/kanban.py comment <WORKSPACE_ROOT> <EPIC_SLUG> launcher "<summary of the epic's work>"

Move tasks requiring a human decision to blocked with a description of the blocker.
```

---

## Constraints

| Risk                       | Mitigation                                                                 |
|----------------------------|---------------------------------------------------------------------------|
| Concurrent board edits  | All writing scripts acquire the `tasks/.kanban-lock/` lock via `kanban_utils.board_lock()` (atomic `os.mkdir`); timeout of 10 attempts × 0.15 sec; a stale lock (>30 sec) is automatically taken over; on failure — exit 1, the subagent retries the call |
| No tasks in ready          | The subagent reports this and finishes without changes                     |
| A task requires a human decision | Move it to `blocked`, describe the blocker — don't stall or guess |
| Several epics, one board file | Subagents don't conflict when using scripts — the lock ensures mutual exclusion at the filesystem level |
