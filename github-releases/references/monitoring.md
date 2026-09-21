# Monitoring with a host scheduler

The CLI fetches public data; the host owns a durable JSON state file, scheduling and delivery. Keep state in the task workspace, outside the installed skill and version control. Use one state file per repository and filter selection. A concurrent run must finish before another starts.

## State

Persist `initialized`, `repository`, `include_prereleases`, `include_nonversion`, `last_processed_tag`, `last_published_at`, and `processed_tags_at_boundary` (all handled tags sharing that timestamp). Record the last successful check separately from the last failure. Do not store credentials or release bodies.

## First successful check

1. If a release was already reported in this task, use that verified exact tag as the baseline.
2. Otherwise call `list` with the desired filters, and persist the newest entry and every returned tag sharing its publication timestamp. Increase `--limit` if `has_more` could hide a boundary tie. Set `initialized: true` even for an empty history, with null tag/time and an empty tag list, so the first future release will be notified.
3. This establishes the baseline quietly. Send an initial-release summary only if requested; an already-existing release is not a newly published event.

## Subsequent checks

1. Load state. Missing state starts the initial procedure; corrupt state or mismatched filters/repository requires repair, not silent reinitialization.
2. Run `list --since <last_processed_tag>` with the saved filters. For an initialized empty baseline, run `list` without `--since` and increase `--limit` until `has_more` is false. The result includes other tags at the same timestamp to avoid missing simultaneous publications; remove `processed_tags_at_boundary` from the candidates.
3. If there are no candidates, stay quiet. A repeated check with the same state must produce no duplicate notification. Changes to old release bodies and moving channel tags are outside this new-publication monitor.
4. Process candidates oldest first. Fetch `notes` and prepare 3–7 supported changes, the exact tag, publication date and direct release link. State when only part of the notes was read. Follow pagination when the required changes are not yet supported.
5. Advance state only after successful notification delivery. On a newer timestamp, reset boundary tags to that release; at the same timestamp, append its tag. Write state atomically through a same-directory temporary file and rename, preserving the previous state if writing fails.

If the host cannot acknowledge delivery, persist a pending notification and use its tag as an idempotency key when supported. Do not claim exactly-once delivery: a crash between sending and saving can duplicate a notification. Avoid advancing past an undelivered or unread release.

## Failures

- Network/rate-limit, malformed response, missing baseline or history-limit errors preserve the cursor. Record failure and retry at the next scheduled check. Surface a persistent failure or a required user action once; remain quiet for unchanged failures.
- A missing/deleted baseline needs an explicit recovery decision, not replacement with today's latest release.
- `RESULT_LIMIT` requires a larger `--limit` or a narrower comparison; no partial new-release list is acknowledged.
- `latest` means GitHub's designated latest stable version, which can differ from newest publication. Use `list --since` on every monitoring run so backports are not missed when `latest` stays unchanged.
- Keep schedule and user notification preferences in the host automation. This skill does not create its own daemon, cron job or service.
