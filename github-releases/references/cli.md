# CLI Reference

## Compare releases

```bash
node scripts/github-releases.js compare \
  --repo <owner/repo> \
  --from <tag> \
  --to <tag> \
  [--format json|text]
```

Alias: `compare-releases`.

The default format is `json`.

## Resolution strategy

1. Try `CHANGELOG.md` from the repository's default conventional branches (`main`, then `master`).
2. If both requested tags cannot be resolved from changelog sections, query the public GitHub Releases API.
3. Return the inclusive range between the two resolved releases.

No RSS/Atom feed is used by this skill.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Usage, validation, retrieval, or tag-resolution failure |

## Failure behavior

- Repository must be in `owner/repo` form.
- Both tags must resolve from the same source.
- HTTP timeout: 10 seconds.
- Maximum redirects: 5.
- Maximum response size: 5 MiB.
- Fatal JSON responses are written to stdout when JSON format is active.
