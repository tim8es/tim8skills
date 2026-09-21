# FeedPulse

A Claude Code skill for deterministic feed monitoring via RSS and Atom.

The runtime script handles network requests, XML parsing, dates, filtering, deduplication, and persisted feed state. The model is responsible for analysis and summarization after data has been retrieved.

## Requirements

- Node.js 18+
- npm

Install the runtime dependency once:

```bash
cd feed-pulse
npm ci
```

## Quick start

```bash
node scripts/feed-pulse.js add "https://example.com/feed.xml" --category competitors
node scripts/feed-pulse.js list
node scripts/feed-pulse.js check --since 24h --format json
node scripts/feed-pulse.js remove "https://example.com/feed.xml"
```

By default, feed configuration and mutable runtime state are stored outside the skill directory in the current user's home directory:

```text
<home>/.feed-pulse/feeds.json
```

Examples:

```text
macOS:   /Users/user/.feed-pulse/feeds.json
Linux:   /home/user/.feed-pulse/feeds.json
Windows: C:\Users\user\.feed-pulse\feeds.json
```

The directory and file are created automatically when state is first persisted. Set `FEED_PULSE_DATA_DIR` to use a different data directory, for example in tests, CI, or an isolated agent runtime.

## Agent interface

For agent workflows, prefer:

```bash
node scripts/feed-pulse.js check --since 24h --format json
```

The JSON response is versioned and includes per-source failures. A failed source is not treated as an empty source.

Feed items keep short feed-provided summaries separate from longer feed-provided content. Summaries are bounded to 2,000 characters and content to 8,000 characters, with explicit truncation flags. FeedPulse does not crawl the linked article page; agents can use the returned `url` with a web/browser tool when full-page reading is required.

See:

- [SKILL.md](SKILL.md) — runtime instructions for the model
- [references/cli.md](references/cli.md) — CLI reference and exit codes
- [references/data-model.md](references/data-model.md) — structured output schema
- [references/examples.md](references/examples.md) — usage patterns

## Tests

```bash
npm test
```

Tests use Node's built-in test runner and do not require live network access. CI validates the runtime on Linux, macOS, and Windows with Node.js 18, 20, and 22.
