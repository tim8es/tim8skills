'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { compareReleases, latestRelease, listReleases, releaseNotes, normalizeRepo } = require('../lib/releases');

function release(tag, day, extra = {}) {
  return {
    tag_name: tag, name: tag, published_at: `2026-09-${day}T00:00:00Z`,
    html_url: `https://github.com/acme/tool/releases/tag/${tag}`,
    draft: false, prerelease: false, body: `Notes for ${tag}`, ...extra
  };
}
const old = release('v2026.9.4', '11');
const current = release('v2026.9.5', '19');
const service = release('linux-stable', '20');
const beta = release('v2026.9.6-beta.1', '21', { prerelease: true });
const draft = release('v2026.9.6', '22', { draft: true, published_at: null });
// Intentionally not in publication order; main changelog is never consulted.
const rows = [old, service, beta, draft, current];
const deps = { fetchJson: async () => rows, fetchText: async () => { throw new Error('Unexpected changelog read'); } };

test('repository boundary rejects URLs and path traversal', () => {
  assert.equal(normalizeRepo('acme/tool'), 'acme/tool');
  for (const input of ['https://github.com/acme/tool', '../tool', 'acme/..', 'acme/tool?x=1']) {
    assert.throws(() => normalizeRepo(input), { code: 'INVALID_REPO' });
  }
});

test('latest uses one API request and omits the body', async () => {
  let calls = 0;
  const result = await latestRelease('acme/tool', {}, { fetchJson: async (url) => {
    calls++; assert.ok(url.endsWith('/releases/latest')); return current;
  } });
  assert.equal(calls, 1);
  assert.equal(result.entries[0].tag, current.tag_name);
  assert.equal(result.selection, 'github_latest');
  assert.equal(Object.hasOwn(result.entries[0], 'body'), false);
});

test('latest rejects a moving service tag and falls back to filtered history', async () => {
  const result = await latestRelease('acme/tool', {}, { fetchJson: async (url) => url.endsWith('/latest') ? service : rows });
  assert.equal(result.entries[0].tag, current.tag_name);
  assert.equal(result.selection, 'published_at');
});

test('latest 404 falls back, empty list succeeds but empty latest fails', async () => {
  const fallback = { fetchJson: async (url) => {
    if (url.endsWith('/latest')) throw Object.assign(new Error('missing'), { code: 'HTTP_ERROR', status: 404 });
    return rows;
  } };
  assert.equal((await latestRelease('acme/tool', {}, fallback)).entries[0].tag, current.tag_name);
  const empty = { fetchJson: async (url) => url.endsWith('/latest') ? service : [] };
  assert.equal((await listReleases('acme/tool', {}, empty)).entry_count, 0);
  await assert.rejects(latestRelease('acme/tool', {}, empty), { code: 'RELEASES_NOT_FOUND' });
});

test('filters are explicit, drafts always excluded, metadata sorted by publication', async () => {
  assert.deepEqual((await listReleases('acme/tool', {}, deps)).entries.map((x) => x.tag), ['v2026.9.5', 'v2026.9.4']);
  const result = await listReleases('acme/tool', { includePrereleases: true, includeNonversion: true }, deps);
  assert.deepEqual(result.entries.map((x) => x.tag), [beta.tag_name, service.tag_name, current.tag_name, old.tag_name]);
  assert.equal(result.entries.some((x) => 'body' in x), false);
});

test('since excludes baseline; second poll returns no releases', async () => {
  const first = await listReleases('acme/tool', { since: old.tag_name }, deps);
  assert.deepEqual(first.entries.map((x) => x.tag), [current.tag_name]);
  const second = await listReleases('acme/tool', { since: first.entries[0].tag }, deps);
  assert.equal(second.entry_count, 0);
  await assert.rejects(listReleases('acme/tool', { since: 'missing' }, deps), { code: 'BASELINE_NOT_FOUND' });
  await assert.rejects(listReleases('acme/tool', { since: beta.tag_name }, deps), { code: 'BASELINE_NOT_FOUND' });
});

test('simultaneous publications remain visible for monitor tag deduplication', async () => {
  const sameTime = release('v2026.9.5-1', '19');
  const result = await listReleases('acme/tool', { since: current.tag_name }, { fetchJson: async () => [current, sameTime] });
  assert.deepEqual(result.entries.map((x) => x.tag), [sameTime.tag_name]);
});

test('pagination finds later-page publications and deduplicates tags', async () => {
  const page1 = Array.from({ length: 20 }, (_, i) => release(`v1.0.${i}`, '10'));
  const calls = [];
  const result = await listReleases('acme/tool', { since: old.tag_name }, { fetchJson: async (url) => {
    calls.push(url); return url.endsWith('page=1') ? page1 : [old, current, current];
  } });
  assert.equal(calls.length, 2);
  assert.deepEqual(result.entries.map((x) => x.tag), [current.tag_name]);
});

