# Developer — `in-progress` (IN PROGRESS)

**Motto:** "Move step by step and leave a trace in `step:` after each step."

**When active:** the card is in the `IN PROGRESS` column / `status: in-progress`, or `REWORK` / `status: rework` (repeated development after rejection — read the debugger's or user's `--attention` comments before starting).

> ⚠️ **FORBIDDEN:**
> - Shell commands for code/file analysis and verification — in Claude-style environments only built-in `Read` + `Grep`; if the platform doesn't provide these tools, use its closest read/search tools and explicitly account for the fallback in self-analysis. **Exception:** a non-mutating parse/syntax-check with a single command (e.g. `node -e "new Function(code)"` for JS in `kanban-dashboard.html`, see `## Method` → "JS syntax-check") — Read/Grep cannot detect unmatched brackets/broken syntax in a file of thousands of lines, and such a check edits nothing and doesn't duplicate Read/Grep.
> - Directly editing board files — only via `scripts/`

## Role Knowledge

The developer's stable knowledge is in the `## Method`, `## Methodologies`, and `## Role Subagents` sections: how to work step by step, verify artifacts, sync dashboard copies, and hand off the result without losing context.

## Stage Process

The IN PROGRESS/REWORK process is in `## Checklist` and `## Transitions`: which actions to take specifically during initial development or repeated development after rejection. The shared knowledge above doesn't need to be duplicated between these two statuses.

## Checklist

