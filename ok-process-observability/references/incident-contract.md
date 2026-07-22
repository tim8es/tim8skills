# Incident Contract — rule for recording live process incidents

## When to record

An incident is recorded IMMEDIATELY as soon as the agent observes workflow
friction that cost extra tokens/retries/time — before continuing with the
main work. Triggers:

- a command ended in an error and required a retry;
- shell quoting broke arguments (quotes, spaces, Cyrillic, `%VAR%`);
- command output turned out noisy/excessive and had to be re-read;
- work was done in the wrong scope (wrong file/board/directory);
- a file was read in full when only a fragment was needed (context-heavy read);
- a browser/UAT check blocked autonomous progress.

## Record form (all fields mandatory)

| Field | Content |
|---|---|
| symptom | What was observed (exact command/action and result) |
| cause | Root cause, as far as visible from the session |
| workaround | How it was worked around to continue the work |
| proposed durable fix | What to change so the incident does not recur |
| metric category | One of the categories below |

## Categories (metric category)

- `command-failure` — the command returned a non-zero exit code / error.
- `shell-quoting` — arguments lost/corrupted due to quoting and escaping.
- `noisy-output` — excessive output that bloated the context.
- `wrong-scope` — work done on the wrong file/board/directory.
- `context-heavy-read` — a read far larger than necessary.
- `browser-uat-blocker` — a check requires a browser/human, the autonomous run stalls.

## One-off vs recurring pattern

- **One-off**: local friction, occurred once in the session → a comment
  record in the current task is enough.
- **Recurring pattern**: the same symptom/category ≥2 times in the session,
  or it has already occurred in previous runs (visible in the Comments/Changelog
  of other tasks) → besides the record, a durable fix MUST be proposed and a
  follow-up task created (see the stop-rule in session-audit.md). A comment
  alone is not enough.

## Durable assignment of the record

The incident is recorded via the kanban CLI (skill files are not touched):

```
echo "incident: symptom=...; cause=...; workaround=...; fix=...; category=shell-quoting" | \
  python <SCRIPT_PREFIX>/kanban.py comment "." <task-slug> <role> --stdin
```

or in one transaction when closing out a role:
`kanban.py update "." <slug> --comment - --as <role>` (text via stdin).
For findings outside the context of a specific task — an artifact in
`tasks/artifacts/`.

## Example of a real incident

```
symptom: echo "text" | kanban.py comment ... --stdin in Windows cmd produced
         garbled output (Cyrillic was corrupted); before that, 2 retries with
         different quoting for comment "long text" — arguments were split on spaces.
cause: cmd.exe parses quotes/spaces differently than a POSIX shell; sys.stdin
       has no utf-8 reconfigure on Windows.
workaround: a short shell-safe comment with no spaces, then the full text via
            a file: kanban.py comment ... --stdin < comment.txt.
proposed durable fix: document --stdin as the default for long comments;
            reconfigure(encoding="utf-8") for stdin in add_comment.py.
metric category: shell-quoting
```
