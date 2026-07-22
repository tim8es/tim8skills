# Scripts — automation scripts documentation

This folder contains scripts for working with the Obsidian Kanban workspace. All scripts are written in **Python 3** and require no external dependencies (stdlib only). `pip install` is not needed.

**Source-of-truth hierarchy** (see [SKILL.md §10](../SKILL.md)): (1) script behavior — its docstring (`--help`), the docstring takes priority in case of discrepancy; (2) when and in what order to call — SKILL.md §10 and `agents/<role>.md`; (3) this README — navigational reference.

---

## Summary table

### Core

Used in every task work cycle — these 12 commands are enough for the full BACKLOG → DONE flow.

| Script | Purpose | Writes files? |
|---|---|---|
| `setup.py` | Workspace initialization: creates `tasks/`, `tasks/specs/`, project board, dashboard; idempotent | Yes (structure) |
| `check_reminders.py` | Check reminders and update the dashboard | Yes (dashboard) |
| `new_task.py` | Task/subtask spec scaffolder (YAML + sections, dates with system time) | Yes (spec) |
| `new_epic.py` | Epic spec scaffolder | Yes (spec) |
| `move_card.py` | Move a card between columns | Yes (board + spec) |
| `set_card_tags.py` | Edit a card's emoji tags; `--start` syncs `startedAt`; `--title` — canonical rename (alias + spec H1) | Yes (board + spec) |
| `update.py` | Batch spec mutator: itemType + step + checkboxes (DoD/Subtasks/Test/Review) + comment under a single lock | Yes (spec) |
| `add_comment.py` | Add an entry to `## Comments` / `## Changelog` | Yes (spec) |
| `check.py` | Combined sync + lint for a single spec | Yes (via sync) |
| `resume.py` | Single context-recovery entry point: no flags — compact packet; `--full-checklist` — full role checklist §9; `--brief` — spec summary | No (stdout only) |
| `next_task.py` | Next task by priority: REWORK → TODO → BACKLOG | No (stdout only) |
| `archive_done.py` | Move old DONE cards to an archive board | Yes (board + archive) |

### Utility / advanced

Fully functional commands, but not the agent's first choice — call directly only for a specific reason, not as an equal alternative to the composites above:
- `lint` — full scan of the whole board outside a single-task gate (the `check` composite already covers the gate before transitioning a single spec).
- `sync` — forced YAML normalization without lint.
- `set-type`/`step`/`check-item` — pointwise edit of a single field instead of the `update` composite, when a batch isn't needed.
- `metrics` — KPI snapshot of the autonomous loop outside a single task's role cycle.

| Script | Purpose | Writes files? |
|---|---|---|
| `lint_board.py` | Board format and spec YAML diagnostics, including `## Related` bidirectionality | No (report only) |
| `sync_properties.py` | Spec YAML property normalization | Yes (specs) |
| `set_step.py` | Set the YAML `step` field (progress marker) | Yes (spec) |
| `set_item_type.py` | Set the YAML `itemType` field (epic/task/subtask/unassigned; `set-type` command) | Yes (spec) |
| `check_item.py` | Check/uncheck checkboxes in spec sections (DoD/Subtasks/Test/Review) | Yes (spec) |
| `loop_metrics.py` | Read-only KPI snapshot of the autonomous loop for baseline/current/target comparison | No (stdout only) |

### Other (direct board card management)

Neither part of the core nor the advanced diagnostics — pointwise operations on the card itself (epic decomposition §9, one-off orphan-card cleanup).

| Script | Purpose | Writes files? |
|---|---|---|
| `add_card.py` | Add a card to the board | Yes (board) |
| `remove_card.py` | Remove a card from the board under board_lock; WARNING if a spec exists | Yes (board) |

### Internal modules (not called directly)

