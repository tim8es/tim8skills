# Template: Epic Specification

Copy into `tasks/specs/<epic-slug>.md`.
Fill in all fields; remove comment lines `<!-- ... -->` before saving.

---

```markdown
---
flowId: <project>/epic/<epic-slug>
itemType: epic
status: backlog
parentId: null
step: null
owner: analyst
priority: medium
createdAt: YYYY-MM-DD HH:MM:SS
updatedAt: YYYY-MM-DD HH:MM:SS
reminder: null
startedAt: null
testingAt: null
reviewAt: null
doneAt: null
dependsOn: []
blocks: []
---

# 🗃️ TAG: Epic Title

## Goal
<!-- One sentence: what this epic delivers to the user/system -->

## Context
<!-- Why it's needed. What problem it solves. Links to research if any. -->

## Definition of Done (DoD)
<!-- Concrete, verifiable criteria. At least 2. -->
- [ ] 
- [ ] 

## Tasks
<!-- REQUIRED ≥1 child task (decomposition recommendation — 3–7). An epic = decomposable work: it ALWAYS has
     decomposed child tasks. If decomposition isn't needed — it's NOT an epic, but a
     regular task (itemType: task), create via new-task without --epic. An epic with an empty
     `## Tasks` (or only prose instead of a wikilink) is a linter error (except in BACKLOG/ICEBOX,
     where decomposition may not be done yet — there it's WARN).
     Filled in during decomposition. Each line is a link to specs/<task-slug>.md.
     The task's checkbox is marked [x] when that task transitions to status: done. -->
- [ ] [[task-slug|TAG: Task Title]] — brief description
- [ ] [[task-slug-2|TAG: Task Title 2]] — brief description

## Dependencies
- Blocks: <!-- [[other-epic]] or — -->
- Depends on: <!-- [[other-epic]] or — -->

## Risks
<!-- What could go wrong. Optional, but recommended for large epics. -->

## Review Checklist
<!-- Cross-check of epic completion before moving to done — making sure
     the epic is closed as intended. Gate: must be filled when status: review. -->
- [ ] All tasks in the "Tasks" section are in status done
- [ ] All epic DoD items are completed
- [ ] Results are documented (artifact / summary note)
- [ ] Dependent epics and tasks are unblocked

## Changelog
<!-- Do not edit manually. Transitions between columns are written by move_card.py automatically
     (YYYY-MM-DD HH:MM:SS | move | SRC → DST). Other events — add_comment.py --section history. -->

## Comments
<!-- Do not edit manually. Add only via script:
     python <SCRIPT_PREFIX>/kanban.py comment "." <slug> <role> "<self-analysis>" [--attention]
     --attention marks the entry as critical (!!!ATTENTION!!!) — read BEFORE your stage. -->
```

---

## YAML Fields — Reference

Full list of fields, allowed values, enums (including `owner` with role `uat`), and date formats (`YYYY-MM-DD HH:MM:SS`) — single source: [`references/metadata.md`](../references/metadata.md). Key points: an epic has `itemType: epic`, `parentId: null`; `owner` = the author, doesn't change on transitions; datetime fields use the format `YYYY-MM-DD HH:MM:SS`.

---

## Example of a Filled Epic

```markdown
---
flowId: my-app/epic/auth-epic
itemType: epic
status: backlog
parentId: null
step: null
owner: analyst
priority: high
createdAt: 2026-05-18 10:00
updatedAt: 2026-05-18 10:00
---

# 🗃️ DEV: Authentication System

## Goal
Provide secure user login via email/password and OAuth (GitHub, Google).

## Context
The current prototype works without authentication. Before public launch a
full session-management and access-control system is needed.

## Definition of Done (DoD)
- [ ] JWT authentication via email/password works
- [ ] OAuth via GitHub and Google is set up
- [ ] Refresh tokens are implemented
- [ ] All endpoints are protected by middleware
- [ ] E2E tests for the auth flow pass

## Tasks
- [ ] [[db-schema|DEV: users and sessions table schema]] — models and migrations
- [ ] [[jwt-service|DEV: JWT service]] — token issuance and validation
- [ ] [[oauth-integration|DEV: OAuth integration]] — GitHub + Google
- [ ] [[auth-middleware|DEV: Auth middleware]] — route protection

## Dependencies
- Blocks: [[user-profile-epic]]
- Depends on: —

## Risks
- OAuth credentials need to be requested from Timur (may be delayed)

## Review Checklist
- [ ] All tasks in the "Tasks" section are in status done
- [ ] All epic DoD items are completed
- [ ] Results are documented (artifact / summary note)
- [ ] Dependent epics and tasks are unblocked

## Changelog
2026-05-18 10:00 | analyst | Epic created, decomposition approved with the user
```
