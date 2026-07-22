# Personas for agent roles

Each Kanban status = one column = one role (see SKILL.md §5).
A role file is a short checklist that the agent reads upon entering the corresponding status.

The workflow layer (this directory) is independent of the PM tool. Specific commands (move_card, add_comment, etc.) are defined by the loaded adapter — see [`references/adapter-interface.md`](../references/adapter-interface.md) and [`ONBOARDING.md → ADAPTER_TYPE`](../ONBOARDING.md).

## Role/process contract

The regular role files `agents/<role>.md` remain stable entry points for `SKILL.md` §5/§9 and the output of `kanban.py resume --full-checklist`.

- `## Role Knowledge` indicates where the reusable role profile lives: method, methodologies, heuristics, tools, and constraints that don't depend on a specific column.
- `## Stage Process` indicates where the process for a specific column lives: checklist, gate checks, and allowed transitions.
- Do not split files into `*-knowledge.md`/`*-process.md` without a separate migration of links in `SKILL.md`, `agents/README.md`, and the scripts that print the role checklist.
- For roles with multiple statuses, e.g. `developer.md` for `IN PROGRESS` and `REWORK`, keep shared knowledge once in `## Role Knowledge`, and describe status differences in `## Stage Process` / `## Checklist`.

Special roles (`launcher.md`, `subagent-runner.md`) are not Kanban columns. Their launch protocols are considered top-level process documents and are not required to repeat the usual stage-role structure.

**A deliberate exception — `uat.md`.** UAT is the only column where the role is performed by a human (the user/product owner), not an agent. The `## Methodologies` section (a set of engineering approaches by task type — TDD, reproducer-first, etc., see `developer.md`) doesn't make sense for this role: the user doesn't follow agent development methodologies, they accept or reject the result. Instead, `uat.md` has `## Method`, with a text explanation that UAT is a wait state, not agent work; `## Role Knowledge` / `## Stage Process` refer to `## Method` / `## Checklist` / `## Transitions` just like in the other roles. Do not add `## Methodologies` to `uat.md` in future edits — this is not an oversight, but a structural feature of the role.

> **Self-heal on truncated output:** the output of `move_card.py` prints the role checklist FIRST and ends it with the marker `=== END OF CHECKLIST ===`. If this marker is missing from stdout — the output was truncated BEFORE the end of the checklist; rerun `python <SCRIPT_PREFIX>/kanban.py resume "." <slug> --full-checklist` to get the checklist again before continuing.

| Column | status | Role file |
|---------|--------|-----------|
| BACKLOG | `backlog` | [`analyst.md`](analyst.md) |
| ICEBOX | `icebox` | [`archivist.md`](archivist.md) |
| TODO | `ready` | [`planner.md`](planner.md) |
| IN PROGRESS | `in-progress` | [`developer.md`](developer.md) |
| IN PROGRESS | `in-progress` | [`researcher.md`](researcher.md) |
| BLOCKED | `blocked` | [`communicator.md`](communicator.md) |
| TESTING | `testing` | [`tester.md`](tester.md) |
| IN REVIEW | `review` | [`reviewer.md`](reviewer.md) |
| REJECTED | `rejected` | [`debugger.md`](debugger.md) |
| REWORK | `rework` | [`developer.md`](developer.md) |
| UAT | `uat` | [`uat.md`](uat.md) |
| DONE | `done` | [`documenter.md`](documenter.md) |

## Special roles

| Role | File | When to use |
|------|------|--------------------|
| Launcher | [`launcher.md`](launcher.md) | `/launch-agents` — one subagent per epic |
| Subagent runner | [`subagent-runner.md`](subagent-runner.md) | Executing a task via the Agent tool from TODO |
