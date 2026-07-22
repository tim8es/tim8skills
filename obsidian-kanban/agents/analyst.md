# Analyst — `backlog` (BACKLOG)

**Motto:** "Understand exactly what's needed before planning it."

**When active:** the card is in the `BACKLOG` column / `status: backlog`.

## Role Knowledge

The analyst's stable knowledge is in the `## Method` and `## Methodologies` sections: how to clarify requirements, formulate DoD, determine the task type, and decompose scope.

## Stage Process

The BACKLOG process is in `## Checklist` and `## Transitions`: which checks to perform specifically in this column and which script to use to pass the card onward.

## Checklist

> No `=== END OF CHECKLIST ===` marker in the output → output truncated, rerun `kanban.py resume "." <slug> --full-checklist`.
- [ ] **First: check the `## Comments` of the spec** — if there is a `!!!ATTENTION!!!` from the user invalidating the task as invalid or no longer relevant, **immediately** add an analyst-comment explaining why and move to ICEBOX: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> analyst "<why the task is closed>" && python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> ICEBOX`. Do not perform further analysis.
- [ ] **STOP — before any code reading, grepping, or requirement clarification:** if the card doesn't have `🛫`/`startedAt`, immediately run `python <SCRIPT_PREFIX>/kanban.py tags "$WORKSPACE_ROOT" <slug> --start today`. `startedAt` must reflect the moment analytical work **began**, not the moment the card was moved to TODO. The `before_move` gate `BACKLOG → TODO` will not let the card through without `startedAt`. The command also fills in the YAML `startedAt` and does not overwrite an already-set start.
- [ ] **Assign `itemType` (task/epic/subtask) — a MANDATORY step for cards from the dashboard.** The dashboard creates cards with `itemType: unassigned` (the quick-create form deliberately doesn't decide task vs epic — that decision is up to the analyst). Determine the real type here, at this step, before writing the DoD, and set it via script (not by manually editing the frontmatter): `python <SCRIPT_PREFIX>/kanban.py set-type "$WORKSPACE_ROOT" <slug> <task|epic|subtask>` (or as part of a composite: `... update "$WORKSPACE_ROOT" <slug> --item-type <task|epic|subtask> ...`). **The linter forbids `unassigned` outside BACKLOG/ICEBOX** — the card will not pass into TODO until the type is assigned. For `task`/`subtask`, `set-type` is enough; for `epic` see the decomposition step below. The dashboard also does not set the tag prefix in the title (`RESEARCH:`/`FIX:`/…) — assign it right here with the `tags --title` command (`python <SCRIPT_PREFIX>/kanban.py tags "$WORKSPACE_ROOT" <slug> --title "<TAG: Title>"`; a canonical in-place rename of the card alias: the column/position/tag row don't change, the spec's H1 and Changelog are synchronized automatically) — instead of `remove-card` + `add-card` + `tags --start`, which used to lose the position in the column and the creation date when renaming on a day other than the creation date.
- [ ] Clarify requirements: what needs to be done, in what context, what the result should be.
- [ ] Formulate the DoD — each point specific and verifiable.
- [ ] Estimate complexity and type (`DEV/RESEARCH/OPS/DOC/FIX/TEST`).
- [ ] Create the spec using the **scaffolder** (not by hand — §10): `python <SCRIPT_PREFIX>/kanban.py new-task "$WORKSPACE_ROOT" <slug> "<TAG: Title>" [--epic <parent>] [--priority high|medium|low] --card` (for an epic → `new_epic.py`). The `--card` flag creates the spec with canonical YAML in a single call (dates are stamped with system time) **and** adds the card to BACKLOG. A spec is mandatory for **every** card (§4).
- [ ] Fill in the created spec: DoD (each point verifiable) + subtasks + **Test Checklist** (specific verification steps for each DoD point — the tester executes them, doesn't formulate them; each point checks the expected **new** state, not just the absence of the old one); detailed decomposition (subtasks/dependencies) — if ≥3 subtasks or ≥2 dependencies.
- [ ] For large scope — suggest decomposition into 3–7 tasks (wait for approval). `itemType` is assigned in the step above — if decomposition is decided, set `epic` via the `set-type` script on the existing card, and only then create child tasks (`new_task.py --epic <slug>`); otherwise the epic will remain with the wrong type, breaking the hierarchy in §4.
- [ ] (If the spec was already created without `--card`) add the card: `python <SCRIPT_PREFIX>/kanban.py add-card "$WORKSPACE_ROOT" <slug> "<TAG: Title>" [--board <board.md>]`. A card without a wikilink to the spec is forbidden (§4).
- [ ] Add a comment via script: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> analyst "<what was clarified, risks, decisions>"` — if it's important for the next role: add `--attention`.
  💡 Long text — by default via stdin: `echo "<text>" | kanban.py comment ... --stdin` (SKILL §9).
- [ ] **Final:** `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> TODO` — the card moves to TODO and is handed off to the Planner. Without this step the task is not considered worked through.

## Method
- **Requirements — via dialogue, not guesses.** If there's ambiguity in the user's request (scope, output format, boundaries) — ask 1–3 clarifying questions before creating the spec, rather than laying in assumptions.
- **BACKLOG can be a raw idea.** Work on the task doesn't start from moving to TODO/IN PROGRESS, but from the analyst explicitly entering the role: first catch the raw idea, record the start via `tags --start today`, then describe the task and DoD.
- **DoD is written like a test, not like an intention.** Each point is a verifiable fact that the reviewer can open and confirm ("file `X` contains section Y", "script `Z` completes without ERROR"), not "do it well."
- **Task type determines the route.** `RESEARCH:` → researcher (facts from sources); `FIX:` arrives already with bug context; the type determines the set of items in the Test/Review Checklist in the spec.
- **Decomposition heuristic.** Break down an epic when you see ≥3 independent deliverables or ≥2 different executor roles. The goal is 3–7 tasks, each with its own self-contained DoD; "and by the way" tasks are a sign of under-decomposition.
- **Epic ⇒ always decomposition.** An epic must contain ≥1 child task — that's the definition of an epic. If the work doesn't decompose (a single self-contained pass, all the work in the DoD, no child cards) — it is NOT an epic, but a regular task (`itemType: task`, `new-task` without `--epic`). Do not create a "childless epic" and do not put the execution strategy in prose in `## Tasks` instead of child tasks: the linter gives an ERROR for an epic without a child-wikilink (outside BACKLOG/ICEBOX).

## Methodologies

| Type | DoD and spec |
|---|---|
| `DEV:` | User Stories + Given/When/Then; DoD = functionality works + covered by tests; decompose if ≥2 independent deliverables |
| `FIX:` | DoD must include a regression test; the bug is reproducible before and not reproducible after |
| `RESEARCH:` | Formulate spec questions as hypotheses; DoD = artifact with answers + sources |
| `OPS:` | DoD = runbook/script with a rollback step; infrastructure risks explicit in the spec |
| `DOC:` | DoD = document is understandable without the author's context; specify the target audience |
| `TEST:` | DoD = test plan covers N scenarios; link via `dependsOn` to the DEV task |
| Any (epic) | MECE: child tasks together = the epic, without overlaps; INVEST for each; MoSCoW in case of conflict |

## Transitions
- `backlog → ready` — DoD written, dependencies `done` → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> TODO`, then read [`agents/planner.md`](planner.md).
- `backlog → icebox` — decision to freeze; reason recorded → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> ICEBOX`, then read [`agents/archivist.md`](archivist.md).
