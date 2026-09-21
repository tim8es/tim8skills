'use strict';

const {
  loadConfig,
  normalizeCategory,
  normalizeText,
  saveConfig,
  toPublicFeed,
  validateHttpUrl
} = require('./config');
const { createError } = require('./errors');
const { dedupeItems, normalizeKeywords, parseFeedXml, parseSince, sortItems } = require('./feed');
const { fetchUrl } = require('./http');

const SCHEMA_VERSION = 1;

async function addFeed(url, options = {}, dependencies = {}) {
  const retrieve = dependencies.fetchUrl || fetchUrl;
  const normalizedUrl = validateHttpUrl(url);
  const config = loadConfig();
  if (config.feeds.some((feed) => feed.url === normalizedUrl)) {
    throw createError('FEED_EXISTS', `Feed already exists: ${normalizedUrl}`);
  }

  const parsed = parseFeedXml(await retrieve(normalizedUrl), normalizedUrl);
  const feed = {
    url: normalizedUrl,
    name: normalizeText(options.name) || parsed.title || normalizedUrl,
    category: normalizeCategory(options.category),
    enabled: true,
    lastChecked: null,
    lastItemDate: null
  };
  config.feeds.push(feed);
  saveConfig(config);
  return {
    schema_version: SCHEMA_VERSION,
    command: 'add',
    ok: true,
    feed: toPublicFeed(feed),
    validated_item_count: parsed.items.length
  };
}

async function removeFeed(selector) {
  const config = loadConfig();
  const lowered = String(selector).toLowerCase();
  let normalizedSelector = null;
  try { normalizedSelector = validateHttpUrl(selector); } catch { /* selector may be a name */ }
  const index = config.feeds.findIndex((feed) => feed.url === normalizedSelector || feed.name.toLowerCase() === lowered);
  if (index === -1) throw createError('FEED_NOT_FOUND', `Feed not found: ${selector}`);

  const [removed] = config.feeds.splice(index, 1);
  saveConfig(config);
  return { schema_version: SCHEMA_VERSION, command: 'remove', ok: true, feed: toPublicFeed(removed) };
}

function listFeeds() {
  const config = loadConfig();
  return {
    schema_version: SCHEMA_VERSION,
    command: 'list',
    ok: true,
    feed_count: config.feeds.length,
    feeds: config.feeds.map(toPublicFeed)
  };
}

async function checkFeeds(options = {}, now = new Date(), dependencies = {}) {
  const retrieve = dependencies.fetchUrl || fetchUrl;
  const config = loadConfig();
  const category = options.category ? normalizeCategory(options.category) : null;
  const sinceDate = parseSince(options.since, now);
  const keywords = normalizeKeywords(options.keywords);
  const feeds = config.feeds.filter((feed) => feed.enabled && (!category || feed.category === category));
  const items = [];
  const errors = [];
  let checkedFeeds = 0;

  for (const feed of feeds) {
    try {
      const parsed = parseFeedXml(await retrieve(feed.url), feed.url);
      checkedFeeds += 1;
      feed.lastChecked = now.toISOString();
      const datedItems = parsed.items.filter((item) => item.published_at);
      if (datedItems.length) feed.lastItemDate = sortItems(datedItems)[0].published_at;

      let feedItems = parsed.items;
      if (sinceDate) {
        feedItems = feedItems.filter((item) => item.published_at && new Date(item.published_at) > sinceDate);
      }
      if (keywords.length) {
        feedItems = feedItems.filter((item) => {
          const text = `${item.title} ${item.summary || ''} ${item.content || ''}`.toLowerCase();
          return keywords.some((keyword) => text.includes(keyword));
        });
      }

      for (const item of feedItems.slice(0, config.settings.maxItemsPerFeed)) {
        items.push({
          id: item.id,
          feed_name: feed.name,
          feed_url: feed.url,
          category: feed.category,
          title: item.title,
          url: item.url,
          published_at: item.published_at,
          summary: item.summary,
          summary_truncated: item.summary_truncated,
          content: item.content,
          content_truncated: item.content_truncated
        });
      }
    } catch (error) {
      errors.push({
        feed_name: feed.name,
        feed_url: feed.url,
        code: error.code || 'FETCH_ERROR',
        message: error.message
      });
    }
  }

  saveConfig(config);
  const resultItems = dedupeItems(sortItems(items));
  return {
    schema_version: SCHEMA_VERSION,
    command: 'check',
    ok: errors.length === 0,
    partial: errors.length > 0 && checkedFeeds > 0,
    checked_at: now.toISOString(),
    filters: { category, since: options.since || null, keywords },
    feed_count: feeds.length,
    checked_feeds: checkedFeeds,
    failed_feeds: errors.length,
    item_count: resultItems.length,
    items: resultItems,
    errors
  };
}

