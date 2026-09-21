# GitHub Releases

Retrieve published release metadata and bounded notes from public GitHub repositories using Node.js 18+ and its standard library. No runtime dependencies or installation step are needed.

```bash
node scripts/github-releases.js latest --repo openclaw/openclaw
node scripts/github-releases.js list --repo openclaw/openclaw --since v2026.9.4
node scripts/github-releases.js notes --repo openclaw/openclaw --tag v2026.9.5
node scripts/github-releases.js compare --repo openclaw/openclaw --from v2026.9.4 --to v2026.9.5
```

Publication is verified through GitHub Releases API. Discovery omits bodies, drafts, prereleases and non-version channel tags by default. Detailed notes support bounded pages and same-repository Markdown links pinned to a release tag or explicit commit.

The CLI is read-only and stateless. A host scheduler owns monitoring state and notifications; follow the [monitoring procedure](references/monitoring.md) to establish a quiet baseline, deduplicate runs and preserve state on errors.

- [Agent workflow](SKILL.md)
- [Commands, filters, pagination and migration from v1](references/cli.md)
- [JSON schema v2](references/data-model.md)

Run offline tests with `npm test`. The HTTP boundary test uses a temporary loopback server; no external services are contacted. Live GitHub checks are separate and subject to public API rate limits.
