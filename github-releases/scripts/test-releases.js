'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');

const {
  compareReleases,
  normalizeRepo,
  parseChangelog,
  selectRange
} = require('../lib/releases');

const CHANGELOG = `# Changelog

## [1.2.0] - 2026-09-20

- Added agents.

## [1.1.0] - 2026-09-10

- Fixed parsing.

## [1.0.0] - 2026-09-01

- Initial release.
`;

test('normalizeRepo accepts owner/repo and rejects arbitrary URLs', () => {
  assert.equal(normalizeRepo('openai/example'), 'openai/example');
  assert.throws(() => normalizeRepo('https://github.com/openai/example'), { code: 'INVALID_REPO' });
});

test('parseChangelog extracts version sections', () => {
  const entries = parseChangelog(CHANGELOG);
  assert.equal(entries.length, 3);
  assert.equal(entries[0].tag, '1.2.0');
  assert.match(entries[0].body, /Added agents/);
});

test('selectRange includes both requested releases and intermediates', () => {
  const entries = parseChangelog(CHANGELOG);
  const selected = selectRange(entries, 'v1.0.0', 'v1.2.0');
  assert.deepEqual(selected.map((entry) => entry.tag), ['1.2.0', '1.1.0', '1.0.0']);
});

test('compareReleases prefers matching changelog data', async () => {
  const result = await compareReleases('acme/tool', 'v1.0.0', 'v1.2.0', {
    fetchText: async () => CHANGELOG,
    fetchJson: async () => { throw new Error('API should not be called'); }
  });

  assert.equal(result.ok, true);
  assert.equal(result.source, 'changelog');
  assert.equal(result.entry_count, 3);
});

test('compareReleases falls back to GitHub Releases API', async () => {
  const releases = [
    {
      tag_name: 'v2.0.0',
      name: 'Version 2',
      body: 'Breaking API change.',
      html_url: 'https://github.com/acme/tool/releases/tag/v2.0.0',
      published_at: '2026-09-20T00:00:00Z'
    },
    {
      tag_name: 'v1.0.0',
      name: 'Version 1',
      body: 'Initial release.',
      html_url: 'https://github.com/acme/tool/releases/tag/v1.0.0',
      published_at: '2026-09-01T00:00:00Z'
    }
  ];

  const result = await compareReleases('acme/tool', 'v1.0.0', 'v2.0.0', {
    fetchText: async () => '# Changelog\n\nNo version headings here.',
    fetchJson: async () => releases
  });

  assert.equal(result.source, 'github_releases');
  assert.equal(result.entry_count, 2);
  assert.equal(result.entries[0].url, 'https://github.com/acme/tool/releases/tag/v2.0.0');
});

test('compareReleases fails explicitly when both tags cannot be resolved', async () => {
  await assert.rejects(
    () => compareReleases('acme/tool', 'v1.0.0', 'v9.0.0', {
      fetchText: async () => '# Changelog',
      fetchJson: async () => [{ tag_name: 'v1.0.0' }]
    }),
    { code: 'RELEASES_NOT_FOUND' }
  );
});