function timeAgo(isoDate) {
  if (!isoDate) return 'unknown date';
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(isoDate).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function outputList(payload) {
  if (payload.command === 'list') {
    if (!payload.feeds.length) return console.log('No feeds configured.');
    console.log(`\nRSS Feeds (${payload.feed_count}):\n`);
    for (const feed of payload.feeds) {
      console.log(`[${feed.category}] ${feed.enabled ? '✓' : '✗'} ${feed.name}`);
      console.log(`  ${feed.url}`);
      console.log(`  Last checked: ${feed.last_checked ? timeAgo(feed.last_checked) : 'never'}`);
    }
    return;
  }
  if (payload.command === 'add') return console.log(`✓ Added: "${payload.feed.name}" (${payload.validated_item_count} items) [${payload.feed.category}]`);
  if (payload.command === 'remove') return console.log(`✓ Removed: "${payload.feed.name}"`);

  if (!payload.items.length) {
    console.log(payload.errors.length ? 'No items returned; one or more feeds failed.' : 'No matching items found.');
  } else {
    console.log(`\nFound ${payload.item_count} items:\n`);
    for (const item of payload.items) {
      console.log(`[${item.category}] ${item.feed_name} - "${item.title}" (${timeAgo(item.published_at)})`);
      if (item.url) console.log(`  ${item.url}`);
    }
  }
  if (payload.errors.length) {
    console.error(`\nFeed errors (${payload.errors.length}):`);
    for (const error of payload.errors) console.error(`  ✗ ${error.feed_name}: ${error.message}`);
  }
}

function outputIdeas(payload) {
  if (!payload.items.length) return outputList(payload);
  console.log('\n## Content Ideas from RSS\n');
  const groups = new Map();
  for (const item of payload.items) {
    if (!groups.has(item.category)) groups.set(item.category, []);
    groups.get(item.category).push(item);
  }
  for (const [category, items] of groups.entries()) {
    console.log(`### ${category.charAt(0).toUpperCase()}${category.slice(1)}\n`);
    for (const item of items.slice(0, 5)) {
      console.log(`- **"${item.title}"** — [${item.feed_name}]`);
      const preview = item.summary || item.content;
      if (preview) console.log(`  ${preview.slice(0, 200)}${preview.length > 200 ? '…' : ''}`);
      if (item.url) console.log(`  ${item.url}`);
      console.log();
    }
  }
  if (payload.errors.length) outputList({ ...payload, items: [] });
}

function printPayload(payload, format) {
  if (format === 'json') console.log(JSON.stringify(payload, null, 2));
  else if (format === 'ideas' && payload.command === 'check') outputIdeas(payload);
  else outputList(payload);
}

function parseArgs(argv) {
  const args = [...argv];
  const command = args.shift();
  const options = {};
  const positionals = [];
  const valueOptions = new Set(['--category', '--name', '--since', '--format', '--keywords']);

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (valueOptions.has(arg)) {
      if (!args[i + 1] || args[i + 1].startsWith('--')) throw createError('USAGE_ERROR', `Missing value for ${arg}.`);
      const key = arg.slice(2).replace(/-([a-z])/g, (_, c) => c.toUpperCase());
      options[key] = args[++i];
    } else if (arg === '--help' || arg === '-h') {
      options.help = true;
    } else if (arg.startsWith('--')) {
      throw createError('USAGE_ERROR', `Unknown option: ${arg}`);
    } else {
      positionals.push(arg);
    }
  }
  return { command, options, positionals };
}

function usage() {
  return `RSS Feed Reader\n\nCommands:\n  add <url>            Add and validate a feed\n  remove <url-or-name> Remove a feed\n  list                 List configured feeds\n  check                Retrieve and filter feed items\n\nOptions:\n  --category <cat>     Filter/set category\n  --name <name>        Set feed name\n  --since <time>       Positive hours/days, e.g. 24h or 7d\n  --format <fmt>       list, ideas, or json\n  --keywords <kw>      Comma-separated keywords\n`;
}

async function main(argv = process.argv.slice(2)) {
  try {
    const { command, options, positionals } = parseArgs(argv);
    if (!command || options.help || command === 'help') {
      console.log(usage());
      return 0;
    }

    const format = options.format || 'list';
    if (!['list', 'ideas', 'json'].includes(format)) throw createError('USAGE_ERROR', '--format must be one of: list, ideas, json.');

    let payload;
    if (command === 'add') {
      if (!positionals[0]) throw createError('USAGE_ERROR', 'Usage: add <url> [--category <cat>] [--name <name>]');
      payload = await addFeed(positionals[0], options);
    } else if (command === 'remove' || command === 'rm') {
      if (!positionals[0]) throw createError('USAGE_ERROR', 'Usage: remove <url-or-name>');
      payload = await removeFeed(positionals[0]);
    } else if (command === 'list' || command === 'ls') {
      payload = listFeeds();
    } else if (command === 'check') {
      payload = await checkFeeds(options);
    } else {
      throw createError('USAGE_ERROR', `Unknown command: ${command}`);
    }

    printPayload(payload, format);
    if (payload.command === 'check' && payload.partial) return 2;
    if (payload.command === 'check' && payload.feed_count > 0 && payload.checked_feeds === 0 && payload.failed_feeds > 0) return 1;
    return 0;
  } catch (error) {
    const payload = { schema_version: SCHEMA_VERSION, ok: false, error: { code: error.code || 'ERROR', message: error.message } };
    const formatIndex = argv.indexOf('--format');
    if (formatIndex !== -1 && argv[formatIndex + 1] === 'json') console.log(JSON.stringify(payload, null, 2));
    else console.error(`Error [${payload.error.code}]: ${payload.error.message}`);
    return 1;
  }
}

module.exports = {
  addFeed,
  checkFeeds,
  listFeeds,
  main,
  parseArgs,
  removeFeed
};
