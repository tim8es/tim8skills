'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {
  dataDir,
  loadConfig,
  saveConfig,
  validateHttpUrl
} = require('../lib/config');

function withTempDataDir(fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'rss-reader-config-'));
  const previous = process.env.RSS_READER_DATA_DIR;
  process.env.RSS_READER_DATA_DIR = dir;
  try {
    return fn(dir);
  } finally {
    if (previous === undefined) delete process.env.RSS_READER_DATA_DIR;
    else process.env.RSS_READER_DATA_DIR = previous;
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

test('default data directory is outside the skill directory', () => {
  const previous = process.env.RSS_READER_DATA_DIR;
  delete process.env.RSS_READER_DATA_DIR;
  try {
    assert.equal(dataDir(), path.join(os.homedir(), '.rss-reader'));
    assert.notEqual(dataDir(), path.join(__dirname, '..', 'data'));
  } finally {
    if (previous !== undefined) process.env.RSS_READER_DATA_DIR = previous;
  }
});

test('RSS_READER_DATA_DIR overrides the default data directory', () => {
  withTempDataDir((dir) => {
    assert.equal(dataDir(), dir);
  });
});

test('missing config returns an empty default without creating files', () => {
  withTempDataDir((dir) => {
    assert.deepEqual(loadConfig(), {
      version: 1,
      feeds: [],
      settings: { maxItemsPerFeed: 10 }
    });
    assert.equal(fs.existsSync(path.join(dir, 'feeds.json')), false);
  });
});

test('saveConfig creates a missing data directory', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rss-reader-create-dir-'));
  const target = path.join(root, 'nested', 'state');
  const previous = process.env.RSS_READER_DATA_DIR;
  process.env.RSS_READER_DATA_DIR = target;
  try {
    saveConfig({ feeds: [], settings: { maxItemsPerFeed: 10 } });
    assert.equal(fs.existsSync(path.join(target, 'feeds.json')), true);
  } finally {
    if (previous === undefined) delete process.env.RSS_READER_DATA_DIR;
    else process.env.RSS_READER_DATA_DIR = previous;
    fs.rmSync(root, { recursive: true, force: true });
  }
});

test('malformed config fails explicitly instead of resetting state', () => {
  withTempDataDir((dir) => {
    fs.writeFileSync(path.join(dir, 'feeds.json'), '{broken json');
    assert.throws(
      () => loadConfig(),
      (error) => error.code === 'CONFIG_PARSE_ERROR'
    );
  });
});

test('save/load normalizes categories and preserves feed state', () => {
  withTempDataDir(() => {
    saveConfig({
      feeds: [{
        url: 'https://example.com/feed.xml',
        name: ' Example ',
        category: ' Competitors ',
        enabled: true,
        lastChecked: '2026-09-20T12:00:00Z',
        lastItemDate: null
      }],
      settings: { maxItemsPerFeed: 5 }
    });

    const config = loadConfig();
    assert.equal(config.feeds[0].name, 'Example');
    assert.equal(config.feeds[0].category, 'competitors');
    assert.equal(config.feeds[0].lastChecked, '2026-09-20T12:00:00.000Z');
    assert.deepEqual(config.settings, { maxItemsPerFeed: 5 });
  });
});

test('rejects non-http feed URLs', () => {
  assert.throws(
    () => validateHttpUrl('file:///tmp/feed.xml'),
    (error) => error.code === 'INVALID_URL'
  );
});