| Script | Purpose | Writes files? |
|---|---|---|
| `kanban_utils.py` | Standard aggregating import facade (re-exports `board_io` / `workflow` / `spec_mutations`) | — |
| `board_io.py` | Board I/O: parsing, serialization, lock, resolution | — |
| `workflow.py` | Column↔role mapping, role_checklist, next-task lookup | — |
| `spec_mutations.py` | Spec scaffolding and mutations | — |
| `lint_board_rules.py` | Data-only reference tables/regex for `lint_board.py` without a CLI surface | — |
| `hooks.py` | Runtime transition hooks: `before_move` (gates, checklist completion), `after_move`, resume/recovery packets | — |
| `role_prompt.py` | Renders the column role checklist (compact/full); shared engine for `move_card` and `resume --full-checklist` | — |
| `spec_brief.py` | Renders a compact spec summary for `resume --brief` | — |

---

## new_task.py / new_epic.py

Spec scaffolders. Creating a spec is the only unscripted and most fragile workspace mutation (14 YAML fields, a 3-part `flowId`, a canonical set of sections). The scripts generate a spec from a template (§6 `templates/task.md` / `templates/epic.md`) with a full YAML block and stamp `createdAt`/`updatedAt` with **system time** — the model no longer writes dates by hand (it doesn't know "today"). The spec is born passing `check.py` with no ERROR.

The project for `flowId` is taken from the name of the single board in `tasks/` (or `--board`). Shared engine — `kanban_utils.scaffold_spec` / `build_spec_text` (no duplication between the two scripts); YAML is assembled via `sync_properties.render_frontmatter` (single field order, §8).

```bash
python <SCRIPT_PREFIX>/kanban.py new-task <WORKSPACE_ROOT> <slug> "<TAG: Title>" [options]
python <SCRIPT_PREFIX>/kanban.py new-epic <WORKSPACE_ROOT> <slug> "<TAG: Title>" [options]
```

**Flags:**
- `--epic <slug>` — `parentId` (only `new_task.py`)
- `--subtask` — `itemType: subtask` instead of `task` (only `new_task.py`)
- `--priority high|medium|low` — priority (default `medium`)
- `--owner <role|user>` — task author (only `new_task.py`; default `analyst`; use `user` for a spec created from a user card)
- `--card` — immediately add the card to BACKLOG (`add_card.py` logic)
- `--column <COLUMN>` — target column for `--card` (only `new_task.py`; default `BACKLOG`)
- `--board <name.md>` — board file name, if there are several in `tasks/`
- `--dry-run` — show the spec without writing

**Exit codes:** `0` — created/simulated; `1` — error (duplicate slug → file not overwritten, board not found/ambiguous, `add_card` error with `--card`).

---

## add_card.py

Deterministic card addition to the board. Replaces manual editing — a source of format errors (broken indentation, orphaned tag lines). Inserts the card into the target column and rebuilds the board in the canonical format (§6 SKILL.md).

```bash
python <SCRIPT_PREFIX>/kanban.py add-card <WORKSPACE_ROOT> <slug> "<TAG: Title>" [options]
```

**Flags:**
- `--column <COLUMN>` — target column (default `BACKLOG`)
- `--tags "<string>"` — tag string without a tab (default `➕ <today>`)
- `--board <name.md>` — board file name, if there are several boards in `tasks/`
- `--dry-run` — show the result without writing

**Exit codes:** `0` — added/simulated; `1` — error (duplicate slug, unknown column, board not found).
---

## remove_card.py

Deterministic card removal from the board under board_lock. Removes the card line and the tags line. Does not remove the spec — only the card from the board. If the spec exists, prints a WARNING.

```bash
python <SCRIPT_PREFIX>/kanban.py remove-card <WORKSPACE_ROOT> <slug> [options]
```

**Flags:**
- `--board <name.md>` — board file name, if there are several boards in `tasks/`
- `--dry-run` — show the result without writing

**Exit codes:** `0` — removed/simulated; `1` — error (card not found, board not found).

---

## move_card.py

Deterministic card transfer between columns. Moves the tags line together with the card, sets the checkbox (`[x]` in DONE), stamps `✅ <date+time>` when moved to DONE, syncs `status` in the spec, adds an entry to `## Changelog`, fills timestamp fields for subsequent stages (`testingAt`, `reviewAt`, `doneAt`). `startedAt`/`🛫` are not set by a transition: the analyst sets them with the explicit `tags --start today` command when taking a BACKLOG idea into work. `owner` is not changed: it is the task's author, not the current assignee. `TODO` means ready and is not considered the start of work.

After a successful move, it prints to stdout **the checklist for the target column's role** (`=== ROLE: <name> (<column>) ===` + the content of `agents/<role>.md`) — the role's instructions arrive in the agent's context automatically, without a separate `Read` (§9: hard stop = execute the printed checklist). For `IN PROGRESS`, the `RESEARCH:` prefix in the card title routes to `researcher.md` instead of `developer.md`. Column↔role mapping is a single dictionary, `workflow.COLUMN_TO_ROLE`. A missing role file — WARN to stderr, the move is not broken.

```bash
python <SCRIPT_PREFIX>/kanban.py move <WORKSPACE_ROOT> <slug> <COLUMN> [--board <name.md>] [--dry-run] [--full]
```

**COLUMN:** `BACKLOG | ICEBOX | TODO | IN PROGRESS | BLOCKED | TESTING | IN REVIEW | UAT | REJECTED | REWORK | DONE`

Shell-safe aliases for columns with spaces: `IN_PROGRESS`, `IN-PROGRESS`, `IN_REVIEW`, `IN-REVIEW`, `INREVIEW`.

**Flags:**
- `--board <name.md>` — board file name, if there are several in `tasks/`
- `--dry-run` — show the result without writing (the role checklist is not printed)
- `--full` — print the full text of the role checklist, including command blocks. By default (without `--full`) the checklist is rendered compactly: only headings and role checklist lines, without command blocks (token savings)

**Exit codes:** `0` — moved/simulated; `1` — card not found or unknown column.

---

## loop_metrics.py

Read-only KPI snapshot of the autonomous loop for baseline/current/target comparison — stdout only, writes nothing. Computes kanban-specific metrics: lint errors/warnings, orphan cards, active tasks, history-chain, overflow (§10 SKILL.md).

```bash
python <SCRIPT_PREFIX>/kanban.py metrics <WORKSPACE_ROOT>
python <SCRIPT_PREFIX>/kanban.py metrics <WORKSPACE_ROOT> --board claude-obsidian-kanban.md
python <SCRIPT_PREFIX>/kanban.py metrics <WORKSPACE_ROOT> --project claude-obsidian-kanban
```

**Flags:**
- `--board <name.md>` — count only one board and its project specs
- `--project <slug>` — same, by board stem (`<slug>.md`)

**Exit codes:** `0` — snapshot printed; `2` — `tasks/` folder not found.

## resume.py

Single context-recovery entry point for an agent that lost state (session interruption, truncated stdout, conversation resume). Without flags — a read-only compact packet for the given slug, or, if no slug is given, for the single active task in `IN PROGRESS`, `REWORK`, `TESTING`, `IN REVIEW`, `UAT`, or `BLOCKED`. The command does not mutate boards or specs; stdout is the agent's primary interface after an interruption or wakeup.

```bash
python <SCRIPT_PREFIX>/kanban.py resume <WORKSPACE_ROOT> [slug] [--board <name.md>]
python <SCRIPT_PREFIX>/kanban.py resume <WORKSPACE_ROOT> [slug] --full-checklist
python <SCRIPT_PREFIX>/kanban.py resume <WORKSPACE_ROOT> [slug] --brief
```

**The packet contains (without flags):** the card, column/status, role, step, the last `!!!ВНИМАНИЕ!!!`, DoD/Test/Review summary, output links, and the next allowed action per the workflow contract.

**`--full-checklist`:** prints the full role checklist §9 for the task's current column — the same output that `move_card.py` gives automatically after a move; used for self-heal (truncated stdout) and by external adapters (Linear/Trello/GitHub Projects), where the card move happens via an MCP tool rather than `move_card.py`. Render logic — `role_prompt.print_role_checklist()`.

**`--brief`:** prints a compact spec summary — saves 50-70% of tokens compared to a full `Read` when entering a role. Outputs only actionable parts: key YAML fields (`status`/`step`/`priority`/`owner`), unchecked `[ ]` items from DoD/Subtasks/Test/Review Checklist, the whole `## Output / Artifacts` section, `!!!ВНИМАНИЕ!!!` lines from `## Comments`. Checked `[x]` items and regular comments are not printed; sections with no unchecked items are omitted. Render logic — `spec_brief.print_spec_brief()`.

**Exit codes:** `0` — packet/checklist/brief printed, or (without flags and no active task) the queue is empty — shows the next task from REWORK/TODO/BACKLOG; `1` — multiple active tasks (slug required), card/spec not found, or ambiguous board.

## add_comment.py

Safe append to a spec's `## Comments` or `## Changelog`. Replaces manual editing — with a combined edit it's easy to accidentally delete the section heading. The script inserts a `YYYY-MM-DD HH:MM:SS | <role> | <text>` line at the end of the section, sorts entries by timestamp (newest first), updates `updatedAt`. If the section doesn't exist, it creates it (self-healing).

```bash
python <SCRIPT_PREFIX>/kanban.py comment <WORKSPACE_ROOT> <slug> <role> "<text>" [options]
# Recommended path for long/verbose text (spaces, quotes, Cyrillic) — stdin, no shell-quoting:
echo "Developer comment with spaces" | python <SCRIPT_PREFIX>/kanban.py comment <WORKSPACE_ROOT> <slug> <role> --stdin
```

**Flags:**
- `--stdin` — read the text from stdin instead of a positional argument (pipe-friendly; use by default for text with spaces/special characters — quoting retries on Windows/Codex shell should trend to zero)
- `--section comments|history` — target section (default `comments` → `## Comments`)
- `--attention` — add the `!!!ВНИМАНИЕ!!! ` prefix to the text
- `--dry-run` — show the result without writing

**Roles:** `analyst`, `planner`, `developer`, `researcher`, `tester`, `reviewer`, `debugger`, `documenter`, `communicator`, `archivist`, `uat`, `user`

**Exit codes:** `0` — added/simulated; `1` — spec not found or invalid role/section.

---

## lint_board.py

Workspace linter — report only, writes nothing. Checks:
- §6 board format: frontmatter, tab-separated tag line, settings block, checkboxes
- §8 spec YAML: required fields, valid enum values
- §10 orphan / reverse-orphan / stale / dependency, `status`↔column mismatch, required sections, gates before `review`/`done`

```bash
python <SCRIPT_PREFIX>/kanban.py lint <WORKSPACE_ROOT>
python <SCRIPT_PREFIX>/kanban.py lint <WORKSPACE_ROOT> --strict           # WARN also causes exit 1
python <SCRIPT_PREFIX>/kanban.py lint <WORKSPACE_ROOT> --slug <slug>      # limit the report to a single spec
python <SCRIPT_PREFIX>/kanban.py lint <WORKSPACE_ROOT> --check-urls       # additionally check external URLs in specs
```

**Flags:**
- `--strict` — WARN also causes exit 1
- `--slug <slug>` — check only this spec + its card on the board; other specs and board-checks are skipped
- `--check-urls` — check URL reachability in RESEARCH-task artifacts (makes HTTP requests; disabled by default)

**Exit codes:** `0` — no errors; `1` — has ERROR (or WARN with `--strict`); `2` — `tasks/` folder not found.

---

## sync_properties.py

Normalization of spec YAML properties. Guarantees the presence of all required fields, a canonical order, valid enum values, syncs `status` with the board column (the column is the source of truth), normalizes date formats, updates `updatedAt`.

```bash
python <SCRIPT_PREFIX>/kanban.py sync <WORKSPACE_ROOT> --slug <slug>    # single spec
python <SCRIPT_PREFIX>/kanban.py sync <WORKSPACE_ROOT> --all             # whole workspace
python <SCRIPT_PREFIX>/kanban.py sync <WORKSPACE_ROOT> --slug <slug> --dry-run  # diff without writing
python <SCRIPT_PREFIX>/kanban.py sync <WORKSPACE_ROOT> --slug <slug> --no-status  # without syncing status with the board
```

Without `--slug` and without `--all` it exits with an error — a full scan updates `updatedAt` for all files.

**Flags:**
- `--no-status` — do not sync `status` with the board column (normalizes only the other fields)

**Exit codes:** `0` — success; `1` — argument error.

---

## check.py

Combined sync + lint in a single call: first `sync_properties.py`, then `lint_board.py`. Intended for the role cycle §9: before every transition and on YAML changes. After `add_comment.py` and prose edits, a separate `check.py` is not required. The `--slug` flag is mandatory — a full scan is not allowed (use `kanban.py lint` for that). Without `--slug`, an actionable hint (exit 2) with both paths is printed instead of a raw argparse error.

```bash
python <SCRIPT_PREFIX>/kanban.py check <WORKSPACE_ROOT> --slug <slug>
```

**Exit codes:** `0` — no errors; `1` — lint found an ERROR; `2` — called without `--slug` (prints a lint / --slug hint).

---

## set_card_tags.py

Deterministic editing of a card's emoji tags line on the board. Rebuilds the tags line in canonical order §7 (`➕ → 🛫 → 📅 → ⏳ → priority → 🔁 → ✅`), preserving unspecified tags and overwriting the ones given. Used by the analyst for `--start today`, by the planner for `⏳`, and for priority/deadlines without manually editing the tags line. An explicit `--start` additionally syncs the YAML `startedAt`: `today` writes the exact system time of the first start, an existing non-null value is not overwritten; for a card with `status: icebox`, `--start` with a date is rejected (for a frozen task, `🛫`/`startedAt` = actual start, not the return date — for that there is `--reminder`). `--reminder <DATE|none>` mutates only the spec's YAML `reminder` field (a one-off return date from ICEBOX / reminder, surfaced by `check_reminders.py`), does not touch the board's emoji tags line, and, unlike `startedAt`, is freely overwritten.

`--title` — canonical card rename: changes the alias in `[[slug|Title]]` on the first line of the board card IN PLACE (column, position within the column, and tags line are untouched), synchronously updates the spec H1 (`# 📋 <Title>`) and `updatedAt`, adds an entry to `## Changelog`. Does not change the slug (spec file name) — only the display title. Used by the analyst to assign a tag prefix (`RESEARCH:`/`FIX:`/…) to cards from the dashboard instead of `remove-card` + `add-card` + `tags --start`.

```bash
python <SCRIPT_PREFIX>/kanban.py tags <WORKSPACE_ROOT> <slug> [options]
```

**Flags** (`none` or `-` removes the tag; `today` for dates = today):
- `--created <DATE>` — creation date `➕`
- `--start <DATE|today>` — start date `🛫` (syncs `startedAt`; rejected for `status: icebox` card, except `none`)
- `--reminder <DATE|none>` — the spec's YAML `reminder` field (a one-off return date from ICEBOX / reminder; **not** a board emoji tag — does not touch the tags line; `none` → `null`)
- `--due <DATE|today>` — deadline `📅`
- `--estimate <Nh|Nd>` — duration estimate `⏳`
- `--done <DATE|today>` — completion date `✅`
- `--priority high|medium|low|none` — priority
- `--recurring / --no-recurring` — repeat `🔁`
- `--title "<Title>"` — canonical rename: board card alias + spec H1 + Changelog (does not change the slug/spec file)
- `--board <name.md>` — board file name, if there are several
- `--dry-run` — show the result without writing

**Exit codes:** `0` — applied/simulated; `1` — card/board not found.

---

## set_step.py

Set the YAML `step` field (developer progress marker, §8/§9 — resume point after a session interruption). `step` and `itemType` (see `set_item_type.py`) used to be edited manually; a manual `Edit` right after `move_card.py` used to break on a race («file modified since read»), since `move_card` rewrites the frontmatter. The script reads the file at execution time and writes under `board_lock`. Replaces only the `step:` line (`count=1`, multiline `^…$`) and bumps `updatedAt`.

```bash
python <SCRIPT_PREFIX>/kanban.py step <WORKSPACE_ROOT> <slug> step-2
python <SCRIPT_PREFIX>/kanban.py step <WORKSPACE_ROOT> <slug> "step-3 (refactor ready)"
python <SCRIPT_PREFIX>/kanban.py step <WORKSPACE_ROOT> <slug> null      # == --clear
```

**Flags:**
- `--clear` — set `step: null` (the value is then optional)
- `--dry-run` — show the result without writing

**Exit codes:** `0` — set/simulated; `1` — spec not found / no `step` field / no value given.

---

## set_item_type.py

Set the YAML `itemType` field (card type in the `epic`/`task`/`subtask` hierarchy, §4). The `set-type` command. The dashboard creates cards with `itemType: unassigned`; the analyst assigns the real type before moving to TODO (the linter forbids `unassigned` outside BACKLOG/ICEBOX). This used to be the last manually-edited frontmatter field — now it's scripted, like `step`. The value is validated against `lint_board.VALID_ITEMTYPE`; an invalid value → exit 1 with the list of valid ones. Replaces only the `itemType:` line (`count=1`, multiline `^…$`) under `board_lock` and bumps `updatedAt`.

```bash
python <SCRIPT_PREFIX>/kanban.py set-type <WORKSPACE_ROOT> <slug> task
python <SCRIPT_PREFIX>/kanban.py set-type <WORKSPACE_ROOT> <slug> epic
# as part of the update composite:
python <SCRIPT_PREFIX>/kanban.py update <WORKSPACE_ROOT> <slug> --item-type subtask --comment "..." --as analyst
```

**Flags:**
- `--dry-run` — show the result without writing

**Exit codes:** `0` — set/simulated; `1` — spec not found / no `itemType` field / invalid value.

---

## check_item.py

Check/uncheck checkboxes in spec sections — the last mutation that used to be edited manually with `Edit`. Manual editing violates the "mutate via script" principle and, after any script mutation of the file, fails with «file modified since read» (an extra re-Read). The script toggles `- [ ]`↔`- [x]` by 1-based index or `--all` under `board_lock`, counting **only** checkbox lines in the target section; bumps `updatedAt`.

```bash
python <SCRIPT_PREFIX>/kanban.py check-item <WORKSPACE_ROOT> <slug> <section> [indexes...] [options]
# section: dod | subtasks | test | review
python <SCRIPT_PREFIX>/kanban.py check-item "." my-task dod 1 3      # check DoD items 1 and 3
python <SCRIPT_PREFIX>/kanban.py check-item "." my-task test --all   # check all Test Checklist items
```

**Flags:**
- `--all` — all checkboxes in the section (indexes not needed)
- `--uncheck` — remove the check mark (`[x]`→`[ ]`)
- `--dry-run` — show the result without writing

**Exit codes:** `0` — applied/simulated; `1` — spec/section not found, no checkboxes, index out of range, neither indexes nor `--all` given.

---

## check_reminders.py

Finds tasks with a reminder due today and updates the dashboard. Run automatically by the agent during onboarding (§3 SKILL.md). Scans the `reminder` field in `specs/*.md`, prints the list of triggered reminders. Automatically overwrites `tasks/kanban-dashboard.html` from `assets/kanban-dashboard.html` — the dashboard is always up to date after onboarding.

```bash
python <SCRIPT_PREFIX>/kanban.py reminders <WORKSPACE_ROOT>
python <SCRIPT_PREFIX>/kanban.py reminders <WORKSPACE_ROOT> --date 2026-06-09   # for tests
```

**`reminder` formats:** `YYYY-MM-DD` (one-off) | `weekly:mon` | `monthly:15` | `daily` | `null`

**Exit codes:** `0` — no problems; `2` — at least one problem to show the user: a triggered reminder ∪ a task with no activity in UAT ≥ 2 days ∪ an active-column overflow (>10) ∪ a DONE overflow.

---

## archive_done.py

Archiving old DONE cards to a separate board. When the DONE column overflows, moves the oldest cards to `tasks/<board>-archive.md` (creates it if missing), leaving the `--keep` most recent ones on the main board.

```bash
python <SCRIPT_PREFIX>/kanban.py archive <WORKSPACE_ROOT> <board-slug> [--keep N] [--dry-run]
# Example:
python <SCRIPT_PREFIX>/kanban.py archive "." claude-obsidian-kanban --keep 10
```

**Flags:**
- `--keep N` — how many cards to keep on the main board (default `10`)
- `--dry-run` — show the result without writing

**Exit codes:** `0` — success; `1` — error.

---

## update.py

Batch spec mutator in a single call. Combines `set-type` (itemType), `step`, `check-item` (DoD / Subtasks / Test / Review) and `comment` into one transaction: one lock, one read/write, one `updatedAt` bump. Use instead of a chain of separate `set-type` + `step` + `check-item` + `comment` calls.

```bash
python <SCRIPT_PREFIX>/kanban.py update <WORKSPACE_ROOT> <slug> [options]
# Example — closing out the developer stage:
python <SCRIPT_PREFIX>/kanban.py update "." <slug> --dod all --subtasks all --comment "what was implemented" --as developer
# Stdin variant for --comment with spaces (no shell-quoting):
echo "Developer comment with spaces" | python <SCRIPT_PREFIX>/kanban.py update "." <slug> --dod all --comment - --as developer
```

**Flags:**
- `--item-type <value>` — set the YAML `itemType` field (epic|task|subtask|unassigned)
- `--step <value>` — set the YAML `step` field; `null` clears it
- `--clear-step` — reset `step` to `null`
- `--dod all|N,N` — check DoD items (all or by index)
- `--subtasks all|N,N` — check Subtasks
- `--test all|N,N` — check Test Checklist
- `--review all|N,N` — check Review Checklist
- `--uncheck` — uncheck instead of check
- `--comment "<text>"` — comment text for `## Comments`; `"-"` reads from stdin
- `--as <role>` — comment author role (required with `--comment`)
- `--attention` — `!!!ВНИМАНИЕ!!!` prefix on the comment
- `--dry-run` — show the result without writing

**Exit codes:** `0` — success; `1` — argument error or spec not found.

---

## kanban_utils.py

**Standard aggregating import facade** — not called directly as a CLI. Re-exports everything from the three domain modules: `board_io` (board parsing/serialization, lock, resolution), `workflow` (column↔role mapping, role_checklist), `spec_mutations` (spec scaffolding and mutations). Scripts import it as `import kanban_utils as ku` — this is the main import path across the codebase (20+ scripts).

The domain modules (`board_io.py`, `workflow.py`, `spec_mutations.py`) are **not called directly**, they are imported by other scripts.
---

## next_task.py

Shows the next task by priority, scanning columns **REWORK → TODO → BACKLOG** (in that order). Within each column, sorted by `priority` (high → medium → low → no tag). Always exit 0 — an empty queue is not considered an error.

```bash
python <SCRIPT_PREFIX>/kanban.py next <WORKSPACE_ROOT>
python <SCRIPT_PREFIX>/kanban.py next <WORKSPACE_ROOT> --json
```

**Flags:**
- `--json` — output as JSON `{"slug":..., "title":..., "column":..., "priority":..., "board":...}`; `{}` on an empty queue

**Exit codes:** `0` — always; `1` — error reading the workspace.
