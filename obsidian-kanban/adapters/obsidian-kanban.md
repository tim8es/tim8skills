# Adapter: Obsidian Kanban

Maps the [abstract interface](../references/adapter-interface.md) onto concrete commands of the current implementation.

**ADAPTER_TYPE:** `obsidian`  
**Requirements:** Python 3.x, filesystem (offline), Obsidian Kanban plugin (for viewing in Obsidian — optional).  
**SCRIPT_PREFIX:** determined during onboarding (`ONBOARDING.md → ## SCRIPT_PREFIX`).

---

## Operation Mapping

### `move_card`

```
python <SCRIPT_PREFIX>/kanban.py move "." <slug> "<TARGET_COLUMN>"
```

- Parses all `tasks/*.md` with `kanban-plugin: board`
- Accepts shell-safe aliases for columns with spaces: `IN_PROGRESS` → `IN PROGRESS`, `IN_REVIEW` → `IN REVIEW`
- Moves the card, updates `status` in `tasks/specs/<slug>.md`
- Stamps ✅ when moved to DONE (format `HH:MM`, for `sort_done()` sorting)
- Prints the role checklist from `agents/<role>.md` (§9 hard stop)
- Script: `scripts/move_card.py`

---

### `inject_role_prompt` (additional operation)

For cases where the card move was performed externally (MCP, manually) and `move_card.py` was not called — inject the role checklist without mutating the board:

```
python <SCRIPT_PREFIX>/kanban.py resume "." <slug> --full-checklist
```

- Prints the same checklist as `move_card.py` — single business logic via `kanban_utils.role_checklist()`; `resume` determines the card's current column from the slug itself (no need to pass `<TARGET_COLUMN>` manually)
- Does not modify files — stdout only
- The card title (for IN PROGRESS routing: `RESEARCH:` prefix → `researcher.md` instead of `developer.md`) is taken automatically by `resume` from the board card
- Script: `scripts/resume.py`

Typical pattern for external adapters (Linear, Trello, GitHub Projects):
```
# 1. Move the card via an MCP tool (adapter-specific)
# 2. Immediately after — inject the checklist:
python <SCRIPT_PREFIX>/kanban.py resume "$WORKSPACE_ROOT" <slug> --full-checklist
```

---

### `add_comment`

```
python <SCRIPT_PREFIX>/kanban.py comment "." <slug> <role> "<text>" [--section history] [--attention]
```

- Appends to `## Comments` (default) or `## Changelog`
- Timestamp: `YYYY-MM-DD HH:MM:SS` (via `kanban_utils.hist_stamp()`)
- Bumps `updatedAt` in the YAML frontmatter
- Script: `scripts/add_comment.py`

---

### `set_card_tags`

```
python <SCRIPT_PREFIX>/kanban.py tags "." <slug> [--priority high|medium|low] [--estimate 2h] [--start YYYY-MM-DD] [--due YYYY-MM-DD] [--done YYYY-MM-DD]
```

- Edits the emoji tag line on the card's line on the board (format §7)
- Script: `scripts/set_card_tags.py`

---

### `find_next_task`

Implemented as the function `kanban_utils.find_next_task(tasks_path)`.

Called automatically from `move_card.py` when moving to DONE (prints a recommendation).

Order: REWORK → TODO → BACKLOG, within a column — by priority (high > medium > low).

---

### `get_card`

Implemented as directly reading the board + spec (no separate script):

```python
# Column and tags — from tasks/<project>.md (parsed via kanban_utils.parse_board)
# Spec content — from tasks/specs/<slug>.md
```

The agent reads the board via `Read` + `Grep` (no shell command).

---

### `list_cards`

Implemented via `Grep` over the board text:

```
Grep pattern="^\s*- \[[ x]\] \[\[" path="tasks/<project>.md"
```

To filter by column — read the `## <COLUMN>` section from the board file.

---

### `create_spec`

```
python <SCRIPT_PREFIX>/kanban.py new-task "." <slug> "<Task title>" --card [--priority high] [--epic <parent-slug>]
```

Creates `tasks/specs/<slug>.md` with canonical frontmatter and empty sections.  
The `--card` flag immediately adds the card `- [ ] [[slug|Title]]` to the BACKLOG column of the board (by default `new-task` does not create a card — add it as a separate step via `kanban.py add-card`).  
Script: `scripts/new_task.py`

---

### `read_spec`

Direct file read (no separate script):

```
Read file_path="tasks/specs/<slug>.md"
```

Frontmatter — the YAML block between `---`. Sections — `## <Title>` headings.

---

### `lint_spec`

```
python <SCRIPT_PREFIX>/kanban.py check "." --slug <slug>
```

Checks: YAML fields (format, enum values), presence of `[x]` in DoD, Output with a wikilink/outside the workspace, board syntax.  
Exit 0 = clean (WARNs are allowed, don't block the transition). Exit 1 = ERROR (blocks the transition). Exit 2 = called without `--slug` (prints an actionable hint / --slug; a full scan is forbidden).  
Script: `scripts/check.py`

---

## Adapter Detection

Indicator that the Obsidian adapter is active:

```python
# tasks/*.md contains the line:
"kanban-plugin: board"
```

Check: `Grep pattern="kanban-plugin: board" path="tasks/"`.

---

## Adapter Limitations

| Limitation | Description |
|-------------|----------|
| Offline only | No MCP; works without internet |
| Markdown spec | The spec lives in `tasks/specs/<slug>.md` — outside the ticket body |
| Wikilinks | `[[slug]]` links are Obsidian-specific; unreadable in other tools |
| Encoding | Files are UTF-8 LF; Windows may create CRLF (scripts normalize) |
