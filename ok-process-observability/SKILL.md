---
name: process-observability
description: >
  Process-cost observability for AI agent work sessions: capture live workflow
  incidents (command failures, quoting retries, noisy output, wrong scope),
  run a mandatory post-run session self-audit, and print deterministic
  context-cost metrics over the kanban task workspace. Launch on demand,
  in parallel with the obsidian-kanban skill, when a session should be
  measured or when workflow friction is observed. Triggers (RU/EN):
  observability, process cost, инцидент процесса, аудит сессии, session audit,
  context cost, стоимость контекста, workflow friction.
metadata:
  openclaw:
    emoji: '📡'
---

# Process Observability — observability of process cost

Standalone skill. It runs ALONGSIDE the obsidian-kanban skill and never
modifies kanban skill files. It reads `tasks/` read-only; durable findings
are written through the kanban CLI (`kanban.py comment/update --stdin`) or
as artifacts in `tasks/artifacts/`.

## Activation

Run when needed, in parallel with the kanban session:

- the user asks to measure/reduce process or context cost;
- the agent notices recurring workflow friction (failed commands, quoting
  retries, noisy output) and wants to record it in a structured way;
- at the end of a significant work run (dogfooding, epic run) a self-audit
  is needed.

The skill is NOT a daemon and NOT hidden telemetry: all data is visible
session facts and `tasks/` files.

## Run contract

Mandatory order for an observability run:

1. **Live incident capture** — during the work, record incidents per the
   rule from [`references/incident-contract.md`](references/incident-contract.md):
   symptom / cause / workaround / proposed durable fix / metric category.
   Durable record — via `kanban.py comment <ws> <slug> <role> --stdin`
   or `kanban.py update ... --comment - --as <role>`.
2. **Post-run session audit** — before the final answer, go through the
   checklist in [`references/session-audit.md`](references/session-audit.md): categorize
   waste based on visible session facts, apply the stop-rule (recurring
   incident → follow-up task, not just a comment).
3. **Context-cost metrics** — deterministic metrics of context volume:
   `python .agents/skills/process-observability/scripts/observe.py metrics "." [--board <board.md>|--project <slug>]`
   Read-only over `tasks/`; complements `kanban.py metrics` (historical proxy
   baseline), does not replace or modify it.

## Boundaries

- Do not modify files under `.agents/skills/obsidian-kanban/` or any board files.
- Do not claim exact token counts: only deterministic proxies
  (bytes, lines, counts). Metric limitations are documented in the
  docstring of `scripts/context_metrics.py`.

## Files

- [`references/incident-contract.md`](references/incident-contract.md) — when and how to record an incident.
- [`references/session-audit.md`](references/session-audit.md) — mandatory post-run checklist.
- `scripts/observe.py` — dispatcher (`metrics` command).
- `scripts/context_metrics.py` — context-cost rows.
- `scripts/test_observability.py` — deterministic tests (temp workspace).
