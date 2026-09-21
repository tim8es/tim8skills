'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  CONTENT_MAX_CHARS,
  SUMMARY_MAX_CHARS,
  dedupeItems,
  normalizeKeywords,
  parseFeedXml,
  parseSince
} = require('../lib/feed');

test('parses RSS 2.0 with CDATA and GUID', () => {
  const xml = `<?xml version="1.0"?><rss version="2.0"><channel><title>Example RSS</title><item><guid>post-1</guid><title><![CDATA[Hello <b>world</b>]]></title><link>https://example.com/1</link><pubDate>Sun, 20 Sep 2026 12:00:00 GMT</pubDate><description><![CDATA[<p>Useful summary</p>]]></description></item></channel></rss>`;
  const result = parseFeedXml(xml, 'https://example.com/feed.xml');
  assert.equal(result.title, 'Example RSS');
  assert.equal(result.items.length, 1);
  assert.equal(result.items[0].id, 'post-1');
  assert.equal(result.items[0].title, 'Hello world');
  assert.equal(result.items[0].summary, 'Useful summary');
  assert.equal(result.items[0].summary_truncated, false);
  assert.equal(result.items[0].content, null);
  assert.equal(result.items[0].content_truncated, false);
  assert.equal(result.items[0].published_at, '2026-09-20T12:00:00.000Z');
});

test('parses Atom summary and content separately and prefers rel=alternate link', () => {
  const xml = `<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Atom Feed</title><entry><id>tag:example,1</id><title>Entry</title><link rel="self" href="https://example.com/api/1"/><link rel="alternate" href="https://example.com/posts/1"/><published>2026-09-20T10:00:00Z</published><summary>Summary</summary><content>Full body text</content></entry></feed>`;
  const result = parseFeedXml(xml, 'https://example.com/atom.xml');
  assert.equal(result.items[0].url, 'https://example.com/posts/1');
  assert.equal(result.items[0].published_at, '2026-09-20T10:00:00.000Z');
  assert.equal(result.items[0].summary, 'Summary');
  assert.equal(result.items[0].content, 'Full body text');
});

test('handles namespaced RSS date and content fields', () => {
  const xml = `<?xml version="1.0"?><rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>Namespaced</title><item><title>Item</title><link>https://example.com/x</link><dc:date>2026-09-19T09:30:00Z</dc:date><description>Short summary</description><content:encoded><![CDATA[<p>Body text</p>]]></content:encoded></item></channel></rss>`;
  const result = parseFeedXml(xml, 'https://example.com/feed');
  assert.equal(result.items[0].published_at, '2026-09-19T09:30:00.000Z');
  assert.equal(result.items[0].summary, 'Short summary');
  assert.equal(result.items[0].content, 'Body text');
});

test('marks summary and content truncation explicitly', () => {
  const summary = 's'.repeat(SUMMARY_MAX_CHARS + 1);
  const content = 'c'.repeat(CONTENT_MAX_CHARS + 1);
  const xml = `<rss version="2.0"><channel><title>Long Feed</title><item><title>Long</title><description>${summary}</description><content>${content}</content></item></channel></rss>`;
  const item = parseFeedXml(xml, 'https://example.com/feed').items[0];

  assert.equal(item.summary.length, SUMMARY_MAX_CHARS);
  assert.equal(item.summary_truncated, true);
  assert.equal(item.content.length, CONTENT_MAX_CHARS);
  assert.equal(item.content_truncated, true);
});

test('missing publication date stays null', () => {
  const xml = `<rss version="2.0"><channel><title>No Dates</title><item><title>Undated</title><link>https://example.com/u</link></item></channel></rss>`;
  assert.equal(parseFeedXml(xml, 'https://example.com/feed').items[0].published_at, null);
});

test('parseSince accepts positive hours/days and rejects malformed values', () => {
  const now = new Date('2026-09-21T00:00:00Z');
  assert.equal(parseSince('24h', now).toISOString(), '2026-09-20T00:00:00.000Z');
  assert.equal(parseSince('7d', now).toISOString(), '2026-09-14T00:00:00.000Z');
  assert.throws(() => parseSince('0h', now), /positive integer/);
  assert.throws(() => parseSince('1w', now), /positive integer/);
});

test('normalizes comma-separated keywords', () => {
  assert.deepEqual(normalizeKeywords(' AI, agents, ,Automation '), ['ai', 'agents', 'automation']);
});

test('deduplicates items by stable id within the same feed', () => {
  const item = { id: 'same', feed_url: 'https://example.com/feed', title: 'A', url: 'https://example.com/a' };
  const result = dedupeItems([item, { ...item, title: 'Changed title' }]);
  assert.equal(result.length, 1);
  assert.equal(result[0].title, 'A');
});

test('does not collide identical GUIDs from different feeds', () => {
  const a = { id: '1', feed_url: 'https://a.example/feed', title: 'A' };
  const b = { id: '1', feed_url: 'https://b.example/feed', title: 'B' };
  assert.equal(dedupeItems([a, b]).length, 2);
});

test('rejects unsupported XML roots', () => {
  assert.throws(() => parseFeedXml('<html><body>not a feed</body></html>'), /supported RSS, Atom, or RDF/);
});


test('preserves escaped angle brackets and nested Atom XHTML text', () => {
  const xml = `<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Text</title><entry><id>tag:example,2</id><title>1 &lt; 2 and 3 &gt; 2</title><summary type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml"><p>Nested <b>details</b></p></div></summary></entry></feed>`;
  const item = parseFeedXml(xml, 'https://example.com/feed.xml').items[0];
  assert.equal(item.title, '1 < 2 and 3 > 2');
  assert.equal(item.summary, 'Nested details');
});

test('resolves relative Atom links against feed and xml:base', () => {
  const xml = `<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xml:base="https://cdn.example/root/"><title>Relative</title><entry xml:base="posts/"><id>tag:example,3</id><title>Entry</title><link rel="alternate" href="../article/1"/></entry></feed>`;
  const item = parseFeedXml(xml, 'https://example.com/feed.xml').items[0];
  assert.equal(item.url, 'https://cdn.example/root/article/1');
});

test('truncation never leaves an unpaired Unicode surrogate', () => {
  const summary = `${'s'.repeat(SUMMARY_MAX_CHARS - 1)}😀tail`;
  const xml = `<rss version="2.0"><channel><title>Unicode</title><item><title>Item</title><description>${summary}</description></item></channel></rss>`;
  const item = parseFeedXml(xml, 'https://example.com/feed.xml').items[0];
  assert.equal(item.summary, `${'s'.repeat(SUMMARY_MAX_CHARS - 1)}😀`);
  assert.equal(item.summary_truncated, true);
  assert.doesNotMatch(item.summary, /[\uD800-\uDBFF]$/);
});
