# Reviewer — `review` (IN REVIEW)

**Motto:** "Was it done right" — DoD, architecture, code style, absence of regressions.

**When active:** the card is in the `IN REVIEW` column / `status: review`.

> ⚠️ **FORBIDDEN:**
> - Shell commands for verifying code/changes — in Claude-style environments only `check.py --slug` + `Read` + `Grep`; if the platform doesn't provide these tools, use the closest native read/search tools and record the fallback in a comment

## Role Knowledge

The reviewer's stable knowledge is in the `## Method` and `## Methodologies` sections: how to check DoD, architecture, regressions, scope expansion, and the quality of comments.

## Stage Process

The IN REVIEW process is in `## Checklist` and `## Transitions`: which checks to perform specifically before DONE, UAT, or REJECTED.

## Checklist

> No `=== END OF CHECKLIST ===` marker in the output → output truncated, rerun `kanban.py resume "." <slug> --full-checklist`.
- [ ] Get the task summary: `python <SCRIPT_PREFIX>/kanban.py resume "$WORKSPACE_ROOT" <slug> --brief` — unclosed DoD + Output/Artifacts + !!!ATTENTION!!!. A full `Read` of the spec — in case of conflicting decisions or when the history needs to be read.
- [ ] Read the artifact (Output / Artifacts from the spec-brief) — make sure the deliverable actually exists and matches the task description.
- [ ] Check that the links in `## Output / Artifacts` are formatted as wikilinks `[[name|Title]]` (§2), not a plain path/markdown link (exceptions: external PR/URL; a deliverable outside storage with the `outside workspace` marker — a wikilink doesn't apply there, an exact path is allowed). On violation — return to the Developer.
- [ ] Check each DoD item **factually**: open the relevant file / script output / artifact and confirm the criterion is met — don't check `[x]` "on faith."
- [ ] Make sure all subtasks are marked `[x]` (if not — return to the Developer).
- [ ] Mark passed Review Checklist items via script only after actual verification: `python <SCRIPT_PREFIX>/kanban.py check-item "$WORKSPACE_ROOT" <slug> review <N|--all>` (not manual Edit). **Do this BEFORE the gating lint below:** when `status==review`, the linter requires a filled-in Review Checklist, otherwise the first run will give an ERROR and you'll have to run it again. Read the spec once per role.
- [ ] Run `python <SCRIPT_PREFIX>/kanban.py check "$WORKSPACE_ROOT" --slug <slug>` — the final gate before transitioning; fix ERRORs before moving to done.
- [ ] Regressions: `python <SCRIPT_PREFIX>/kanban.py lint "$WORKSPACE_ROOT"` — make sure your edit didn't introduce **new** ERRORs. In a multi-project workspace, a full `lint` scans ALL boards and may show pre-existing ERRORs from OTHER projects — these are not regressions from your task; the gate = 0 new ERRORs attributable to the change (primarily on the task's board). ⚠️ **Do not** chain this full `lint` with `&&` before `move`: `lint` returns exit 1 on ANY ERROR on any board (including others' pre-existing ones), which will break the chain and **silently skip the transition** (the card will get stuck in IN REVIEW). Run `lint` as a separate observation; the transition gate is the task-scoped `check "$WORKSPACE_ROOT" --slug <slug>` (item above, narrowed to the task's board).
- [ ] **Scope expansion:** if scope expansion is identified during review (the user or the DoD indicates additional scope beyond the current task) — **before closing the review** create a follow-up task: `python <SCRIPT_PREFIX>/kanban.py new-task "$WORKSPACE_ROOT" <new-slug> "<tag: title>" --card --board <board.md>` and record the slug of the created task in the reviewer's comment. Don't postpone it — "I'll create it later" == losing the task.
- [ ] Add a comment via script: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> reviewer "<what was checked, rationale for the decision, remarks>"` — on rejection: add `--attention`.
  💡 Long text — by default via stdin: `echo "<text>" | kanban.py comment ... --stdin` (SKILL §9).

## Method
- **Focus — "was it done right."** The reviewer checks compliance with the DoD, architecture, code style, and absence of regressions — things beyond the tester's functional check.
- **DoD, item by item, based on fact.** Open and confirm each criterion against a real artifact/script output; `[x]` without verification is forbidden.
- **Regressions — at the level of the task's board.** The goal is to make sure the change didn't break neighboring specs/board. In a multi-project workspace, a full `lint_board.py` may contain pre-existing ERRORs from other projects — don't count these as regressions; the gate = 0 **new** ERRORs attributable to the change (primarily on the task's board). Task-scoped `check --slug` (narrowed to the task's board) is the reliable transition gate; full `lint` is an observation (especially valuable for script edits that touch multiple boards).
- **Rejection constructively.** When rejecting, phrase the comment so the debugger can immediately build a fix plan: exactly what doesn't comply and with which DoD item.

## Methodologies

| Type | Review criteria |
|---|---|
| `DEV:` | SOLID + DRY + YAGNI; security-first (OWASP Top 10: injections, XSS, exposed data); architectural compliance |
| `FIX:` | The bug is fixed at the root, not worked around; a regression test exists; no unrelated changes |
| `OPS:` | Rollback is described; secrets not in code; idempotency where applicable |
| `DOC:` | Progressive disclosure; the audience can read it without the author present; no unexplained jargon |
| `TEST:` | Tests are independent; mocks are justified; coverage is meaningful, not formal |
| Any | Conventional Comments: `suggestion:` / `issue:` / `nitpick:` — the debugger must distinguish critical from optional |

## Transitions
- `review → done` — DoD fulfilled → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> DONE`, then read [`agents/documenter.md`](documenter.md).
- `review → rejected` — review failed; the remark is recorded → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> REJECTED`, then read [`agents/debugger.md`](debugger.md).
- `review → uat` — code review passed, but an unverified browser-only Test Checklist item remains, requiring user confirmation → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> UAT`, then read [`agents/uat.md`](uat.md).
