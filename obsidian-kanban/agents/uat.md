# UAT — `uat` (UAT)

**Motto:** "The work is done — it's the user's word now."

**When active:** the card is in the `UAT` column / `status: uat`.

## Role Knowledge

UAT's stable knowledge is in the `## Method` section: UAT is a wait for user acceptance, not active agent work.

## Stage Process

The UAT process is in `## Checklist` and `## Transitions`: the agent only reports what exactly needs to be accepted and doesn't move the card itself.

## Checklist

> No `=== END OF CHECKLIST ===` marker in the output → output truncated, rerun `kanban.py resume "." <slug> --full-checklist`.
- [ ] Read the `## Comments` section of the spec — especially lines with `!!!ATTENTION!!!`.
- [ ] Make sure the spec's `## Output / Artifacts` is filled in: the user needs to know exactly what to accept.
- [ ] Tell the user: "🔎 Task [[slug|Title]] is awaiting your acceptance. Check the result (see Output) and take one of the following actions:"
  - `python <SCRIPT_PREFIX>/kanban.py move "." <slug> DONE` — if the result is accepted.
  - `python <SCRIPT_PREFIX>/kanban.py move "." <slug> REJECTED` — if changes are needed (goes to the debugger next).
- [ ] Add a handoff comment: `python <SCRIPT_PREFIX>/kanban.py comment "$WORKSPACE_ROOT" <slug> uat "Handed off to the user for acceptance. Output: <brief description>"`.
  💡 Long text — by default via stdin: `echo "<text>" | kanban.py comment ... --stdin` (SKILL §9).
- [ ] **Make no changes at all** — the card is waiting for a human, the agent is passive here.

## Method

UAT (User Acceptance Testing) is a **wait**, not agent work. A card lands
in UAT from `IN REVIEW`, when the reviewer considers the result technically correct, but
explicit acceptance from the user is required (product owner, customer, end user).

- **The agent doesn't move the card out of UAT itself** — only the user makes the decision.
- **Waiting period** — if the card sits in UAT without activity for ≥2 days (counted from `updatedAt`), remind the user.
- **Rejection from UAT → REJECTED** — the debugger analyzes exactly what the user didn't accept;
  the developer does REWORK.

## Transitions (user only)
- `uat → done` — the user accepted it: `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> DONE`
- `uat → rejected` — the user rejected it: `python <SCRIPT_PREFIX>/kanban.py move "$WORKSPACE_ROOT" <slug> REJECTED`, then the debugger reads [`agents/debugger.md`](debugger.md)

ℹ Full column contract: [`references/workflow-contract.md`](../references/workflow-contract.md)
