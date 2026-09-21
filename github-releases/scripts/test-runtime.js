'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { main, parseArgs } = require('../lib/runtime');

async function run(args, dependencies = {}) {
  const output = [];
  const original = console.log;
  console.log = (value) => output.push(String(value));
  try { return { code: await main(args, dependencies), text: output.join('\n') }; }
  finally { console.log = original; }
}

test('help works as a top-level flag and compare alias is preserved', async () => {
  for (const flag of ['--help', '-h', 'help']) {
    const result = await run([flag]);
    assert.equal(result.code, 0); assert.match(result.text, /latest --repo/);
  }
  assert.equal(parseArgs(['compare-releases']).command, 'compare');
});

test('CLI rejects incomplete, duplicate, unknown and command-inappropriate options before retrieval', async () => {
  const deps = { fetchJson: async () => { assert.fail('No network request expected'); } };
  for (const args of [
    ['compare', '--repo', 'acme/tool'], ['notes', '--repo', 'acme/tool'],
    ['latest', '--repo', 'acme/tool', '--since', 'v1.0.0'],
    ['list', '--repo', 'acme/tool', '--limit', '0'],
    ['list', '--repo', 'acme/tool', '--limit', 'abc'],
    ['latest', '--repo', 'a/b', '--repo', 'c/d'],
    ['latest', '--repo', 'a/b', '--unknown'], ['unknown', '--repo', 'a/b'], ['toString', '--repo', 'a/b']
  ]) {
    const result = await run(args, deps);
    assert.equal(result.code, 1); assert.equal(JSON.parse(result.text).error.code, 'USAGE_ERROR');
  }
});

test('CLI emits compact schema-v2 metadata and structured failures', async () => {
  const release = { tag_name: 'v1.0.0', name: 'v1', body: 'long body', draft: false, prerelease: false,
    published_at: '2026-09-19T00:00:00Z', html_url: 'https://github.com/acme/tool/releases/tag/v1.0.0' };
  const result = await run(['latest', '--repo', 'acme/tool'], { fetchJson: async () => release });
  assert.equal(result.code, 0);
  const payload = JSON.parse(result.text);
  assert.equal(payload.schema_version, 2);
  assert.equal(payload.entries[0].body, undefined);
  const failed = await run(['list', '--repo', 'acme/tool'], { fetchJson: async () => { throw Object.assign(new Error('offline'), { code: 'TIMEOUT' }); } });
  assert.equal(failed.code, 1); assert.equal(JSON.parse(failed.text).ok, false);
});
