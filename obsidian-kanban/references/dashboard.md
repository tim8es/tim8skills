# Web Dashboard for Non-Obsidian Use

The file `assets/kanban-dashboard.html` is a self-contained Kanban dashboard for working without Obsidian.
A single HTML file, vanilla JS, no dependencies and no network — works offline by double-click.

## Capabilities

- List of all project boards and switching between them (sidebar).
- Full task management: creation, editing, drag-and-drop between columns, checkboxes, deletion, filtering.
- In the topbar next to `View`, before the search input, there is `▷ Artifacts N` — a board-level page of unique artifacts for the currently active board. Clicking it switches the dashboard's main area from cards to the artifact gallery; clicking again returns to cards.
- The gallery is deduplicated by artifact slug and assembled only from cards on the selected board: a wikilink in `## Output / Artifacts`, an artifact file with `linkedTask: <task-slug>`, or a spec link to an artifact note. Empty placeholder lines are not counted as artifacts. Targets are normalized before opening (`foo.md`, `artifacts/foo`, `tasks/artifacts/foo.md` → `foo`), so a resolvable artifact note opens on click.
- In artifact mode, the shared search input filters artifact cards, and its dropdown switches to the single category `Artifacts`: `All / Readable / Other`. Other artifacts remain visible; if the artifact note itself cannot be opened, the source note of the task where it was mentioned can be opened instead. Artifact cards show the date and time from the artifact note's metadata, or, if there's no note, from the source note of the task.
- On the card — `👤 Owner` from the `owner` field, a description preview, and DoD progress from the spec; in the editor — the full note content (description, DoD, subtasks) read-only.
- Lifecycle timestamps come from the spec's YAML: `createdAt`, `startedAt`, `doneAt` are displayed as Created / Start / Finish with date and time. Empty `startedAt`/`doneAt` are shown as an empty state, without substituting the current date.
- Configurable settings (toggles in the header, persisted): showing dependencies △ and description preview 📝. The card preview shows only `dependsOn` / `blocks`. In the right panel of an open task there are always three categories: `Depends on`, `Blocks`, `Mentions`; the last one combines non-blocking `## Related` entries, regular wikilinks, and backlinks without duplicates.
- Task types: the list is assembled from cards + seeds (`DEV/RESEARCH/OPS/DOC/FIX/TEST`) + new types added in the editor.
- Support for Obsidian links `[[slug]]`: clickable, navigate to the corresponding card.
- Reads and writes the **same format** as the Obsidian Kanban plugin (11 columns, emoji tags, settings block).

## Opening Data

| Mode | Condition | Behavior |
|-------|---------|-----------|
| **"Open tasks/ folder"** | Chrome/Edge (File System Access API) | Reads all boards and `specs/`, writes changes directly to files; syncs `status` in the spec when a card is moved |
| **"Open files"** | Any browser | In-memory edits; saved by downloading `.md` |

When a card is moved via the dashboard, `status`, `updatedAt`, and the first fill-in of the lifecycle timestamp field for the target column are synced: `startedAt` for IN PROGRESS, `testingAt` for TESTING, `reviewAt` for IN REVIEW, `doneAt` for DONE. Timestamp fields that are already filled in are not overwritten.

## Persisting Access Across Reloads

After the folder is chosen the first time, it is remembered (a handle in IndexedDB). On the next open, the dashboard silently restores it without re-prompting the picker. If the browser requires confirmation, it shows a "↻ Open saved tasks/ folder" button.

That's why, during onboarding, the dashboard is placed in `$WORKSPACE_ROOT/tasks/` next to the boards — the user picks the folder once.

## Installation (Onboarding)

When creating a new workspace, the agent copies `assets/kanban-dashboard.html` → `tasks/kanban-dashboard.html`.

## Limitations

- The dashboard does not replace the agent workflow contract — it is only for a human to view/edit boards.
- Auto-running scripts (`lint_board.py`, `sync_properties.py`) is not supported — only through the agent.
