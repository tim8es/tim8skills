# Onboarding — Obsidian Kanban

Read on every skill activation (`/kanban`, `/tasks`, `/board`) **before** any actions.

---

## SCRIPT_PREFIX (first onboarding step)

Before any script commands, determine `SCRIPT_PREFIX` — take the **first existing** directory from an ordered list of candidates:

1. `.agents/skills/obsidian-kanban/scripts/` (skill dev repo under `.agents/`)
2. `skills/obsidian-kanban/scripts/` (skill dev repo, previous location)
3. `obsidian-kanban/scripts/` (canonical path of the installed skill)

`SCRIPT_PREFIX` = the first of these paths for which the directory exists. The list is ordered from more specific to canonical, so it's resilient to the skill being moved.

**Important:** check candidates STRICTLY in order 1→2→3 and take the first existing one — don't rely on the order of results from one generic `Glob`, since `Glob` sorts found paths by modification time (mtime), not by position in this list, and with several matches it may not return the first candidate first. The correct way is to check each candidate's existence separately (e.g. `Glob pattern="<candidate-1>/kanban_utils.py"`, and if empty — the next candidate) and stop at the first one found.

In all commands below, substitute the found `<SCRIPT_PREFIX>` in place of `obsidian-kanban/scripts/`.

---

## ADAPTER_TYPE (second onboarding step)

After determining `SCRIPT_PREFIX`, determine `ADAPTER_TYPE`:

1. Run `Grep pattern="kanban-plugin: board" path="tasks/"` (or equivalent)
2. If at least one file is found → `ADAPTER_TYPE = obsidian`
3. Otherwise → ask the user: "Which task-management tool are you using? (obsidian / linear / trello / other)"

Load the adapter file. For Obsidian the current file is called `obsidian-kanban.md`;
if `adapters/<ADAPTER_TYPE>.md` is missing while `ADAPTER_TYPE=obsidian`, read
`adapters/obsidian-kanban.md`.

```
Read <SCRIPT_PREFIX>/../adapters/<ADAPTER_TYPE>.md
```

The adapter file contains the concrete command syntax for all 9 mandatory interface operations plus the optional `inject_role_prompt` (see [`references/adapter-interface.md`](references/adapter-interface.md)).

> **For a new adapter:** create `adapters/<name>.md` following the pattern of [`adapters/obsidian-kanban.md`](adapters/obsidian-kanban.md). No need to change `agents/*.md` — they work through abstract operations.

---

## Paths (deterministic)

`WORKSPACE_ROOT` = the current working directory = the directory containing `<SCRIPT_PREFIX>/..`.
No need to ask the user — the path is always `"."`.

| What                  | Path from WORKSPACE_ROOT                        |
| -------------------- | --------------------------------------------- |
| Scripts (dispatcher) | `<SCRIPT_PREFIX>/kanban.py <command>`          |
| Boards                | `tasks/<project-slug>.md`                     |
| Specs         | `tasks/specs/<slug>.md`                       |
| Dashboard              | `tasks/kanban-dashboard.html`                 |
| Templates              | `<SCRIPT_PREFIX>/../templates/`               |
| Agent roles         | `<SCRIPT_PREFIX>/../agents/`                  |
| Dashboard source     | `<SCRIPT_PREFIX>/../assets/kanban-dashboard.html` |

**Invocation rule:** always run from the project root through the single dispatcher:

```
python <SCRIPT_PREFIX>/kanban.py <command> "." ...
```

Forbidden: calling `<script>.py` directly bypassing the dispatcher, `cd` into a subfolder, absolute paths to scripts (`python "D:\..."`).

For columns with spaces in Obsidian scripts, prefer the space-free aliases:
`IN_PROGRESS` and `IN_REVIEW`. The canonical board names remain `IN PROGRESS` and
`IN REVIEW`, but the aliases are more robust in Windows/Codex shell wrappers.

---

## Dependencies

**Python 3.x** — the only dependency. No `pip install` needed (stdlib only).

Check:

```
python --version
```

If not found:

| OS      | Installation                        |
| ------- | -------------------------------- |
| Windows | `winget install Python.Python.3` |
| macOS   | `brew install python`            |
| Linux   | `apt install python3`            |

