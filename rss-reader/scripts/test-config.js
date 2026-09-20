'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const os = require('os');
const path = require('path');
const {
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
      settings: { maxItemsPerFeed: 5, maxAgeDays: 14 }
    });

    const config = loadConfig();
    assert.equal(config.feeds[0].name, 'Example');
    assert.equal(config.feeds[0].category, 'competitors');
    assert.equal(config.feeds[0].lastChecked, '2026-09-20T12:00:00.000Z');
    assert.equal(config.settings.maxItemsPerFeed, 5);
  });
});

test('rejects non-http feed URLs', () => {
  assert.throws(
    () => validateHttpUrl('file:///tmp/feed.xml'),
    (error) => error.code === 'INVALID_URL'
  );
});