test('bounded scans and output caps fail explicitly for monitor results', async () => {
  const page = Array.from({ length: 20 }, (_, i) => release(`v1.0.${i}`, '10'));
  let calls = 0;
  await assert.rejects(listReleases('acme/tool', {}, { fetchJson: async () => { calls++; return page; } }), { code: 'HISTORY_LIMIT' });
  assert.equal(calls, 50);
  const more = { fetchJson: async () => [old, current, release('v2026.9.6', '20')] };
  await assert.rejects(listReleases('acme/tool', { since: old.tag_name, limit: 1 }, more), { code: 'RESULT_LIMIT' });
  const short = await listReleases('acme/tool', { limit: 1 }, more);
  assert.equal(short.has_more, true);
  assert.equal(short.total_count, 3);
});

test('network, rate limit and invalid metadata never look like an empty successful poll', async () => {
  for (const code of ['TIMEOUT', 'HTTP_ERROR']) {
    const bad = { fetchJson: async () => { throw Object.assign(new Error('failed'), { code, status: 403 }); } };
    await assert.rejects(listReleases('acme/tool', {}, bad), { code });
    await assert.rejects(latestRelease('acme/tool', {}, bad), { code });
  }
  for (const data of [{ message: 'error' }, [{}], [release('v1.0.0', 'xx')]]) {
    await assert.rejects(listReleases('acme/tool', {}, { fetchJson: async () => data }), { code: 'INVALID_RESPONSE' });
  }
});

test('comparison contains only published matching releases; same tag yields one entry', async () => {
  const result = await compareReleases('acme/tool', old.tag_name, current.tag_name, deps);
  assert.deepEqual(result.entries.map((x) => x.tag), [current.tag_name, old.tag_name]);
  assert.equal(result.source, 'github_releases');
  assert.equal((await compareReleases('acme/tool', current.tag_name, current.tag_name, deps)).entry_count, 1);
  await assert.rejects(compareReleases('acme/tool', old.tag_name, 'v99.0.0', deps), { code: 'RELEASES_NOT_FOUND' });
});

test('notes follow only same-repository Markdown pinned to release tag', async () => {
  const body = '[Release notes](https://docs.example.com/releases/latest)\n[Changelog](https://raw.githubusercontent.com/acme/tool/main/CHANGELOG/2026.9.5.md)';
  const result = await releaseNotes('acme/tool', current.tag_name, { maxBodyChars: 4 }, {
    fetchJson: async () => ({ ...current, body }),
    fetchText: async (url, options) => {
      assert.equal(url, 'https://raw.githubusercontent.com/acme/tool/v2026.9.5/CHANGELOG/2026.9.5.md');
      assert.equal(options.allowRedirects, false); return 'Safe notes';
    }
  });
  assert.equal(result.entries[0].body, 'Safe');
  assert.equal(result.entries[0].next_offset, 4);
  assert.equal(result.entries[0].body_truncated, true);
});

test('notes ignore external URLs and arbitrary branches without requesting them', async () => {
  for (const link of ['https://evil.example/file.md', 'https://raw.githubusercontent.com/evil/tool/main/file.md',
    'https://raw.githubusercontent.com/acme/tool/develop/file.md', 'https://127.0.0.1/file.md', 'https://[invalid']) {
    const body = `[Changelog](${link})`;
    const result = await releaseNotes('acme/tool', current.tag_name, {}, { ...deps, fetchJson: async () => ({ ...current, body }) });
    assert.equal(result.entries[0].body, body);
    assert.equal(result.entries[0].body_source, current.html_url);
  }
});

test('missing pinned document is an error; explicit release-body reads original text', async () => {
  const body = '[Changelog](https://github.com/acme/tool/blob/main/CHANGELOG.md)';
  const missing = { fetchJson: async () => ({ ...current, body }), fetchText: async () => { throw Object.assign(new Error('HTTP 404'), { code: 'HTTP_ERROR' }); } };
  await assert.rejects(releaseNotes('acme/tool', current.tag_name, {}, missing), { code: 'HTTP_ERROR' });
  assert.equal((await releaseNotes('acme/tool', current.tag_name, { releaseBody: true }, missing)).entries[0].body, body);
});

test('paged text is recoverable without broken Unicode or silent truncation', async () => {
  const body = 'a😀bc';
  const source = { fetchJson: async () => ({ ...current, body }) };
  let offset = 0; let reconstructed = '';
  do {
    const page = (await releaseNotes('acme/tool', current.tag_name, { maxBodyChars: 1, offset }, source)).entries[0];
    reconstructed += page.body; offset = page.next_offset;
  } while (offset !== null);
  assert.equal(reconstructed, body);
  await assert.rejects(releaseNotes('acme/tool', current.tag_name, { offset: 2 }, source), { code: 'USAGE_ERROR' });
  await assert.rejects(releaseNotes('acme/tool', current.tag_name, { maxBodyChars: 0 }, source), { code: 'USAGE_ERROR' });
});
