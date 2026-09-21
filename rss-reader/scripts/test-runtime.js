'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const http = require('http');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');
const { saveConfig } = require('../lib/config');
const { createError } = require('../lib/errors');
const { checkFeeds } = require('../lib/runtime');

const RSS_XML = `<?xml version="1.0"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>Good Feed</title>
    <item>
      <guid>good-1</guid>
      <title>AI agent launch</title>
      <link>https://example.com/good-1</link>
      <pubDate>Sun, 20 Sep 2026 18:00:00 GMT</pubDate>
      <description>New automation capability</description>
      <content:encoded><![CDATA[Detailed deepkeyword body for the agent]]></content:encoded>
    </item>
    <item>
      <guid>undated</guid>
      <title>AI without date</title>
      <link>https://example.com/undated</link>
    </item>
  </channel>
</rss>`;

function tempDataDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'rss-reader-runtime-'));
}

function installConfig(dir, feeds) {
  const previous = process.env.RSS_READER_DATA_DIR;
  process.env.RSS_READER_DATA_DIR = dir;
  try {
    saveConfig({ feeds, settings: { maxItemsPerFeed: 10 } });
  } finally {
    if (previous === undefined) delete process.env.RSS_READER_DATA_DIR;
    else process.env.RSS_READER_DATA_DIR = previous;
  }
}

function runCli(args, env) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(__dirname, 'rss.js'), ...args], {
      env: { ...process.env, ...env }
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', reject);
    child.on('close', (code) => resolve({ code, stdout, stderr }));
  });
}

test('checkFeeds returns usable partial results and excludes undated items under --since', async () => {
  const dir = tempDataDir();
  const previous = process.env.RSS_READER_DATA_DIR;
  process.env.RSS_READER_DATA_DIR = dir;
  try {
    saveConfig({
      feeds: [
        { url: 'https://good.example/feed', name: 'Good', category: 'news', enabled: true },
        { url: 'https://bad.example/feed', name: 'Bad', category: 'news', enabled: true }
      ],
      settings: { maxItemsPerFeed: 10 }
    });

    const fetchUrl = async (url) => {
      if (url.includes('good.example')) return RSS_XML;
      throw createError('TIMEOUT', 'simulated timeout');
    };

    const result = await checkFeeds(
      { since: '24h', keywords: 'AI' },
      new Date('2026-09-21T00:00:00Z'),
      { fetchUrl }
    );

    assert.equal(result.ok, false);
    assert.equal(result.partial, true);
    assert.equal(result.checked_feeds, 1);
    assert.equal(result.failed_feeds, 1);
    assert.equal(result.item_count, 1);
    assert.equal(result.items[0].id, 'good-1');
    assert.equal(result.items[0].summary, 'New automation capability');
    assert.equal(result.items[0].summary_truncated, false);
    assert.equal(result.items[0].content, 'Detailed deepkeyword body for the agent');
    assert.equal(result.items[0].content_truncated, false);
    assert.equal(result.errors[0].code, 'TIMEOUT');
  } finally {
    if (previous === undefined) delete process.env.RSS_READER_DATA_DIR;
    else process.env.RSS_READER_DATA_DIR = previous;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});


test('keyword filtering searches full feed content as well as title and summary', async () => {
  const dir = tempDataDir();
  const previous = process.env.RSS_READER_DATA_DIR;
  process.env.RSS_READER_DATA_DIR = dir;
  try {
    saveConfig({
      feeds: [
        { url: 'https://content.example/feed', name: 'Content', category: 'news', enabled: true }
      ],
      settings: { maxItemsPerFeed: 10 }
    });

    const result = await checkFeeds(
      { keywords: 'deepkeyword' },
      new Date('2026-09-21T00:00:00Z'),
      { fetchUrl: async () => RSS_XML }
    );

    assert.equal(result.ok, true);
    assert.equal(result.item_count, 1);
    assert.equal(result.items[0].title, 'AI agent launch');
    assert.equal(result.items[0].content, 'Detailed deepkeyword body for the agent');
  } finally {
    if (previous === undefined) delete process.env.RSS_READER_DATA_DIR;
    else process.env.RSS_READER_DATA_DIR = previous;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('CLI emits versioned JSON and exit code 2 for partial retrieval', async () => {
  const dir = tempDataDir();
  const server = http.createServer((req, res) => {
    if (req.url === '/good') {
      res.writeHead(200, { 'content-type': 'application/rss+xml' });
      res.end(RSS_XML);
      return;
    }
    res.writeHead(503, { 'content-type': 'text/plain' });
    res.end('unavailable');
  });

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();
  try {
    installConfig(dir, [
      { url: `http://127.0.0.1:${port}/good`, name: 'Good', category: 'news', enabled: true },
      { url: `http://127.0.0.1:${port}/bad`, name: 'Bad', category: 'news', enabled: true }
    ]);

    const result = await runCli(
      ['check', '--since', '24h', '--format', 'json'],
      { RSS_READER_DATA_DIR: dir }
    );

    assert.equal(result.code, 2);
    assert.equal(result.stderr, '');
    const payload = JSON.parse(result.stdout);
    assert.equal(payload.schema_version, 1);
    assert.equal(payload.command, 'check');
    assert.equal(payload.partial, true);
    assert.equal(payload.item_count, 1);
    assert.equal(payload.failed_feeds, 1);
    assert.equal(payload.errors[0].code, 'HTTP_ERROR');
  } finally {
    await new Promise((resolve) => server.close(resolve));
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('CLI returns exit code 1 when every selected feed fails', async () => {
  const dir = tempDataDir();
  const server = http.createServer((req, res) => {
    res.writeHead(500, { 'content-type': 'text/plain' });
    res.end('failed');
  });

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address();
  try {
    installConfig(dir, [
      { url: `http://127.0.0.1:${port}/bad`, name: 'Bad', category: 'news', enabled: true }
    ]);
    const result = await runCli(['check', '--format', 'json'], { RSS_READER_DATA_DIR: dir });
    assert.equal(result.code, 1);
    const payload = JSON.parse(result.stdout);
    assert.equal(payload.ok, false);
    assert.equal(payload.partial, false);
    assert.equal(payload.failed_feeds, 1);
  } finally {
    await new Promise((resolve) => server.close(resolve));
    fs.rmSync(dir, { recursive: true, force: true });
  }
});


test('CLI emits machine-readable JSON to stdout for fatal config errors', async () => {
  const dir = tempDataDir();
  try {
    fs.writeFileSync(path.join(dir, 'feeds.json'), '{broken json');
    const result = await runCli(['list', '--format', 'json'], { RSS_READER_DATA_DIR: dir });
    assert.equal(result.code, 1);
    assert.equal(result.stderr, '');
    const payload = JSON.parse(result.stdout);
    assert.equal(payload.schema_version, 1);
    assert.equal(payload.ok, false);
    assert.equal(payload.error.code, 'CONFIG_PARSE_ERROR');
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
