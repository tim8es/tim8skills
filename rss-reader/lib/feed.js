'use strict';

const crypto = require('crypto');
const { XMLParser, XMLValidator } = require('fast-xml-parser');
const { normalizeText, rawText } = require('./config');
const { createError } = require('./errors');

const SUMMARY_MAX_CHARS = 2000;
const CONTENT_MAX_CHARS = 8000;

function parser() {
  return new XMLParser({
    ignoreAttributes: false,
    attributeNamePrefix: '@_',
    removeNSPrefix: true,
    trimValues: true,
    parseTagValue: false,
    parseAttributeValue: false,
    processEntities: true
  });
}

function toArray(value) {
  if (value == null) return [];
  return Array.isArray(value) ? value : [value];
}

function truncateText(value, maxChars) {
  const text = normalizeText(value);
  if (!text) return { text: null, truncated: false };
  return {
    text: text.slice(0, maxChars),
    truncated: text.length > maxChars
  };
}

function parsePublishedAt(item) {
  for (const candidate of [item.pubDate, item.published, item.updated, item.date, item.created]) {
    const value = rawText(candidate);
    if (!value) continue;
    const date = new Date(value);
    if (!Number.isNaN(date.getTime())) return date.toISOString();
  }
  return null;
}

function extractLink(item) {
  const links = toArray(item.link);
  for (const link of links) {
    if (link && typeof link === 'object' && link['@_href'] && (!link['@_rel'] || link['@_rel'] === 'alternate')) {
      return String(link['@_href']).trim();
    }
  }
  for (const link of links) {
    if (link && typeof link === 'object' && link['@_href']) return String(link['@_href']).trim();
    const text = rawText(link).trim();
    if (text) return text;
  }
  return null;
}

function fallbackId({
  feedUrl = '',
  title = '',
  publishedAt = '',
  summary = '',
  content = '',
  description = ''
}) {
  const text = summary || content || description || '';
  const digest = crypto.createHash('sha256')
    .update([feedUrl, title, publishedAt || '', text].join('\n'))
    .digest('hex');
  return `sha256:${digest}`;
}

function normalizeItem(item, feedUrl) {
  const title = normalizeText(item.title) || 'Untitled';
  const url = extractLink(item);
  const publishedAt = parsePublishedAt(item);
  const summary = truncateText(item.summary || item.description, SUMMARY_MAX_CHARS);
  const content = truncateText(item.content || item.encoded, CONTENT_MAX_CHARS);
  const explicitId = normalizeText(item.guid || item.id);

  return {
    id: explicitId || url || fallbackId({
      feedUrl,
      title,
      publishedAt,
      summary: summary.text,
      content: content.text
    }),
    title,
    url,
    published_at: publishedAt,
    summary: summary.text,
    summary_truncated: summary.truncated,
    content: content.text,
    content_truncated: content.truncated,
    source_feed_url: feedUrl || null
  };
}

function dedupeItems(items) {
  const seen = new Set();
  const result = [];
  for (const item of items) {
    const scope = item.feed_url || item.source_feed_url || '';
    const identity = item.id || item.url || fallbackId(item);
    const key = `${scope}|${identity}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(item);
  }
  return result;
}

function parseFeedXml(xml, feedUrl = '') {
  const validation = XMLValidator.validate(xml);
  if (validation !== true) {
    const detail = validation?.err?.msg || 'validation failed';
    throw createError('XML_PARSE_ERROR', `Invalid XML: ${detail}`);
  }

  let parsed;
  try {
    parsed = parser().parse(xml);
  } catch (error) {
    throw createError('XML_PARSE_ERROR', `Invalid XML: ${error.message}`);
  }

  let title = 'Unknown Feed';
  let rawItems = [];
  if (parsed.rss?.channel) {
    title = normalizeText(parsed.rss.channel.title) || title;
    rawItems = toArray(parsed.rss.channel.item);
  } else if (parsed.feed) {
    title = normalizeText(parsed.feed.title) || title;
    rawItems = toArray(parsed.feed.entry);
  } else if (parsed.RDF) {
    title = normalizeText(parsed.RDF.channel?.title) || title;
    rawItems = toArray(parsed.RDF.item);
  } else {
    throw createError('UNSUPPORTED_FEED', 'XML does not contain a supported RSS, Atom, or RDF feed root.');
  }

  return {
    title,
    items: dedupeItems(rawItems.map((item) => normalizeItem(item || {}, feedUrl)))
  };
}

function parseSince(value, now = new Date()) {
  if (!value) return null;
  const match = /^(\d+)(h|d)$/.exec(String(value).trim());
  if (!match || Number(match[1]) <= 0) {
    throw createError('INVALID_SINCE', '--since must be a positive integer followed by h or d, e.g. 24h or 7d.');
  }
  const amount = Number(match[1]);
  const multiplier = match[2] === 'h' ? 60 * 60 * 1000 : 24 * 60 * 60 * 1000;
  return new Date(now.getTime() - amount * multiplier);
}

function normalizeKeywords(value) {
  if (!value) return [];
  return String(value).split(',').map((keyword) => keyword.trim().toLowerCase()).filter(Boolean);
}

function sortItems(items) {
  return [...items].sort((a, b) => {
    if (a.published_at && b.published_at) return new Date(b.published_at) - new Date(a.published_at);
    if (a.published_at) return -1;
    if (b.published_at) return 1;
    return a.title.localeCompare(b.title);
  });
}

module.exports = {
  CONTENT_MAX_CHARS,
  SUMMARY_MAX_CHARS,
  dedupeItems,
  fallbackId,
  normalizeKeywords,
  parseFeedXml,
  parseSince,
  sortItems
};
