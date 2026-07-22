# Session Audit — mandatory post-run process-cost self-audit

Before the final answer of an observability run, the agent MUST go through
this checklist based on **visible session facts**: its own tool calls,
their output, retries, errors. Hidden host telemetry (exact token counts,
internal logs) is not available and is not used — the audit relies only on
what the agent actually saw in the transcript of its own work.

## Self-audit checklist

Go through each category and record findings (or an explicit "none"):

- [ ] **failed-commands** — commands with a non-zero exit code / error; how many, which ones, why.
- [ ] **quoting-retries** — repeated runs of the same command with different quoting/escaping.
- [ ] **noisy-output** — commands whose output was much larger than needed (full dumps, broad greps).
- [ ] **excessive-reads** — full-file reads when a fragment/grep would have sufficed; repeated reads of the same file.
- [ ] **wrong-scope** — work/search done in the wrong file, directory, or board, followed by a redirect.
- [ ] **browser-uat-leftovers** — items left unchecked due to the lack of a browser/human.
- [ ] **avoidable-ceremony** — process steps that added no value in this run (unnecessary intermediate commands, duplicate checks, splitting into separate calls instead of batching).

## Finding format

Each finding is one line:
`<category>: <fact> -> <proposed improvement>`

Example from a real session history:

```
quoting-retries: kanban.py comment "long Russian text" failed in cmd.exe,
  2 retries with different quoting -> use --stdin by default for long comments
excessive-reads: dashboard.html (5k lines) read in full for the sake of one function
  -> Grep by function name + Read with offset/limit
avoidable-ceremony: step/check-item/comment called via three separate commands
  -> a single composite kanban.py update
```

## Durable assignment

The audit result is not left in an ephemeral answer:

1. **Task comment** — audit summary in the `## Comments` of the current/epic task:
   `... | kanban.py comment "." <slug> <role> --stdin`.
2. **Artifact** — for large volume: `tasks/artifacts/<run>-audit.md`.
3. **Follow-up task** — see the stop-rule below.

## Stop-rule (mandatory escalation rule)

If an incident of the same category has recurred **≥2 times in a run**, or
has already been recorded in past runs (visible in the Comments/Changelog of
tasks) — a comment is NOT enough. The agent must create a follow-up task
with a specific durable fix:

```
python <SCRIPT_PREFIX>/kanban.py new-task "." <fix-slug> "FIX: <summary>" --card --board <board.md>
```

Recurring waste that lives only in comments is uncollected process debt;
the task turns it into an actionable backlog item.
