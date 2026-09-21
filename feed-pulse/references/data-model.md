# Data Model

## Contents

- Check response
- Feed item
- Error object
- Feed object
- Other command responses

`--format json` is the canonical agent interface. All top-level JSON responses include `schema_version`.

## Check response

```json
{
  "schema_version": 2,
  "command": "check",
  "ok": true,
  "partial": false,
  "checked_at": "2026-09-21T00:00:00.000Z",
  "filters": {
    "category": null,
    "since": "24h",
    "keywords": ["ai", "agents"]
  },
  "feed_count": 2,
  "checked_feeds": 2,
  "failed_feeds": 0,
  "item_count": 1,
  "items": [],
  "errors": []
}
```

Semantics:

- `ok=true`: all requested sources completed successfully.
- `partial=true`: at least one source succeeded and at least one failed.
- `feed_count`: configured enabled feeds selected by the category filter.
- `checked_feeds`: feeds successfully fetched and parsed.
- `failed_feeds`: feeds with retrieval or parsing failures.
- `item_count`: number of returned items after filters and deduplication.

## Feed item

```json
{
  "id": "https://example.com/posts/1",
  "feed_name": "Example Blog",
  "feed_url": "https://example.com/feed.xml",
  "category": "competitors",
  "title": "New feature",
  "url": "https://example.com/posts/1",
  "published_at": "2026-09-20T18:30:00.000Z",
  "summary": "Short feed-provided summary",
  "summary_truncated": false,
  "content": "Longer feed-provided article content, when available",
  "content_truncated": false
}
```

`summary` is normalized from the feed's `summary` or `description` field and is limited to 2,000 characters.

`content` is normalized separately from Atom `content` or namespaced RSS full-content fields such as `content:encoded` and is limited to 8,000 characters.

`summary_truncated` and `content_truncated` report whether FeedPulse shortened the corresponding normalized field. A value of `false` does **not** prove that the publisher supplied the complete linked article; it only means FeedPulse did not truncate the feed-provided value.

If `content` is `null`, the feed did not provide a dedicated full-content field recognized by the runtime. Agents that need the linked page itself should retrieve `url` with an appropriate web/browser tool.

`published_at` is either an ISO 8601 timestamp or `null`. Missing dates are never replaced with the current time.

`id` selection order:

1. feed GUID/ID;
2. item URL;
3. deterministic SHA-256 fallback.

Deduplication scopes IDs by feed source so unrelated feeds with identical local GUIDs do not collide.

Keyword filtering searches `title`, `summary`, and `content`.

## Error object

```json
{
  "feed_name": "Example Blog",
  "feed_url": "https://example.com/feed.xml",
  "code": "TIMEOUT",
  "message": "Request timed out after 10000 ms."
}
```

Common codes include:

- `INVALID_URL`
- `TIMEOUT`
- `HTTP_ERROR`
- `RESPONSE_TOO_LARGE`
- `TOO_MANY_REDIRECTS`
- `XML_PARSE_ERROR`
- `UNSUPPORTED_FEED`
- `CONFIG_PARSE_ERROR`
- `CONFIG_INVALID`

## Feed object

```json
{
  "url": "https://example.com/feed.xml",
  "name": "Example Blog",
  "category": "competitors",
  "enabled": true,
  "last_checked": "2026-09-21T00:00:00.000Z",
  "last_item_date": "2026-09-20T18:30:00.000Z"
}
```

## Other command responses

### Add

```json
{
  "schema_version": 2,
  "command": "add",
  "ok": true,
  "feed": {},
  "validated_item_count": 12
}
```

### Remove

```json
{
  "schema_version": 2,
  "command": "remove",
  "ok": true,
  "feed": {}
}
```

### List

```json
{
  "schema_version": 2,
  "command": "list",
  "ok": true,
  "feed_count": 2,
  "feeds": []
}
```

Fatal command errors emitted in JSON mode are written to stdout and have the form:

```json
{
  "schema_version": 2,
  "ok": false,
  "error": {
    "code": "USAGE_ERROR",
    "message": "..."
  }
}
```
