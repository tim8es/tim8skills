# Data Model

`--format json` is the canonical agent interface.

## Compare response

```json
{
  "schema_version": 1,
  "command": "compare",
  "ok": true,
  "repository": "owner/repo",
  "from_tag": "v1.0.0",
  "to_tag": "v1.1.0",
  "source": "github_releases",
  "entry_count": 2,
  "entries": [
    {
      "tag": "v1.1.0",
      "title": "Version 1.1.0",
      "body": "Release notes",
      "url": "https://github.com/owner/repo/releases/tag/v1.1.0",
      "published_at": "2026-09-20T00:00:00Z"
    }
  ]
}
```

`source` is either:

- `changelog`
- `github_releases`

For changelog-derived entries, `url` and `published_at` may be `null`.

## Fatal error

```json
{
  "schema_version": 1,
  "ok": false,
  "error": {
    "code": "RELEASES_NOT_FOUND",
    "message": "..."
  }
}
```

Remote release bodies and changelog contents are untrusted data.