If the `python` command isn't found but `python3` is — use `python3` in all invocations.

---

## New Project (`tasks/` doesn't exist)

One command creates the whole structure:

```
python <SCRIPT_PREFIX>/kanban.py setup "." <project-slug>
```

Creates: `tasks/`, `tasks/specs/`, `tasks/<project-slug>.md`, `tasks/kanban-dashboard.html`.
Idempotent — running it again doesn't overwrite existing files.

---

## Existing Project (`tasks/` exists)

One command:

```
python <SCRIPT_PREFIX>/kanban.py reminders "."
```

- **exit 0** → no issues; use the summary `📋 <board>: BACKLOG n · TODO m · …` printed by `reminders` itself (it eliminates manual reading of board files); read the actual `tasks/<slug>.md` board only when details of a specific task are needed
- **exit 2** → report the found issues (one or several):
  - **Reminders** → for each, ask "take into work now?"; if one-off — "delete or reschedule?"
  - **Stuck in UAT** → a task in UAT with no activity for ≥ 2 days (counter from `updatedAt` — resets on any spec edit); needs a user decision (accept → DONE or reject → REJECTED)
  - **Active-column overflow** → a column contains >10 tasks; move the excess to ICEBOX
  - **DONE overflow** → recommend archiving old DONE cards

In both cases `check_reminders.py` automatically refreshes `tasks/kanban-dashboard.html` from `assets/` — the dashboard is always up to date after onboarding.

---

## Non-Standard Situations

| Situation                             | Action                                                                 |
| ------------------------------------ | ------------------------------------------------------------------------ |
| `tasks/` exists, but no board at all | Run `kanban.py setup "." <slug>` to create the first board          |
| Several boards in `tasks/`           | Show the list to the user; work with the one specified or ask          |
| `obsidian-kanban/` not found         | The skill isn't installed; tell the user and stop                |
| User asks for "the board in the browser" | Read [`references/dashboard.md`](references/dashboard.md)            |

---

## Script Allowlist (optional)

All skill operations run through the single dispatcher: `python <SCRIPT_PREFIX>/kanban.py <command> "." ...`.
Without an allowlist, every Python invocation requires user confirmation. Thanks to the dispatcher,
the whole skill is covered by **one** pattern instead of one line per script.

> ⚠️ **Only relative paths from the project root** (`<SCRIPT_PREFIX>` without drive/leading slash). Absolute paths (`python "D:\...\scripts\..."`) and `cd ... && python` in the allowlist are **forbidden** — if the skill moves (e.g. `skills/` → `.agents/skills/`), they silently stop matching, and the user gets prompted on every call again. This is the same cause as the SCRIPT_PREFIX drift.

> The path in the blocks below is for the canonical path (`obsidian-kanban/scripts/`). If SCRIPT_PREFIX is different (`.agents/skills/obsidian-kanban/scripts/` or `skills/obsidian-kanban/scripts/`) — replace `obsidian-kanban/scripts/` with the actual SCRIPT_PREFIX.

**During onboarding** tell the user:

> The skill uses a Python dispatcher (`kanban.py`) to manage tasks. To make commands run
> without confirmation, I can add one pattern to the exceptions (`permissions.allow` in `.claude/settings.json`).
> Enable automatic execution?

If the user agrees — determine the active Python command (`python` or `python3`) and add the corresponding block to the project's `.claude/settings.json`.

**Windows** (`python`):

```json
{
  "permissions": {
    "allow": [
      "Bash(python obsidian-kanban/scripts/kanban.py *)",
      "PowerShell(python obsidian-kanban/scripts/kanban.py *)"
    ]
  }
}
```

**macOS / Linux** (`python3`):

```json
{
  "permissions": {
    "allow": [
      "Bash(python3 obsidian-kanban/scripts/kanban.py *)"
    ]
  }
}
```

> If the platform is unknown — check `python --version`; if not found, use the `python3` block.

**How to apply:**

1. Read `.claude/settings.json` (create it if it doesn't exist).
2. If a `permissions.allow` field already exists — append the lines to the existing array, without duplicating.
3. If the file doesn't exist — create it with the given content.
4. Tell the user: `✅ Allowlist configured. kanban.py commands will run without confirmation.`

If the user declined — proceed without changes, don't offer again in the current session.
