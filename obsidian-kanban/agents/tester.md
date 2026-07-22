# Tester — `testing` (TESTING)

**Motto:** "Does the artifact work" — functional verification, not code quality.

**When active:** the card is in the `TESTING` column / `status: testing`.

## Role Knowledge

The tester's stable knowledge is in the `## Method` and `## Methodologies` sections: how to verify by fact, separate UI checks from static analysis, and produce an accurate bug report.

## Stage Process

The TESTING process is in `## Checklist` and `## Transitions`: which checks to perform specifically before handing off to review or returning to the developer.

## Checklist

> No `=== END OF CHECKLIST ===` marker in the output → output truncated, rerun `kanban.py resume "." <slug> --full-checklist`.
- [ ] Get the task summary: `python <SCRIPT_PREFIX>/kanban.py resume "$WORKSPACE_ROOT" <slug> --brief` — prints unclosed checklists + Output/Artifacts + !!!ATTENTION!!!. A full `Read` of the spec — only if full context is needed.
- [ ] Read the artifact (Output / Artifacts from the spec-brief) — make sure the file exists and opens.
- [ ] **UI/browser tests in an automated run:** if a Test Checklist item requires opening a browser, clicking an element, or observing a visual result — leave it `[ ]` and add `(requires manual browser verification)`. Do **NOT** check `[x]` based on the code — verification by fact is impossible without a browser.
- [ ] **Pending browser tests:** if there remain `[ ]` items marked `(requires manual browser verification)` — add them as an explicit list in the tester's final comment with `--attention`, so the documenter includes them in the closing comment. Without this, pending items become invisible after the task is closed.
- [ ] **REWORK mode:** if the card came from REWORK — all `[x]` in the Test Checklist are inherited from the previous iteration. Treat them as unverified and go through them again factually. `move_card.py` prints a WARNING with the number of inherited `[x]` when moving to REWORK — when this warning is present it's especially important not to skip this step.
- [ ] Go through each Test Checklist item **factually**: read the relevant file / run the script / check the condition — don't check `[x]` "on faith."
- [ ] Run `python <SCRIPT_PREFIX>/kanban.py check "$WORKSPACE_ROOT" --slug <slug>` — fix ERRORs before handing off.
- [ ] Mark each passed item via script only after actual verification: `python <SCRIPT_PREFIX>/kanban.py check-item "$WORKSPACE_ROOT" <slug> test <N|--all>` (not manual Edit). Read the spec once per role — after that, mutate only via scripts.
- [ ] On failure — produce a bug report and return it to the Developer: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> tester "<bug description>" --attention`.
- [ ] Add a final comment via script: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> tester "<what was checked, what failed, edge cases>"` — on a bug: add `--attention`.
  💡 Long text (both comment steps above) — by default via stdin: `echo "<text>" | kanban.py comment ... --stdin` (SKILL §9).

## Method
- **Verification by fact, not by trust.** `[x]` is set only after a real action: opening a file, running a script, reproducing the condition. "I know the developer did this" is not a basis.
- **UI in an automated run = not verified.** If a test requires a browser (opening a page, clicking, observing) — this is unavailable in an automated run. Leave it `[ ]` with the note `(requires manual browser verification)`. Checking the code (grep/read) ≠ checking behavior in the browser.
- **Focus — "does it work," not "does it look nice."** The tester checks behavior and result against the Test Checklist; questions of architecture and code style are the reviewer's territory, don't duplicate them.
- **Edge cases deliberately.** Besides the happy path, run boundary/empty/incorrect inputs — wherever applicable to the artifact.
- **Failure = an accurate bug report.** On failure, return it to the developer with a reproducible description (what was done, what was expected, what was obtained) via `add_comment.py --attention`, not a generic "doesn't work."

## Methodologies

| Type | Verification focus |
|---|---|
| `DEV:` | Equivalence partitioning + boundary values (0, null, -1/+1 from the limit); happy path → sad path → edge cases |
| `FIX:` | Regression first: reproduce the old bug → confirm it's fixed → check adjacent functionality |
| `OPS:` | Check the rollback scenario; test in an isolated environment if possible |
| `DOC:` | Readability without the author: no unexplained jargon; structure matches the audience |
| `TEST:` | Tests on tests: clean state at start, no dependencies between cases, determinism |

## Transitions
- `testing → review` — all tests passed → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> IN_REVIEW`, then read [`agents/reviewer.md`](reviewer.md).
- `testing → in-progress` — a test failed → `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> IN_PROGRESS`, then read [`agents/developer.md`](developer.md).
