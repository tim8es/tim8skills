# CLI Reference

Run `node scripts/github-releases.js --help` for syntax. All commands default to JSON; `--format text` is for manual reading. No authentication or dependency installation is required for public repositories.

| Command | Required flags | Optional flags |
| --- | --- | --- |
| `latest` | `--repo owner/repo` | Discovery filters |
| `list` | `--repo owner/repo` | `--since exact-tag`, `--limit 20`, discovery filters |
| `notes` | `--repo owner/repo --tag exact-tag` | `--offset 0`, `--max-body-chars 12000`, `--release-body` |
| `compare` | `--repo owner/repo --from exact-tag --to exact-tag` | `--max-body-chars 12000`, discovery filters |

`compare-releases` remains an alias. Tags are exact and case-sensitive; use discovery output rather than adding/removing `v`.

## Selection

- Publication comes only from GitHub Releases API. Drafts are always excluded.
- Discovery filters: `--include-prereleases` admits GitHub-marked prereleases; `--include-nonversion` admits tags outside the default `v?N.N.N[-suffix or +metadata]` pattern. These are independent flags.
- `latest` uses GitHub's designated latest stable release. If that entry is a non-version channel tag, or `/latest` returns 404, it selects the newest matching publication from history. With either inclusion flag, it also uses publication order. The `selection` field distinguishes these meanings.
- `list` sorts by `published_at` descending (exact tag ascending breaks ties), not semantic version or API position. Backports published later are included. Default output limit is 20, maximum 1,000. `has_more` indicates output truncation for ordinary discovery.
- `list --since` requires a baseline in the filtered history and returns later publications, plus other tags with the same timestamp. The baseline itself is excluded. Deduplicate boundary tags in the host monitor. If the result exceeds `--limit`, the command fails instead of returning a partial monitoring result.
- `compare` includes both endpoints and matching publications between their publication timestamps, regardless of argument order. Same-tag comparison returns one release. At most 20 releases per comparison. It does not compute code differences.

## Notes and output limits

`latest` and `list` emit metadata only. `compare` emits bounded GitHub release bodies; use `notes` for each release's linked detailed changelog.

`notes` follows the first eligible Markdown link labelled Changelog, Release notes or Plain Markdown, from `raw.githubusercontent.com/owner/repo/ref/path.md` or `github.com/owner/repo/blob/ref/path.md`. Default-branch refs (`main`, `master`) are replaced with the exact release tag; explicit commit pins remain pinned. Only the same repository is allowed, and redirects are rejected. Other hosts/branches/formats remain visible in the original release body but are not fetched. Links are not followed recursively. If the pinned file fails, the command fails; `--release-body` explicitly requests the original GitHub description without following links.

Bodies default to 12,000 UTF-16 code units (configurable 1–50,000); a surrogate pair can exceed the budget by one unit. Output reports `body_length`, `body_offset`, `body_truncated` and `next_offset`. Continue with `notes --offset <next_offset>` and the same options. `null` means no following page. For a truncated `compare` body use `notes --release-body --offset ...`. A partial page is not the full changelog. A tag is pinned by name, not guaranteed immutable if the publisher moves it.

## Retrieval bounds and errors

- History scans: 20 releases per API page, at most 50 pages. All pages are needed because API order need not match publication order. At the cap, fail with `HISTORY_LIMIT`; never report a complete empty result from partial history. `latest` normally takes one API request. Public unauthenticated GitHub rate limits apply; a large history can consume much of that budget.
- Each HTTP request has a 10-second total deadline and inactivity timeout, a 5 MiB body limit and at most 5 redirects (zero for linked notes).
- Exit 0 requires successful structured data; exit 1 reports usage, retrieval, limit, malformed response or missing-tag errors. JSON errors use `ok: false` and `error.code/message`.
- Schema v2 replaces changelog-first v1: no unverified `main` entries, exact tags, bounded bodies and explicit publication filters. Callers depending on v1 tag normalization or `source: changelog` must migrate.
