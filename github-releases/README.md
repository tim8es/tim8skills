# GitHub Releases

A focused agent skill for retrieving and comparing release notes from public GitHub repositories.

The runtime resolves release information deterministically. It first checks a repository changelog and falls back to the GitHub Releases API. The model is responsible only for analysis and summarization after retrieval.

## Requirements

- Node.js 18+
- npm

```bash
cd github-releases
npm ci
```

## Quick start

```bash
node scripts/github-releases.js compare \
  --repo owner/repo \
  --from v1.0.0 \
  --to v1.1.0 \
  --format json
```

## Scope

This skill handles GitHub release-note retrieval and comparison. It does not handle RSS/Atom feeds, general repository browsing, issues, pull requests, or code review.

See:

- [SKILL.md](SKILL.md)
- [references/cli.md](references/cli.md)
- [references/data-model.md](references/data-model.md)

## Tests

```bash
npm test
```
