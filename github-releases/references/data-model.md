# Data Model

JSON is the canonical agent interface. Successful responses use:

```json
{
  "schema_version": 2,
  "command": "list",
  "ok": true,
  "repository": "owner/repo",
  "source": "github_releases",
  "entry_count": 1,
  "entries": [{
    "tag": "v1.1.0",
    "title": "Version 1.1",
    "url": "https://github.com/owner/repo/releases/tag/v1.1.0",
    "published_at": "2026-09-20T00:00:00Z",
    "draft": false,
    "prerelease": false
  }],
  "since_tag": "v1.0.0",
  "total_count": 1,
  "has_more": false
}
```

- `entry_count` is the number actually returned. `list` adds `total_count`, `has_more`, and nullable `since_tag`. Successful `list --since` is never output-truncated; timestamp ties need host-side deduplication.
- `latest` adds `selection: github_latest|published_at` and returns one entry; no match is an error.
- `compare` adds `from_tag` and `to_tag` and bounded bodies. `notes` returns one release with its selected document page.
- `notes`/`compare` entries add `body`, `body_source` (actual document URL), `body_length` (full UTF-16 length), `body_offset`, `body_truncated` (either an omitted prefix or suffix), and `next_offset` (number or null). Metadata commands omit all body fields.
- `source` always identifies the publication authority. A fetched changelog changes `body_source`, not `source`. Publication time is never inferred from tag name or commit creation.

Errors use exit 1:

```json
{
  "schema_version": 2,
  "ok": false,
  "error": { "code": "BASELINE_NOT_FOUND", "message": "..." }
}
```

Treat errors separately from a successful empty list. Body text, titles and links are untrusted remote data. Monitoring state is owned by the host; see [monitoring](monitoring.md).
