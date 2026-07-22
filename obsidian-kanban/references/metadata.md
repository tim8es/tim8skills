# TaskFlow Metadata — obsidian-kanban

> Full YAML templates with examples: [`templates/epic.md`](../templates/epic.md), [`templates/task.md`](../templates/task.md).

## Required YAML Block

In every spec:

```yaml
---
flowId: <project>/<itemType>/<slug> # 3 parts required: my-app/task/auth-login
itemType: epic | task | subtask | unassigned # unassigned — transient: a card from the dashboard before a type is assigned (see below)
status: backlog | icebox | ready | in-progress | blocked | testing | review | uat | rejected | rework | done
parentId: <slug> | null
step: <current step> | null
owner: analyst | planner | developer | researcher | tester | reviewer | debugger | documenter | communicator | archivist | uat | user
priority: high | medium | low | null # 'none' from the dashboard's sync_properties is rewritten to null
createdAt: YYYY-MM-DD HH:MM:SS
updatedAt: YYYY-MM-DD HH:MM:SS
reminder: YYYY-MM-DD | weekly:mon | monthly:15 | daily | null
startedAt: YYYY-MM-DD HH:MM:SS | null
testingAt: YYYY-MM-DD HH:MM:SS | null
reviewAt: YYYY-MM-DD HH:MM:SS | null
doneAt: YYYY-MM-DD HH:MM:SS | null
dependsOn: []   # list of slugs that must be done before this one can start
blocks: []      # list of slugs that cannot start until this one is closed
---
```

## Transition Timestamp Fields (`startedAt` / `testingAt` / `reviewAt` / `doneAt`)

Record the FACT of reaching the corresponding stage; set idempotently by `move_card.py` on first entry into the status and **not cleared** on exit. `startedAt` is the exception: it's set by the analyst via `tags --start today`, not by a move.

- **lost-DONE safeguard:** `DONE` is terminal (`ALLOWED_EXITS`), and `doneAt` is never rolled back, so `doneAt≠null` while the card is outside the `DONE` column is a reliable sign of a false/racy move that dropped a completed card. `lint` issues a WARN (a status↔column sync would silently reconcile such a mismatch — e.g. `rework/REWORK` looks consistent — so detection relies on the non-clearable `doneAt` rather than on the status/column pair). `sync`, when downgrading `done`→earlier with a non-empty `doneAt`, prints a loud warning but still treats the column as the source of truth. Recovery: check `## Changelog` for a `move DONE → ...` entry without justification and move the card back to DONE if the work is actually complete.

## `dependsOn` and `blocks` Fields

Structural dependencies between tasks. Format: `[slug1, slug2]` or `[]`.

| Field       | Meaning                                                                    | Gate                                           |
| ----------- | ------------------------------------------------------------------------ | ---------------------------------------------- |
| `dependsOn` | Tasks that must be `done` before this one transitions to `ready`         | lint WARN if the dependency is not `done`; lint ERROR if the target lacks a mirrored `blocks` |
| `blocks`    | Tasks that cannot start (ready) until this one is `done`                 | lint ERROR if the target lacks a mirrored `dependsOn` |

- The source of truth is the YAML. The `## Dependencies` section remains as a human-readable representation.
- The blocking relationship must be bidirectional in YAML: if `A.dependsOn` contains
  `B`, then `B.blocks` must contain `A`; if `B.blocks` contains `A`, then
  `A.dependsOn` must contain `B`. Otherwise agents/dashboard see different sides
  of the same relationship.
- Migrating existing specs: `python <SCRIPT_PREFIX>/kanban.py sync "." --all`
- lint ERROR: `dependsOn` contains a slug for a spec that doesn't exist.

## `## Related` Section

Non-blocking relationships between tasks are recorded not in `## Dependencies`, but in a separate section:

```md
## Related
- [[other-task|Short title]]
```

This is used for follow-ups, an alternative spec, a clarification, or a related process artifact, when there's no requirement that "A must close first before B can start."

- The relationship must be bidirectional: if `A` contains `[[B]]` in `## Related`, then `B` must contain `[[A]]` in `## Related`.
- `kanban.py check` / `lint_board.py` verify that the linked spec exists and contains the back-link.
- Regular wikilinks in the description, comments, and changelog are mentions, not a relationship contract.

## `reminder` Field

| Format       | Trigger                                                                                |
| ------------ | --------------------------------------------------------------------------------------- |
| `YYYY-MM-DD` | One-time — exactly on this date; after triggering the agent asks: delete or reschedule |
| `weekly:mon` | Every Monday (`mon` `tue` `wed` `thu` `fri` `sat` `sun`)                                |
| `monthly:15` | The 15th of every month                                                                  |
| `daily`      | Every day                                                                                |
| `null`       | No reminder set                                                                         |

A one-time date (`YYYY-MM-DD`) is set/shifted/removed via the script, not by manual Edit: `kanban.py tags "." <slug> --reminder <DATE|none>` (`none` → `null`). This is, in particular, the expected-return date from ICEBOX (archivist): `reminder` separates the "return date" from `startedAt` (the actual start of work). Recurring formats (`weekly:`/`monthly:`/`daily`) are not accepted by `--reminder` — they are edited manually. `reminder` is a spec-only field, not a board emoji tag.

## Date Format Standard

| Context                                                       | Format             | Example                          |
| ------------------------------------------------------------ | ------------------ | -------------------------------- |
| YAML datetime fields (`createdAt`, `updatedAt`, `startedAt` …) | `YYYY-MM-DD HH:MM:SS` | `2026-06-07 18:00:42`        |
| YAML date-only field (`reminder`)                             | `YYYY-MM-DD`       | `2026-06-15`                    |
| Board emoji tags (`➕`, `🛫`, `📅`)                           | `YYYY-MM-DD`       | `➕ 2026-06-07`                 |
| Completion emoji tag (`✅`)                                   | `YYYY-MM-DD HH:MM` | `✅ 2026-06-07 18:00`           |
| Changelog / Comments                                          | `YYYY-MM-DD HH:MM:SS` | `2026-06-07 18:48:03 \| move \| …` |

> ISO 8601 (`YYYY-MM-DD`) is the **only** valid format. `dd.mm.yyyy` and other variants are incompatible with the scripts (5 parsers: `fromisoformat`, `strptime`, regex `\d{4}-\d{2}-\d{2}`).

## `owner` and `step` Rules

- `owner` = the author of the task/card, not the current assignee. When an agent creates it, the scaffolder sets `analyst` by default; if the agent creates a spec for an existing user-created card, pass `--owner user`. `move_card.py` does not change `owner` on transitions.
- `updatedAt` is updated automatically by mutator scripts (`move_card`, `add_comment`, `set_step`, `set_item_type`, `check_item`, `sync_properties`) — do not edit manually.
- `step` is set only by `set_step.py` (developer/researcher, after each completed step) — do not edit the frontmatter by hand (races with `move_card`).
- `itemType` is set by `set_item_type.py` (the `set-type` command or `update --item-type`; analyst, when assigning a type to a dashboard `unassigned` card → `task`/`epic`/`subtask`) — do not edit the frontmatter by hand.
