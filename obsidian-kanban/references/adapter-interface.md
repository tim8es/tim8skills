# Abstract Adapter Interface

Defines 9 required operations that every PM adapter must implement, plus one optional one (`inject_role_prompt`).
The workflow layer (roles, checklists, transitions) works through these operations — the concrete tool is hidden behind the interface.

Implementations: [`adapters/obsidian-kanban.md`](../adapters/obsidian-kanban.md).

---

## Operations

### WRITE — state mutations

#### `move_card(workspace, slug, target_column)`

Moves the card to the target column. Updates status in the spec. Writes to the change history.

**Returns:** stdout with the role checklist for the target column.

**Parameters:**
- `workspace` — project root (`"."`)
- `slug` — task identifier
- `target_column` — one of: `BACKLOG | ICEBOX | TODO | IN PROGRESS | BLOCKED | TESTING | IN REVIEW | UAT | REJECTED | REWORK | DONE`

Adapters may accept transport aliases for CLI convenience, but internally must normalize them to the canonical columns above. For example, the Obsidian CLI accepts `IN_PROGRESS` and `IN_REVIEW`.

---

#### `inject_role_prompt(workspace, slug)` — optional

Prints the same role checklist for the card's current column as `move_card` does, but **without mutating the board** — for cases where the move was performed externally (external MCP tool, manual edit). Obsidian implementation: `kanban.py resume "." <slug> --full-checklist`. External adapters (Linear/Trello/GitHub Projects) call it right after the MCP move. See [`adapters/obsidian-kanban.md`](../adapters/obsidian-kanban.md#inject_role_prompt-optional-operation).

---

#### `add_comment(workspace, slug, role, text, section?, attention?)`

Adds a timestamped entry to a spec/ticket section.

**Parameters:**
- `section` — `comments` (default, → `## Comments`) or `history` (→ `## Changelog`)
- `attention` — adds the prefix `!!!ATTENTION!!! ` to the text

---

#### `set_card_tags(workspace, slug, **fields)`

Updates card metadata.

**Parameters (`fields`):**
- `priority` — `high | medium | low | none`
- `estimate` — string like `2h`, `1d`
- `start` — `YYYY-MM-DD`
- `due` — `YYYY-MM-DD`
- `done` — `YYYY-MM-DD` (only when moving to DONE)

---

### READ — reading state

#### `find_next_task(workspace)`

Scans the board and returns the next task by priority.

**Scan order:** REWORK → TODO → BACKLOG (descending priority).

**Returns:** `{slug, title, column, priority, board}` or `None`.

---

#### `get_card(workspace, slug)`

Returns full information about a card.

**Returns:** `{slug, title, column, status, priority, tags, spec_content}`.

---

#### `list_cards(workspace, column)`

Returns the list of cards in the given column.

**Returns:** `[{slug, title, priority, tags}]`.

---

### SPEC MANAGEMENT — spec management

#### `create_spec(workspace, slug, name, item_type, **meta)`

Creates a new spec with canonical YAML frontmatter and sections (DoD, Subtasks, Output, etc.).

**Parameters (`meta`):** `priority`, `parent_slug`, `description`, `owner`.

---

#### `read_spec(workspace, slug)`

Reads the spec and parses it into structured parts.

**Returns:** `{frontmatter: dict, sections: {name: content}}`.

---

#### `lint_spec(workspace, slug)`

Checks the spec for compliance with transition requirements.

**Returns:** `{errors: [str], warnings: [str]}`.

**Checks:** presence of DoD with at least one `[x]`, Output with a wikilink/outside the workspace, validity of YAML fields.

---

## Adapter Implementation Rules

1. Each adapter implements all 9 operations or explicitly documents which ones are unsupported and why.
2. `move_card` **must** print the role checklist to stdout — this is the mechanism for §9 (hard stop).
3. `lint_spec` **must** check DoD before transitioning to TESTING/IN REVIEW/DONE.
4. Timestamp format across all operations: `YYYY-MM-DD HH:MM:SS` (§8, canonical source — `kanban_utils.now_stamp()`).
5. All mutations are idempotent: calling again with the same parameters does not create duplicates.
