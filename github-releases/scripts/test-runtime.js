'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');

const { main, parseArgs } = require('../lib/runtime');

test('parseArgs parses compare arguments', () => {
  const parsed = parseArgs(['compare', '--repo', 'acme/tool', '--from', 'v1.0.0', '--to', 'v2.0.0']);
  assert.equal(parsed.command, 'compare');
  assert.equal(parsed.options.repo, 'acme/tool');
  assert.equal(parsed.options.from, 'v1.0.0');
  assert.equal(parsed.options.to, 'v2.0.0');
});

test('main returns non-zero for incomplete usage', async () => {
  const originalLog = console.log;
  console.log = () => {};
  try {
    assert.equal(await main(['compare', '--repo', 'acme/tool']), 1);
  } finally {
    console.log = originalLog;
  }
});

test('main supports deterministic JSON comparison through injected retrieval', async () => {
  const output = [];
  const originalLog = console.log;
  console.log = (value) => output.push(String(value));
  try {
    const code = await main(
      ['compare', '--repo', 'acme/tool', '--from', 'v1.0.0', '--to', 'v1.1.0', '--format', 'json'],
      {
        fetchText: async () => '## 1.1.0\nNew feature\n\n## 1.0.0\nInitial release',
        fetchJson: async () => []
      }
    );
    assert.equal(code, 0);
    const payload = JSON.parse(output.join('\n'));
    assert.equal(payload.source, 'changelog');
    assert.equal(payload.entry_count, 2);
  } finally {
    console.log = originalLog;
  }
});
