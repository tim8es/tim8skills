# Template: Task / Subtask Specification

Copy into `tasks/specs/<task-slug>.md`.
For a subtask: `itemType: subtask`, `parentId: <task-slug>`, `flowId: <project>/subtask/<slug>`.
Remove comment lines `<!-- ... -->` before saving.

---

```markdown
---
flowId: <project>/task/<task-slug>
itemType: task
status: backlog
parentId: <epic-slug or null>
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

# 📋 TAG: Task Title

## Description
<!-- What needs to be done. In what context. The expected result. -->

## Definition of Done (DoD)
<!-- Each item is concrete and verifiable. Not "done", but "file X created", "test Y passes". -->
- [ ] 
- [ ] 

## Subtasks
<!-- Atomic steps. If a subtask > 10 lines of description — extract to specs/<subtask-slug>.md -->
- [ ] 
- [ ] 

## Technical Details
<!-- Architectural decisions, chosen tools, documentation links, snippets. -->

## Output / Artifacts
<!-- REQUIRED: every link to a result must be an Obsidian wikilink `[[file-name|Title]]`,
     shortest path without folders (§2). Do NOT use a plain path (`projects/.../file.md`) or a markdown link.
     For non-.md files (.txt, .csv, .xlsx) include the name with extension: `[[demo_transcript_ru.txt|Translation]]`.
     External resources without a file in storage (PR, URL) are the only exception: a plain link `[text](url)`.
     The spec references the artifact, does not contain it. Filled in as work progresses. -->
- 

## Test Checklist
<!-- The tester (status: testing) goes through this list — functional check "does it work".
     Each item is a concrete behavior check, not a code-quality check. -->
- [ ] Artifact exists at the expected path and runs
- [ ] The main scenario completes without errors
- [ ] Edge cases are handled (empty input, maximum size, missing data)

## Review Checklist
<!-- The reviewer (status: review) goes through this list — quality check "was it done correctly". -->
- [ ] Artifact or code exists at the expected path
- [ ] All DoD items are completed
- [ ] No regressions in adjacent functionality
- [ ] Documentation or task notes are updated when applicable

## Dependencies
- Depends on: <!-- [[task-slug]] or — -->
- Blocks: <!-- [[task-slug]] or — -->

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

Full list of fields, allowed values, enums (including `owner` with role `uat`), and date formats (`YYYY-MM-DD HH:MM:SS`) — single source: [`references/metadata.md`](../references/metadata.md). Key points: `flowId` has 3 parts; `owner` = the task's author, doesn't change on transitions; `step` should be updated as work progresses; datetime fields use the format `YYYY-MM-DD HH:MM:SS`.

---

## Example of a Filled Task (in-progress)

```markdown
---
flowId: my-app/task/jwt-service
itemType: task
status: in-progress
parentId: auth-epic
step: step-2 / building the validation middleware
owner: developer
priority: high
createdAt: 2026-05-20 09:00
updatedAt: 2026-05-21 14:30
---

# 📋 DEV: JWT Service

## Description
Implement a service for issuing and validating JWT access/refresh tokens.
The service must integrate with the `sessions` table from [[db-schema]].

## Definition of Done (DoD)
- [x] Function `issueTokens(userId)` → `{ accessToken, refreshToken }`
- [x] Function `verifyAccessToken(token)` → `userId | null`
- [ ] Function `refreshTokens(refreshToken)` → a new token pair
- [ ] Unit tests for all three functions pass (coverage ≥ 90%)

## Subtasks
- [x] Install `jsonwebtoken`, add env variables `JWT_SECRET`, `JWT_REFRESH_SECRET`
- [x] Implement `issueTokens` and `verifyAccessToken`
- [ ] Implement `refreshTokens` with invalidation of the old refresh token
- [ ] Write unit tests

## Technical Details
- Library: `jsonwebtoken ^9.0`
- Access token TTL: 15 minutes; Refresh token TTL: 30 days
- Refresh tokens are stored in the `sessions` table (see [[db-schema]])
- Invalidation: delete the record from `sessions` on refresh or logout

## Output / Artifacts
- [[jwt-service-impl|src/services/jwt.service.ts]] <!-- wikilink to an artifact/note in storage -->
- PR: <!-- external link to the pull request — a plain markdown link, not a wikilink -->

## Test Checklist
- [ ] `issueTokens` returns a valid token pair for a correct userId
- [ ] `verifyAccessToken` rejects an expired and a tampered token
- [ ] `refreshTokens` invalidates the old refresh token (reuse is rejected)

## Review Checklist
- [ ] Artifact or code exists at the expected path
- [ ] All DoD items are completed
- [ ] No regressions in adjacent functionality
- [ ] Documentation or task notes are updated when applicable

## Dependencies
- Depends on: [[db-schema]]
- Blocks: [[auth-middleware]]

## Changelog
2026-05-20 09:00 | analyst | Task created as part of [[auth-epic]] decomposition
2026-05-20 11:00 | move | TODO → IN PROGRESS
2026-05-21 10:00 | developer | step-1 completed: issueTokens and verifyAccessToken implemented
2026-05-21 14:30 | developer | Started step-2: validation middleware
```
