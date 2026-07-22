# Kanban Board Format — obsidian-kanban

> Full template with an example: read **[`templates/board.md`](../templates/board.md)** before creating a new project.

## Critical Rules

Violating these breaks the Obsidian Kanban plugin:

| Rule           | Details                                                                 |
| -------------- | ---------------------------------------------------------------------- |
| Frontmatter    | Only `kanban-plugin: board`. No other fields.                          |
| Date tags      | On a **separate line indented with `\t`** right after the wikilink line |
| Empty columns  | Keep the heading + one blank line under it                             |
| Settings block | `%% kanban:settings %%` **always** at the end; `list-collapse` has exactly 11 values (one per column) |
| Checkboxes     | `- [ ]` incomplete, `- [x]` complete (only in DONE)                    |
| Separators     | A blank line between cards; two blank lines before `%%`                |

## Workflow Columns

Canonical column order (11 total):

| Column        | Status       | Role         | Purpose                                                 |
| ------------- | ------------ | ------------ | -------------------------------------------------------- |
| `BACKLOG`     | `backlog`    | analyst      | New ideas and tasks to be refined                       |
| `ICEBOX`      | `icebox`     | archivist    | Frozen: still relevant, but not now                     |
| `TODO`        | `ready`      | planner      | Ready to start, dependencies cleared                    |
| `IN PROGRESS` | `in-progress`| developer    | Actively being worked on                                |
| `BLOCKED`     | `blocked`    | communicator | Waiting on external input / decision                    |
| `TESTING`     | `testing`    | tester       | Functional check ("does it work")                       |
| `IN REVIEW`   | `review`     | reviewer     | Quality check (DoD, architecture, code style)            |
| `UAT`         | `uat`        | uat          | Waiting on user acceptance (only a human can close it)   |
| `REJECTED`    | `rejected`   | debugger     | Rejected by reviewer or user — needs a fix plan          |
| `REWORK`      | `rework`     | developer    | Reworked after rejection                                |
| `DONE`        | `done`       | documenter   | Completed and documented                                |

## Task Categories

Prefix in the wikilink display name:

| Category    | Meaning                    |
| ----------- | -------------------------- |
| `DEV:`      | Development / code         |
| `RESEARCH:` | Research / analysis        |
| `OPS:`      | Infrastructure / operations |
| `DOC:`      | Documentation               |
| `FIX:`      | Bug fix                     |
| `TEST:`     | Testing                     |
