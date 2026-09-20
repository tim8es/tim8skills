# RSS Reader

A Claude Code skill for deterministic RSS/Atom feed retrieval and monitoring.

The runtime script handles network requests, XML parsing, dates, filtering, deduplication, and persisted feed state. The model is responsible for analysis and summarization after data has been retrieved.

## Requirements

- Node.js 18+
- npm

Install the runtime dependency once:

```bash
cd rss-reader
npm ci
```

## Quick start

```bash
node scripts/rss.js add "https://example.com/feed.xml" --category competitors
node scripts/rss.js list
node scripts/rss.js check --since 24h --format json
node scripts/rss.js remove "https://example.com/feed.xml"
```

Feed configuration is stored in `data/feeds.json`. Set `RSS_READER_DATA_DIR` to use a different data directory.

## Agent interface

For agent workflows, prefer:

```bash
node scripts/rss.js check --since 24h --format json
```

The JSON response is versioned and includes per-source failures. A failed source is not treated as an empty source.

See:

- [SKILL.md](SKILL.md) — runtime instructions for the model
- [references/cli.md](references/cli.md) — CLI reference and exit codes
- [references/data-model.md](references/data-model.md) — structured output schema
- [references/examples.md](references/examples.md) — usage patterns

## Tests

```bash
npm test
```

Tests use Node's built-in test runner and do not require live network access.

## Legacy command

`compare-releases` remains available for backward compatibility, but GitHub release comparison is not part of the primary RSS skill contract.
