# CLI Reference

## Contents

- Runtime
- Commands
- Filters
- Output formats
- Exit codes
- Configuration
- Failure behavior

## Runtime

Run commands from the `rss-reader` directory or address the script by its full skill-relative path.

```bash
node scripts/rss.js <command> [options]
```

Requirements:

- Node.js 18+
- `npm ci` completed in the skill directory
- network access for remote feeds

## Commands

### Add a feed

```bash
node scripts/rss.js add <url> [--category <category>] [--name <name>] [--format json]
```

The URL is fetched and parsed before it is persisted. Invalid or unsupported feeds are not added.

### Remove a feed

```bash
node scripts/rss.js remove <url-or-name> [--format json]
```

Alias: `rm`.

### List feeds

```bash
node scripts/rss.js list [--format json]
```

Alias: `ls`.

### Check feeds

```bash
node scripts/rss.js check [--category <category>] [--since <duration>] [--keywords <csv>] [--format <format>]
```

This is the primary retrieval command for agent use.

## Filters

### Category

```bash
--category competitors
```

Category matching is case-insensitive. Categories are normalized to lowercase when stored.

### Time

```bash
--since 24h
--since 7d
```

Only positive integer hours (`h`) and days (`d`) are accepted.

When `--since` is active, entries without a valid publication timestamp are excluded because their recency cannot be established.

### Keywords

```bash
--keywords "AI,agents,automation"
```

Matching is:

- case-insensitive;
- against title + description;
- OR-based across keywords;
- whitespace-trimmed.

## Output formats

### JSON

```bash
--format json
```

Canonical format for agents and automation. See [data-model.md](data-model.md).

### List

Default human-readable output.

### Ideas

```bash
--format ideas
```

Backward-compatible presentation format for `check`. Do not use it as the source for model analysis when JSON is available.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Fatal validation, configuration, command, or retrieval failure |
| `2` | Partial `check`: at least one feed succeeded and at least one failed |

For partial results, consume the JSON payload and inspect `errors`; do not discard valid items.

## Configuration

Default location:

```text
<home>/.rss-reader/feeds.json
```

Typical paths:

```text
macOS:   /Users/user/.rss-reader/feeds.json
Linux:   /home/user/.rss-reader/feeds.json
Windows: C:\Users\user\.rss-reader\feeds.json
```

The path is resolved from the current user's home directory. Runtime state is intentionally stored outside the skill directory so updating or replacing the skill does not mix code with mutable user data.

The directory and file are created automatically when state is persisted. Writes use a temporary file followed by a rename so an interrupted write does not normally leave a partially written `feeds.json`.

Override for isolated runs or tests on macOS/Linux:

```bash
RSS_READER_DATA_DIR=/tmp/rss-data node scripts/rss.js list --format json
```

PowerShell on Windows:

```powershell
$env:RSS_READER_DATA_DIR="C:\temp\rss-data"
node scripts/rss.js list --format json
```

When `RSS_READER_DATA_DIR` is set, `feeds.json` is read from and written to that directory instead of the default path.

Malformed JSON is a fatal error. The script never silently replaces a malformed config with an empty one.

## Failure behavior

- HTTP timeout: 10 seconds.
- Maximum redirects: 5.
- Maximum response size: 5 MiB.
- Only `http://` and `https://` URLs are accepted.
- Failed feeds are reported separately from feeds with zero matching items.
- `last_checked` is updated only after a successful fetch and parse.