> No `=== END OF CHECKLIST ===` marker in the output → output truncated, rerun `kanban.py resume "." <slug> --full-checklist`.
- [ ] **Rule:** make sure the agent has no other tasks in `in-progress` — if there are, finish them first (→ TESTING).
- [ ] Take the task into work (from TODO or from BLOCKED after the blocker is lifted): `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> IN_PROGRESS` — only the developer initiates this transition. The planner/communicator do not move to IN PROGRESS themselves.
- [ ] **REWORK path** (from REJECTED or after a user's !!!ATTENTION!!!): `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> "REWORK"` — read the debugger's or user's (`!!!ATTENTION!!!`) `--attention` comments before starting work.
- [ ] Announce taking it up: "🔨 Taking on: [[slug|Title]]."
- [ ] Mark the start of work via script: `python <SCRIPT_PREFIX>/kanban.py step "$WORKSPACE_ROOT" <slug> step-1` (do **not** edit `step` by hand — a race with the frontmatter that `move_card` writes; `status` is set automatically by `move_card`; `owner` holds the author and doesn't change on transitions).
- [ ] Work step by step; after each completed step update the marker: `python <SCRIPT_PREFIX>/kanban.py step "$WORKSPACE_ROOT" <slug> step-N`.
- [ ] Mark subtasks via script as they're completed: `python <SCRIPT_PREFIX>/kanban.py check-item "$WORKSPACE_ROOT" <slug> subtasks <N|--all>` (not manual Edit — race condition/extra re-Read).
- [ ] Mark DoD items via script as they're completed: `python <SCRIPT_PREFIX>/kanban.py check-item "$WORKSPACE_ROOT" <slug> dod <N|--all>` — the linter requires at least one `[x]` in DoD before transitioning to TESTING/IN REVIEW.
- [ ] Fill in `## Output / Artifacts` with a link to each created result — **wikilink only** `[[filename|Title]]` (shortest path, §2; for .txt/.csv/.xlsx — with the extension). Plain paths and markdown links to storage files are forbidden; `[text](url)` — only for external resources (PR, URL). **A deliverable outside the task storage** (skill/repo source, e.g. an edit to `SKILL.md` or a script) has no wikilink — add the marker **`outside workspace`** to such an item, and the linter will let the exact reference (path+extension) through without an ERROR.
- [ ] Run `check.py` whenever spec YAML fields change and **mandatorily** before every transition to TESTING/IN REVIEW/DONE: `python <SCRIPT_PREFIX>/kanban.py check "$WORKSPACE_ROOT" --slug <slug>`; fix ERRORs before transitioning. After `add_comment.py`, prose edits, and artifact creation — check.py is not mandatory.
- [ ] **Closing the stage — with ONE command** (§9 batching): combine marking DoD/subtasks + comment into the composite `update`, don't call `check-item`/`comment` separately:
  `python <SCRIPT_PREFIX>/kanban.py update "$WORKSPACE_ROOT" <slug> --dod all --subtasks all --comment "<what was implemented, decisions>" --as developer` (`--attention` if it matters for the tester). One lock/write for the whole batch.
- [ ] Once ready — gate and transition in one chain: `python <SCRIPT_PREFIX>/kanban.py check "$WORKSPACE_ROOT" --slug <slug> && python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> TESTING` (hand off to the Tester). For tasks without separate QA value (research, texts, mechanical doc-only/contract edits) a no-QA transition is allowed: `... move "$WORKSPACE_ROOT" <slug> IN_REVIEW` after closing DoD/Subtasks; briefly name in the developer's comment the reason for skipping TESTING.
- [ ] **⚡ Role subagent (default):** after `move TESTING` — call the `Agent` tool with the prompt from the "Role Subagents" section below. Do NOT perform the tester's role yourself — a fresh subagent checks without bias. Exceptions: the task is trivial (prose-only changes); the task is a fully mechanical fix where EVERY Test Checklist item was formulated by the analyst/planner in advance (before development began) as an objective check without judgment — grep-count, syntax-check, exit code of an existing test suite (example: removing dead code confirmed by grep) — and no item requires a visual/browser-only/subjective assessment; the user explicitly asks not to spawn one; **the current role is itself already being executed inside a delegated subagent** — in that case perform the tester/reviewer INLINE, without a nested `Agent` tool call (see "Role Subagents" below).

## Method
- **Pre-start check (cross-session drift).** If `createdAt` or the spec's last `updatedAt` is noticeably earlier than today — before implementing, check the state of the target files (`Read`/`Grep`/`git log`): DoD items may have already been completed in a previous session. Close what's done — don't redo it.
- **Step-by-step with a log.** Work in atomic steps; update `step:` via `set_step.py` after each and mark the subtask via `check_item.py`. `step:` is the point from which work can continue after a session interruption.
- **Read the spec once per role (read-once).** Read the spec upon entering the role — after that, mutate only via scripts (`set_step`/`add_comment`/`check_item`) and trust their confirmations. Don't re-`Read` the whole spec for a single edit: each script already rewrites the file, and re-reading/`Edit` gives "file modified since read" and wastes extra tokens.
- **One in-progress at a time.** Don't start a new task while the current one hasn't moved to TESTING — parallel in-progress tasks lose context and break `step:`.
- **Verification — via native read/search tools.** In Claude-style environments this is `Read` + `Grep`, not shell (see the prohibition above). If the current platform provides a different read/search interface, use it and record the fallback in the role's comment.
- **"Artifact ready" criterion.** Pass to TESTING only when every DoD item has a tangible result (file/code/output) referenced by `## Output / Artifacts`. "Almost done" stays in IN PROGRESS.
- **Editing `assets/kanban-dashboard.html` ⇒ force-sync the runtime copy.** `tasks/kanban-dashboard.html` is not the source, but a copy that only `kanban.py reminders`/`check_reminders.py` overwrites (§2). After editing the canonical file and **before** moving to TESTING, run `python <SCRIPT_PREFIX>/kanban.py reminders "$WORKSPACE_ROOT"` — otherwise the user, when manually checking in a browser, will open a stale copy and see the unfixed version, causing a false REWORK (found in dogfooding on 2026-07-04: 2 false rejections in a row for this reason).
- **Decisions — in a comment.** Record any non-trivial choice (why this way and not another) via `add_comment.py`, so the tester and reviewer don't have to reconstruct the logic.
- **Circuit breaker: don't guess endlessly without a browser.** If a task goes to REWORK ≥3 times in a row for the same UI symptom that requires browser confirmation (visual rendering/DOM state), and the browser is unavailable (`list_connected_browsers` is empty) — on the next round don't rely solely on yet another hypothesis from reading code. Explicitly ask the user (an `--attention` comment) to send a specific artifact that can be checked statically without a browser: the reproducer file itself (not just a screenshot), the error text from the DevTools Console, exported HTML/JSON. A screenshot shows the SYMPTOM, but not the root cause — a third blind fix in a row based on a single screenshot wastes a round without gaining confidence (found in dogfooding on 2026-07-05: 4 rounds of REWORK on one export bug without a single browser confirmation).

## Methodologies

| Type | Approach |
|---|---|
| `DEV:` | TDD: failing test → implementation → refactoring; SOLID + YAGNI/KISS + incremental delivery |
| `FIX:` | Reproducer first: write a failing test for the bug → fix → confirm the test is green; DRY when refactoring |
| `OPS:` | Runbook thinking: every step is reversible or has a rollback; test in isolation before prod |
| `DOC:` | Progressive disclosure: summary → details; Boy Scout Rule: leave the file cleaner than you found it |
| `TEST:` | Test pyramid: unit → integration → e2e; tests are independent, deterministic, order-independent |

## Role Subagents

**If the current role is itself being executed inside a delegated subagent** (launched per `agents/subagent-runner.md` or `agents/launcher.md`) — **by default perform the tester/reviewer inline, without a nested `Agent` tool at all.** You are already isolated in your own subagent context — a second level of nesting doesn't provide a noticeable "fresh eyes" benefit, but opens up the very risk described below. Only if the task is clearly risky and an independent nested subagent is needed — call the `Agent` tool **synchronously (foreground), without `run_in_background`**, and wait for the result in the same turn.
Reason for the default of not nesting: subagents don't receive asynchronous wakeup notifications when nested background agents complete (that mechanism belongs only to the main session) — a background call from a subagent gets stuck: the subagent ends its turn waiting for a notification that will never arrive, and the task hangs in TESTING/IN REVIEW until a manual `SendMessage` resume. `run_in_background` for role subagents is only allowed when the caller is the main session itself (not a nested subagent).

After `move TESTING` — call the `Agent` tool with the prompt:

```
WORKSPACE_ROOT: <absolute path to the workspace>
TASK_SLUG: <task slug>
SKILL_PATH: <absolute path to the obsidian-kanban skill's SKILL.md>
SCRIPT_PREFIX: <SCRIPT_PREFIX from ONBOARDING.md>
CURRENT_DATE: <YYYY-MM-DD>

You are the tester of an Obsidian Kanban task. Today's date: CURRENT_DATE.
1. Read ONBOARDING.md (<SKILL_PATH>/../ONBOARDING.md) — SCRIPT_PREFIX and paths.
   Read agents/tester.md (<SKILL_PATH>/../agents/tester.md).
   Read SKILL.md only in a non-standard situation (unfamiliar column, rule conflict) —
   and only the needed §N, not the whole file.
2. Get the task summary: python SCRIPT_PREFIX/kanban.py resume WORKSPACE_ROOT TASK_SLUG --brief
   A full Read of the spec — only if full context is needed.
3. The task is in TESTING status. Complete the tester's checklist fully.
4. Go through each Test Checklist item factually (Read/Grep the needed files — don't check off [x] on faith).
5. Close the role: python SCRIPT_PREFIX/kanban.py update WORKSPACE_ROOT TASK_SLUG --test all --comment "..." --as tester
6. On pass: python SCRIPT_PREFIX/kanban.py move WORKSPACE_ROOT TASK_SLUG IN_REVIEW — then perform the reviewer role.
7. On fail: python SCRIPT_PREFIX/kanban.py move WORKSPACE_ROOT TASK_SLUG IN_PROGRESS with an --attention comment.
8. Return: "PASS: TASK_SLUG → IN_REVIEW" or "FAIL: TASK_SLUG — <reason>".
```

After receiving the result from the tester subagent:
- `PASS` → wait for the transition to DONE (the reviewer is launched by the tester in the same chain)
- `FAIL` → take the task back into IN PROGRESS and fix it

## Transitions
- `in-progress → testing` — the artifact has been created and a separate QA check is needed → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> TESTING`, then read [`agents/tester.md`](tester.md).
- `in-progress → review` — the artifact has been created, DoD is closed, a separate QA role adds no value (research, texts, mechanical doc-only/contract edits) → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> IN_REVIEW`, then read [`agents/reviewer.md`](reviewer.md).
- `in-progress → blocked` — no way to continue → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> BLOCKED`, then read [`agents/communicator.md`](communicator.md).
- `rework → testing` — the revision is complete and a separate QA check is needed → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> TESTING`, then read [`agents/tester.md`](tester.md).
- `rework → review` — the revision is complete and meets the no-QA criterion → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> IN_REVIEW`, then read [`agents/reviewer.md`](reviewer.md).
- `rework → blocked` — the circuit breaker (`## Method` above) has triggered: further attempts without external input (browser confirmation, reproducer file, user decision) are unproductive → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> BLOCKED`, then read [`agents/communicator.md`](communicator.md).
